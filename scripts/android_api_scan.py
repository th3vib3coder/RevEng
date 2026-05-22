from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SOURCE_EXTS = {".java", ".kt", ".xml", ".properties", ".gradle", ".kts"}
RETROFIT_RE = re.compile(r"@(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\(\s*\"([^\"]+)\"", re.I)
URL_RE = re.compile(r"\bhttps?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")
AUTH_RE = re.compile(r"(?i)\b(Authorization|Bearer|X-API-Key|api[_-]?key|token)\b")
OKHTTP_RE = re.compile(r"\.url\(\s*\"([^\"]+)\"", re.I)
VOLLEY_RE = re.compile(r"\b(Request\.Method\.(GET|POST|PUT|DELETE|PATCH))\b.*?\"([^\"]+)\"", re.I)

DEFAULT_MAX_FILE_BYTES = 1024 * 1024


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def iter_source(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SOURCE_EXTS:
            yield path


def scan(root: Path, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")
    base_urls: set[str] = set()
    endpoints: list[dict[str, Any]] = []
    auth_headers: list[dict[str, Any]] = []
    source_files: list[str] = []
    skipped_files: list[str] = []
    for path in iter_source(root):
        rel = path.relative_to(root).as_posix()
        # Skip symlinks (no reading outside the tree) and oversized files, and
        # bound the per-file read so a crafted huge source file cannot exhaust memory.
        if path.is_symlink() or path.stat().st_size > max_file_bytes:
            skipped_files.append(rel)
            continue
        source_files.append(rel)
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            text = handle.read(max_file_bytes)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in RETROFIT_RE.finditer(line):
                endpoints.append({"kind": "retrofit", "method": match.group(1).upper(), "path": match.group(2), "source": rel, "line": line_no})
            for match in OKHTTP_RE.finditer(line):
                value = match.group(1)
                endpoints.append({"kind": "okhttp", "method": "UNKNOWN", "path": value, "source": rel, "line": line_no})
            for match in VOLLEY_RE.finditer(line):
                endpoints.append({"kind": "volley", "method": match.group(2).upper(), "path": match.group(3), "source": rel, "line": line_no})
            for url in URL_RE.findall(line):
                base = re.match(r"^(https?://[^/]+/?)", url)
                if base:
                    base_urls.add(base.group(1))
            if AUTH_RE.search(line):
                auth_headers.append({"source": rel, "line": line_no, "evidence": line.strip()[:240]})
    limitations = ["Static source scan only; app code and endpoints were not executed or contacted."]
    if skipped_files:
        limitations.append(
            f"{len(skipped_files)} file(s) skipped (symlink or larger than --max-file-bytes={max_file_bytes})."
        )
    return {
        "base_urls": sorted(base_urls),
        "endpoints": sorted(endpoints, key=lambda item: (item["source"], item["line"], item["path"])),
        "auth_headers": auth_headers,
        "source_files": source_files,
        "skipped_files": sorted(skipped_files),
        "limitations": limitations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan decompiled Android source for API surfaces")
    parser.add_argument("source_root")
    parser.add_argument("--json-out", required=True)
    parser.add_argument(
        "--max-file-bytes",
        type=positive_int,
        default=DEFAULT_MAX_FILE_BYTES,
        help="Skip files larger than this and bound the bytes read from each scanned file",
    )
    args = parser.parse_args()

    payload = scan(Path(args.source_root), max_file_bytes=args.max_file_bytes)
    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
