from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from repo_common import classify_kind, detect_language, iter_repo_files, looks_binary, read_text, repo_relative, sha256_file


SYMBOL_PATTERNS = [
    re.compile(r"^\s*(?:def|async def)\s+([A-Za-z_][\w]*)\s*\(", re.M),
    re.compile(r"^\s*class\s+([A-Za-z_][\w]*)\b", re.M),
    re.compile(r"^\s*(?:export\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", re.M),
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=", re.M),
]

IMPORT_PATTERNS = [
    re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.M),
    re.compile(r"^\s*import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]", re.M),
    re.compile(r"\brequire\(\s*['\"]([^'\"]+)['\"]\s*\)", re.M),
]


def extract_symbols(text: str) -> list[str]:
    symbols: set[str] = set()
    for pattern in SYMBOL_PATTERNS:
        symbols.update(match.group(1) for match in pattern.finditer(text))
    return sorted(symbols)


def extract_imports(text: str) -> list[str]:
    imports: set[str] = set()
    for pattern in IMPORT_PATTERNS:
        for match in pattern.finditer(text):
            for group in match.groups():
                if group:
                    imports.add(group)
    return sorted(imports)


def evidence_lines(text: str, max_lines: int = 5) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped:
            evidence.append({"line": line_no, "text": stripped[:240]})
        if len(evidence) >= max_lines:
            break
    return evidence


def summarize(rel: str, kind: str, language: str, text: str) -> str:
    first = ""
    for line in text.splitlines():
        stripped = line.strip().strip("#/ ")
        if stripped:
            first = stripped[:160]
            break
    if first:
        return f"{kind} {language} file {rel}: {first}"
    return f"{kind} {language} file {rel}"


def build_records(root: Path, max_file_bytes: int) -> list[dict[str, Any]]:
    root = root.resolve()
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")

    records: list[dict[str, Any]] = []
    for path in iter_repo_files(root):
        rel = repo_relative(root, path)
        if looks_binary(path) or path.stat().st_size > max_file_bytes:
            continue
        text = read_text(path, max_bytes=max_file_bytes)
        kind = classify_kind(root, path)
        language = detect_language(path)
        records.append(
            {
                "path": rel,
                "kind": kind,
                "language": language,
                "sha256": sha256_file(path),
                "summary": summarize(rel, kind, language, text),
                "symbols": extract_symbols(text),
                "imports": extract_imports(text),
                "evidence": evidence_lines(text),
            }
        )
    return sorted(records, key=lambda item: item["path"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Export repository corpus as JSONL")
    parser.add_argument("repo", help="Repository directory to inspect")
    parser.add_argument("--jsonl-out", required=True, help="Write corpus JSONL to this path")
    parser.add_argument("--max-file-bytes", type=int, default=500_000)
    args = parser.parse_args()

    records = build_records(Path(args.repo), args.max_file_bytes)
    out = Path(args.jsonl_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    tmp.replace(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
