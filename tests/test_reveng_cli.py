from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: object, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "reveng.py"), *(str(arg) for arg in args)],
        text=True,
        capture_output=True,
        check=check,
    )


def test_reveng_check_tools_json_dispatches() -> None:
    result = run_cli("check-tools", "--json")
    payload = json.loads(result.stdout)
    assert "tools" in payload
    assert "adapters" in payload
    assert payload["execution_policy"]["adapters_invoked"] is False


def test_reveng_analyze_repo_produces_full_case(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "cli.py").write_text("import os\n\n\ndef main():\n    return 1\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = \"x\"\ndependencies = []\n", encoding="utf-8")
    out = tmp_path / "case"

    run_cli("analyze-repo", str(repo), "--out", str(out))

    for name in ("repo_inventory.json", "repo_map.json", "repo_corpus.jsonl", "case_manifest.json"):
        assert (out / name).is_file(), name
    manifest = json.loads((out / "case_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "reveng.case_manifest.v1"
    assert {item["name"] for item in manifest["artifacts"]} == {"repo_inventory", "repo_map", "repo_corpus"}
    corpus = [json.loads(line) for line in (out / "repo_corpus.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert corpus
    assert all("graph_refs" in record for record in corpus)


def test_reveng_triage_binary_dispatches(tmp_path: Path) -> None:
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"MZ" + b"A" * 64)
    out = tmp_path / "triage.json"

    run_cli("triage-binary", str(sample), "--out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["file_type"] == "PE/DOS MZ"
    assert payload["hashes"]["sha256"]


def test_reveng_ghidra_smoke_dispatches_without_invoking_ghidra(tmp_path: Path) -> None:
    out = tmp_path / "ghidra-smoke.json"

    run_cli("ghidra-smoke", "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema"] == "reveng.ghidra_smoke.v1"
    assert payload["execution_policy"]["sample_executed"] is False
    if payload["status"] == "skipped":
        assert payload["execution_policy"]["ghidra_invoked"] is False
