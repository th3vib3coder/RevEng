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


def iter_source(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SOURCE_EXTS:
            yield path


def scan(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")
    base_urls: set[str] = set()
    endpoints: list[dict[str, Any]] = []
    auth_headers: list[dict[str, Any]] = []
    source_files: list[str] = []
    for path in iter_source(root):
        rel = path.relative_to(root).as_posix()
        source_files.append(rel)
        text = path.read_text(encoding="utf-8", errors="replace")
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
    return {
        "base_urls": sorted(base_urls),
        "endpoints": sorted(endpoints, key=lambda item: (item["source"], item["line"], item["path"])),
        "auth_headers": auth_headers,
        "source_files": source_files,
        "limitations": ["Static source scan only; app code and endpoints were not executed or contacted."],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan decompiled Android source for API surfaces")
    parser.add_argument("source_root")
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    payload = scan(Path(args.source_root))
    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

