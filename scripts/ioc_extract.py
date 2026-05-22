from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


HASH_RE = re.compile(r"\b(?P<hash>[A-Fa-f0-9]{32}|[A-Fa-f0-9]{40}|[A-Fa-f0-9]{64})\b")
URL_RE = re.compile(r"\b(?P<url>hxxps?://[^\s'\"<>]+|https?://[^\s'\"<>]+)", re.I)
IPV4_RE = re.compile(r"\b(?P<ip>(?:\d{1,3}\.){3}\d{1,3})\b")
EMAIL_RE = re.compile(r"\b(?P<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
USER_AGENT_RE = re.compile(r"(?i)\bUser-Agent:\s*(?P<ua>.+)")
REGISTRY_RE = re.compile(r"(?i)\b(?P<reg>HKEY_[A-Z_\\0-9A-Za-z .-]+)")
WIN_PATH_RE = re.compile(r"\b(?P<path>[A-Za-z]:\\[^\r\n\t<>|]+)")
VERSION_CONTEXT_RE = re.compile(r"(?i)(?:\bversion\b|\brelease\b|\bbuild\b|\bv)\s*[:=]?\s*$")

MAX_ITEMS_PER_CATEGORY = 1000
DEFAULT_MAX_LINE_CHARS = 16 * 1024


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def confidence(value: str) -> str:
    return "candidate" if "hxxp" in value.lower() or "[.]" in value else "confirmed"


def normalize_url(value: str) -> str:
    normalized = re.sub(r"^hxxp", "http", value, flags=re.I)
    normalized = normalized.replace("[.]", ".")
    match = re.match(r"^(https?://)([^/]+)(.*)$", normalized, flags=re.I)
    if match:
        return match.group(1).lower() + match.group(2).lower() + match.group(3)
    return normalized


def hash_algorithm(value: str) -> str:
    return {32: "md5", 40: "sha1", 64: "sha256"}[len(value)]


def ipv4_confidence(line: str, start: int) -> str:
    prefix = line[max(0, start - 40) : start]
    return "contextual" if VERSION_CONTEXT_RE.search(prefix) else "confirmed"


def add_item(
    group: dict[str, list[dict[str, Any]]],
    seen_index: dict[str, set[tuple[Any, Any]]],
    key: str,
    item: dict[str, Any],
) -> bool:
    """Add an item; return True if dropped because the category cap was reached.

    Dedup uses a persistent per-category set (O(1) per call) so flooded input
    cannot trigger O(n^2) work rebuilding the seen-set on every call.
    """
    bucket = group.setdefault(key, [])
    seen = seen_index.setdefault(key, set())
    marker = (item.get("value"), item.get("evidence_snippet"))
    if marker in seen:
        return False
    if len(bucket) >= MAX_ITEMS_PER_CATEGORY:
        return True
    bucket.append(item)
    seen.add(marker)
    return False


def scan_line(
    line: str,
    out: dict[str, list[dict[str, Any]]],
    seen_index: dict[str, set[tuple[Any, Any]]],
    source: str,
) -> bool:
    truncated = False
    snippet = line.strip()[:500]
    for match in HASH_RE.finditer(line):
        value = match.group("hash").lower()
        truncated |= add_item(out, seen_index, "hashes", {"value": value, "algorithm": hash_algorithm(value), "confidence": "confirmed", "source": source, "evidence_snippet": snippet})
    for match in URL_RE.finditer(line):
        value = match.group("url").rstrip(".,);]")
        truncated |= add_item(out, seen_index, "network", {"kind": "url", "value": value, "confidence": confidence(value), "source": source, "evidence_snippet": snippet})
        normalized = normalize_url(value)
        if normalized != value:
            truncated |= add_item(out, seen_index, "network", {"kind": "url", "value": normalized, "confidence": "candidate", "source": source, "evidence_snippet": snippet})
    for match in IPV4_RE.finditer(line):
        value = match.group("ip")
        octets = value.split(".")
        if all(0 <= int(octet) <= 255 for octet in octets):
            truncated |= add_item(out, seen_index, "network", {"kind": "ipv4", "value": value, "confidence": ipv4_confidence(line, match.start()), "source": source, "evidence_snippet": snippet})
    for match in EMAIL_RE.finditer(line):
        truncated |= add_item(out, seen_index, "emails", {"value": match.group("email"), "confidence": "confirmed", "source": source, "evidence_snippet": snippet})
    ua = USER_AGENT_RE.search(line)
    if ua:
        truncated |= add_item(out, seen_index, "user_agents", {"value": ua.group("ua").strip(), "confidence": "contextual", "source": source, "evidence_snippet": snippet})
    reg = REGISTRY_RE.search(line)
    if reg:
        truncated |= add_item(out, seen_index, "registry", {"kind": "key", "value": reg.group("reg").strip(), "confidence": "contextual", "source": source, "evidence_snippet": snippet})
    win_path = WIN_PATH_RE.search(line)
    if win_path:
        truncated |= add_item(out, seen_index, "file_paths", {"value": win_path.group("path").strip(), "confidence": "contextual", "source": source, "evidence_snippet": snippet})
    return truncated


def extract(path: Path, max_line_chars: int = DEFAULT_MAX_LINE_CHARS) -> dict[str, Any]:
    out: dict[str, list[dict[str, Any]]] = {}
    seen_index: dict[str, set[tuple[Any, Any]]] = {}
    source = path.as_posix()
    truncated = False
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        while True:
            raw = handle.readline(max_line_chars + 1)
            if not raw:
                break
            had_newline = raw.endswith("\n")
            line = raw[:-1] if had_newline else raw
            if not had_newline and len(raw) > max_line_chars:
                # Overlong physical line: scan only the bounded prefix, then drain
                # the remainder in bounded reads so memory stays bounded even on a
                # newline-free multi-gigabyte input.
                truncated = True
                truncated |= scan_line(line[:max_line_chars], out, seen_index, source)
                while True:
                    cont = handle.readline(max_line_chars + 1)
                    if not cont or cont.endswith("\n"):
                        break
                continue
            truncated |= scan_line(line, out, seen_index, source)
    result: dict[str, Any] = {key: value for key, value in out.items() if value}
    # Signal when a per-category cap dropped indicators or an overlong line was
    # clipped, so a report never looks complete while silently discarding evidence.
    result["truncated"] = truncated
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract traceable defensive IOCs from evidence text")
    parser.add_argument("evidence")
    parser.add_argument("--json-out", required=True)
    parser.add_argument(
        "--max-line-chars",
        type=positive_int,
        default=DEFAULT_MAX_LINE_CHARS,
        help="Maximum characters scanned per evidence line before marking the report truncated",
    )
    args = parser.parse_args()

    payload = extract(Path(args.evidence), max_line_chars=args.max_line_chars)
    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
