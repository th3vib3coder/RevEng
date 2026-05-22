from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_script(script: str, *args: object, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *(str(arg) for arg in args)],
        text=True,
        capture_output=True,
        check=check,
    )


def test_case_manifest_supports_binary_file_target(tmp_path: Path) -> None:
    sample = tmp_path / "sample.bin"
    payload_bytes = b"MZ" + b"A" * 200
    sample.write_bytes(payload_bytes)
    triage = tmp_path / "triage.json"
    triage.write_text('{"sample": {"name": "sample.bin"}}\n', encoding="utf-8")
    case_dir = tmp_path / "case"
    out = case_dir / "case_manifest.json"

    run_script(
        "case_manifest.py",
        "--case-dir",
        case_dir,
        "--target",
        sample,
        "--target-kind",
        "binary",
        "--artifact",
        f"triage={triage}",
        "--json-out",
        out,
    )

    manifest = json.loads(out.read_text(encoding="utf-8"))
    assert manifest["target"]["kind"] == "binary"
    assert manifest["target"]["content_sha256"] == hashlib.sha256(payload_bytes).hexdigest()
    assert manifest["case_id"].startswith("reveng-")
    assert {item["name"] for item in manifest["artifacts"]} == {"triage"}


def test_case_manifest_rejects_missing_target(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    result = run_script(
        "case_manifest.py",
        "--case-dir",
        case_dir,
        "--target",
        tmp_path / "does-not-exist",
        "--json-out",
        case_dir / "case_manifest.json",
        check=False,
    )
    assert result.returncode != 0
