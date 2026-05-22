from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable


IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "vendor",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    "coverage",
}

LANG_BY_EXT = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".h": "C/C++",
    ".cpp": "C++",
    ".cc": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".scala": "Scala",
    ".sh": "Shell",
    ".ps1": "PowerShell",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".html": "HTML",
    ".css": "CSS",
    ".sql": "SQL",
    ".dockerfile": "Dockerfile",
}

TEXT_EXTS = set(LANG_BY_EXT) | {
    ".txt",
    ".cfg",
    ".ini",
    ".env",
    ".example",
    ".lock",
    ".gradle",
    ".properties",
    ".gitignore",
}

MANIFEST_NAMES = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".mcp.json",
    ".app.json",
}


def repo_relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def is_ignored_dir(name: str) -> bool:
    return name in IGNORE_DIRS


def iter_repo_files(root: Path) -> Iterable[Path]:
    # followlinks=False prevents symlinked-directory recursion loops; symlinked
    # files are skipped so the scanner never reads content outside the analyzed
    # repository (defense against symlink-based path traversal / info disclosure).
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(
            d
            for d in dirs
            if not is_ignored_dir(d) and not os.path.islink(os.path.join(current, d))
        )
        for filename in sorted(files):
            path = Path(current) / filename
            if path.is_symlink():
                continue
            yield path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_bytes_prefix(path: Path, limit: int = 4096) -> bytes:
    with path.open("rb") as handle:
        return handle.read(limit)


def looks_binary(path: Path) -> bool:
    data = read_bytes_prefix(path)
    return b"\x00" in data


def read_text(path: Path, max_bytes: int = 500_000) -> str:
    # Bounded read: never load more than max_bytes into memory. A whole-file
    # read()[:max_bytes] would still buffer a multi-GB file before slicing it.
    with path.open("rb") as handle:
        data = handle.read(max_bytes)
    return data.decode("utf-8", errors="replace")


def detect_language(path: Path) -> str:
    name = path.name
    suffix = path.suffix.lower()
    if name == "Dockerfile":
        return "Dockerfile"
    if suffix in LANG_BY_EXT:
        return LANG_BY_EXT[suffix]
    if name in {".gitignore", ".env", ".env.example"}:
        return "Text"
    return "Unknown"


def classify_kind(root: Path, path: Path) -> str:
    rel = repo_relative(root, path)
    name = path.name
    lower_rel = rel.lower()
    if rel in {".codex-plugin/plugin.json", ".claude-plugin/plugin.json"} or name in {".mcp.json", ".app.json"}:
        return "plugin_manifest"
    if name in MANIFEST_NAMES:
        return "manifest"
    if name.startswith(".env"):
        return "config"
    if lower_rel.startswith(".github/workflows/") or name in {"Dockerfile", "docker-compose.yml", "docker-compose.yaml"}:
        return "config"
    if lower_rel.startswith("docs/") or path.suffix.lower() in {".md", ".rst"}:
        return "docs"
    if "/test" in f"/{lower_rel}" or name.startswith("test_") or name.endswith("_test.py") or name.endswith(".test.ts"):
        return "test"
    if detect_language(path) not in {"Unknown", "Markdown", "JSON", "YAML", "TOML", "XML", "HTML", "CSS"}:
        return "source"
    return "other"


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(read_text(path))
    except Exception:
        return {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def line_evidence(text: str, needle: str, limit: int = 3) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            evidence.append({"line": line_no, "text": line.strip()[:240]})
            if len(evidence) >= limit:
                break
    return evidence
