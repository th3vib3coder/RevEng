from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from repo_common import (
    IGNORE_DIRS,
    classify_kind,
    detect_language,
    iter_repo_files,
    looks_binary,
    repo_relative,
    sha256_file,
    write_json,
)


def build_inventory(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")

    files: list[dict[str, Any]] = []
    languages: dict[str, dict[str, int]] = defaultdict(lambda: {"files": 0, "bytes": 0})
    manifests: list[dict[str, Any]] = []

    for path in iter_repo_files(root):
        try:
            size = path.stat().st_size
            rel = repo_relative(root, path)
            language = detect_language(path)
            kind = classify_kind(root, path)
            is_text = not looks_binary(path)
            record = {
                "path": rel,
                "size_bytes": size,
                "sha256": sha256_file(path),
                "language": language,
                "kind": kind,
                "is_text": is_text,
            }
            files.append(record)
            languages[language]["files"] += 1
            languages[language]["bytes"] += size
            if kind in {"manifest", "plugin_manifest", "config"}:
                manifests.append({"path": rel, "kind": kind, "language": language})
        except OSError as exc:
            files.append({"path": str(path), "error": str(exc)})

    return {
        "root": str(root),
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "ignored_directories": sorted(IGNORE_DIRS),
        "file_count": len(files),
        "total_size_bytes": sum(item.get("size_bytes", 0) for item in files),
        "languages": dict(sorted(languages.items())),
        "manifests": sorted(manifests, key=lambda item: item["path"]),
        "files": sorted(files, key=lambda item: item["path"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Static repository inventory")
    parser.add_argument("repo", help="Repository directory to inspect")
    parser.add_argument("--json-out", help="Write inventory JSON to this path")
    args = parser.parse_args()

    payload = build_inventory(Path(args.repo))
    if args.json_out:
        write_json(Path(args.json_out), payload)
    else:
        import json

        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

