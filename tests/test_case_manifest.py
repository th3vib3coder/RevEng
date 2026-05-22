from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_repo_reverse_engineering import make_fixture, run_script


ROOT = Path(__file__).resolve().parents[1]


def run_case_manifest(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "case_manifest.py"), *args],
        text=True,
        capture_output=True,
        check=True,
    )


def build_repo_artifacts(repo: Path, case_dir: Path) -> tuple[Path, Path, Path]:
    inventory = case_dir / "repo_inventory.json"
    repo_map = case_dir / "repo_map.json"
    corpus = case_dir / "repo_corpus.jsonl"
    run_script("repo_inventory.py", str(repo), "--json-out", str(inventory))
    run_script("repo_map.py", str(repo), "--json-out", str(repo_map))
    run_script("repo_corpus_export.py", str(repo), "--jsonl-out", str(corpus))
    return inventory, repo_map, corpus


def test_case_manifest_is_deterministic_and_indexes_repo_outputs(tmp_path: Path) -> None:
    repo = make_fixture(tmp_path)
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    inventory, repo_map, corpus = build_repo_artifacts(repo, case_dir)
    out = case_dir / "case_manifest.json"

    args = [
        "--case-dir",
        str(case_dir),
        "--target",
        str(repo),
        "--artifact",
        f"repo_inventory={inventory}",
        "--artifact",
        f"repo_map={repo_map}",
        "--artifact",
        f"repo_corpus={corpus}",
        "--cap",
        "repo_corpus_max_file_bytes=500000",
        "--json-out",
        str(out),
    ]
    run_case_manifest(*args)
    first = out.read_text(encoding="utf-8")
    run_case_manifest(*args)
    second = out.read_text(encoding="utf-8")

    assert first == second
    payload = json.loads(first)
    assert payload["schema"] == "reveng.case_manifest.v1"
    assert payload["target"]["kind"] == "source_repo"
    assert payload["target"]["path_role"] == "operator_input"
    assert payload["target"]["content_sha256"]
    artifact_names = {item["name"] for item in payload["artifacts"]}
    assert artifact_names == {"repo_inventory", "repo_map", "repo_corpus"}
    assert {item["path"] for item in payload["artifacts"]} == {
        "repo_inventory.json",
        "repo_map.json",
        "repo_corpus.jsonl",
    }
    assert payload["caps"]["repo_corpus_max_file_bytes"] == 500000
    assert payload["script_hashes"]["case_manifest.py"]
    assert payload["script_hashes"]["repo_inventory.py"]
    assert payload["ignored_directories"]


def test_case_manifest_does_not_leak_plugin_absolute_paths(tmp_path: Path) -> None:
    repo = make_fixture(tmp_path)
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    inventory, repo_map, corpus = build_repo_artifacts(repo, case_dir)
    out = case_dir / "case_manifest.json"

    run_case_manifest(
        "--case-dir",
        str(case_dir),
        "--target",
        str(repo),
        "--artifact",
        f"repo_inventory={inventory}",
        "--artifact",
        f"repo_map={repo_map}",
        "--artifact",
        f"repo_corpus={corpus}",
        "--json-out",
        str(out),
    )

    text = out.read_text(encoding="utf-8")
    assert str(ROOT) not in text
    assert "scripts/case_manifest.py" not in text


def test_case_manifest_case_id_is_stable_across_output_locations(tmp_path: Path) -> None:
    repo_a = make_fixture(tmp_path / "a")
    repo_b = make_fixture(tmp_path / "b")
    case_a = tmp_path / "case-a"
    case_b = tmp_path / "case-b"
    case_a.mkdir()
    case_b.mkdir()
    inv_a, map_a, corpus_a = build_repo_artifacts(repo_a, case_a)
    inv_b, map_b, corpus_b = build_repo_artifacts(repo_b, case_b)
    out_a = case_a / "case_manifest.json"
    out_b = case_b / "case_manifest.json"

    common_args = ["--cap", "repo_corpus_max_file_bytes=500000"]
    run_case_manifest(
        "--case-dir",
        str(case_a),
        "--target",
        str(repo_a),
        "--artifact",
        f"repo_inventory={inv_a}",
        "--artifact",
        f"repo_map={map_a}",
        "--artifact",
        f"repo_corpus={corpus_a}",
        "--json-out",
        str(out_a),
        *common_args,
    )
    run_case_manifest(
        "--case-dir",
        str(case_b),
        "--target",
        str(repo_b),
        "--artifact",
        f"repo_inventory={inv_b}",
        "--artifact",
        f"repo_map={map_b}",
        "--artifact",
        f"repo_corpus={corpus_b}",
        "--json-out",
        str(out_b),
        *common_args,
    )

    payload_a = json.loads(out_a.read_text(encoding="utf-8"))
    payload_b = json.loads(out_b.read_text(encoding="utf-8"))
    assert payload_a["target"]["content_sha256"] == payload_b["target"]["content_sha256"]
    assert payload_a["case_id"] == payload_b["case_id"]


def test_case_manifest_rejects_missing_artifact(tmp_path: Path) -> None:
    repo = make_fixture(tmp_path)
    case_dir = tmp_path / "case"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "case_manifest.py"),
            "--case-dir",
            str(case_dir),
            "--target",
            str(repo),
            "--artifact",
            f"repo_inventory={case_dir / 'missing.json'}",
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "artifact not found" in result.stderr
