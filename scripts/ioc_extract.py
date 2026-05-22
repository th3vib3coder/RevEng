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


def add_item(group: dict[str, list[dict[str, Any]]], key: str, item: dict[str, Any]) -> None:
    seen = {(entry.get("value"), entry.get("evidence_snippet")) for entry in group.setdefault(key, [])}
    marker = (item.get("value"), item.get("evidence_snippet"))
    if marker not in seen:
        group[key].append(item)


def extract(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out: dict[str, list[dict[str, Any]]] = {}
    source = path.as_posix()
    for line in text.splitlines():
        snippet = line.strip()[:500]
        for match in HASH_RE.finditer(line):
            value = match.group("hash").lower()
            add_item(out, "hashes", {"value": value, "algorithm": hash_algorithm(value), "confidence": "confirmed", "source": source, "evidence_snippet": snippet})
        for match in URL_RE.finditer(line):
            value = match.group("url").rstrip(".,);]")
            add_item(out, "network", {"kind": "url", "value": value, "confidence": confidence(value), "source": source, "evidence_snippet": snippet})
            normalized = normalize_url(value)
            if normalized != value:
                add_item(out, "network", {"kind": "url", "value": normalized, "confidence": "candidate", "source": source, "evidence_snippet": snippet})
        for match in IPV4_RE.finditer(line):
            value = match.group("ip")
            octets = value.split(".")
            if all(0 <= int(octet) <= 255 for octet in octets):
                add_item(out, "network", {"kind": "ipv4", "value": value, "confidence": "confirmed", "source": source, "evidence_snippet": snippet})
        for match in EMAIL_RE.finditer(line):
            add_item(out, "emails", {"value": match.group("email"), "confidence": "confirmed", "source": source, "evidence_snippet": snippet})
        ua = USER_AGENT_RE.search(line)
        if ua:
            add_item(out, "user_agents", {"value": ua.group("ua").strip(), "confidence": "contextual", "source": source, "evidence_snippet": snippet})
        reg = REGISTRY_RE.search(line)
        if reg:
            add_item(out, "registry", {"kind": "key", "value": reg.group("reg").strip(), "confidence": "contextual", "source": source, "evidence_snippet": snippet})
        win_path = WIN_PATH_RE.search(line)
        if win_path:
            add_item(out, "file_paths", {"value": win_path.group("path").strip(), "confidence": "contextual", "source": source, "evidence_snippet": snippet})
    return {key: value for key, value in out.items() if value}


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract traceable defensive IOCs from evidence text")
    parser.add_argument("evidence")
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    payload = extract(Path(args.evidence))
    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

