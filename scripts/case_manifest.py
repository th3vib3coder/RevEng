from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from repo_common import IGNORE_DIRS, iter_repo_files, repo_relative, sha256_file, write_json


SCHEMA = "reveng.case_manifest.v1"
DEFAULT_SCRIPT_NAMES = (
    "case_manifest.py",
    "repo_inventory.py",
    "repo_map.py",
    "repo_corpus_export.py",
)
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def parse_name_value(raw: str, label: str) -> tuple[str, str]:
    if "=" not in raw:
        raise SystemExit(f"{label} must use name=value syntax")
    name, value = raw.split("=", 1)
    name = name.strip()
    value = value.strip()
    if not name or not NAME_RE.fullmatch(name):
        raise SystemExit(f"{label} name must contain only letters, digits, dot, underscore, or dash")
    if not value:
        raise SystemExit(f"{label} value must not be empty")
    return name, value


def parse_cap(raw: str) -> tuple[str, Any]:
    name, value = parse_name_value(raw, "cap")
    if value.isdigit():
        return name, int(value)
    if value.lower() in {"true", "false"}:
        return name, value.lower() == "true"
    return name, value


def path_for_manifest(case_dir: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(case_dir.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def artifact_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return "jsonl"
    if suffix == ".json":
        return "json"
    if suffix in {".md", ".txt"}:
        return suffix.lstrip(".")
    return "file"


def build_artifact_record(case_dir: Path, name: str, raw_path: str) -> dict[str, Any]:
    path = Path(raw_path)
    if not path.is_file():
        raise SystemExit(f"artifact not found: {path}")
    return {
        "name": name,
        "path": path_for_manifest(case_dir, path),
        "kind": artifact_kind(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def target_content_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in iter_repo_files(root):
        rel = repo_relative(root, path)
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def script_hashes(script_names: tuple[str, ...] = DEFAULT_SCRIPT_NAMES) -> dict[str, str]:
    scripts_dir = Path(__file__).resolve().parent
    hashes: dict[str, str] = {}
    for name in script_names:
        path = scripts_dir / name
        if path.is_file():
            hashes[name] = sha256_file(path)
    return dict(sorted(hashes.items()))


def case_id_for(payload: dict[str, Any]) -> str:
    basis = {
        "schema": payload["schema"],
        "target_kind": payload["target"]["kind"],
        "target_content_sha256": payload["target"]["content_sha256"],
        "caps": payload["caps"],
    }
    encoded = json.dumps(basis, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "reveng-" + hashlib.sha256(encoded).hexdigest()[:16]


def build_manifest(
    *,
    case_dir: Path,
    target: Path,
    target_kind: str,
    artifacts: list[tuple[str, str]],
    caps: dict[str, Any],
    warnings: list[str],
    generated_at: str | None = None,
) -> dict[str, Any]:
    case_dir = case_dir.resolve()
    target = target.resolve()
    if not target.is_dir():
        raise SystemExit(f"target not found or not a directory: {target}")

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "target": {
            "kind": target_kind,
            "path": str(target),
            "path_role": "operator_input",
            "content_sha256": target_content_sha256(target),
        },
        "artifacts": [build_artifact_record(case_dir, name, raw_path) for name, raw_path in artifacts],
        "caps": dict(sorted(caps.items())),
        "script_hashes": script_hashes(),
        "ignored_directories": sorted(IGNORE_DIRS),
        "warnings": sorted(warnings),
        "safety": {
            "static_first": True,
            "executed_target_code": False,
            "network_contacted": False,
        },
    }
    if generated_at is not None:
        payload["generated_at"] = generated_at
    payload["case_id"] = case_id_for(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a deterministic RevEng case_manifest.json")
    parser.add_argument("--case-dir", required=True, help="Case/output directory for this analysis")
    parser.add_argument("--target", required=True, help="Analyzed repository directory")
    parser.add_argument("--target-kind", default="source_repo")
    parser.add_argument("--artifact", action="append", default=[], help="Artifact as name=path; may be repeated")
    parser.add_argument("--cap", action="append", default=[], help="Capability/cap as name=value; may be repeated")
    parser.add_argument("--warning", action="append", default=[], help="Warning string to include; may be repeated")
    parser.add_argument("--generated-at", default=None, help="Optional timestamp; omitted by default for reproducibility")
    parser.add_argument("--json-out", help="Output path; defaults to <case-dir>/case_manifest.json")
    args = parser.parse_args()

    case_dir = Path(args.case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    artifacts = [parse_name_value(item, "artifact") for item in args.artifact]
    caps = dict(parse_cap(item) for item in args.cap)
    payload = build_manifest(
        case_dir=case_dir,
        target=Path(args.target),
        target_kind=args.target_kind,
        artifacts=artifacts,
        caps=caps,
        warnings=list(args.warning),
        generated_at=args.generated_at,
    )
    out = Path(args.json_out) if args.json_out else case_dir / "case_manifest.json"
    write_json(out, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
