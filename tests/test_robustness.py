from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_script(script: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        text=True,
        capture_output=True,
        check=check,
    )


def test_repo_inventory_is_deterministic_by_default(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    out1 = tmp_path / "inv1.json"
    out2 = tmp_path / "inv2.json"

    run_script("repo_inventory.py", str(repo), "--json-out", str(out1))
    run_script("repo_inventory.py", str(repo), "--json-out", str(out2))

    assert out1.read_bytes() == out2.read_bytes()
    payload = json.loads(out1.read_text(encoding="utf-8"))
    assert "generated_at" not in payload


def test_static_triage_caps_bytes_read_but_reports_true_size(tmp_path: Path) -> None:
    sample = tmp_path / "big.bin"
    sample.write_bytes(b"MZ" + b"A" * 8190)  # 8192 bytes total
    out = tmp_path / "triage.json"

    run_script("static_triage.py", str(sample), "--max-read-bytes", "1024", "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["size_bytes"] == 8192
    assert payload["bytes_analyzed"] == 1024
    assert payload["bytes_analyzed"] < payload["size_bytes"]


def test_static_triage_rejects_non_positive_max_read_bytes(tmp_path: Path) -> None:
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"MZ" + b"A" * 128)
    out = tmp_path / "triage.json"

    result = run_script(
        "static_triage.py",
        str(sample),
        "--max-read-bytes",
        "-1",
        "--json-out",
        str(out),
        check=False,
    )

    assert result.returncode != 0
    assert not out.exists()
    assert "positive" in result.stderr.lower()


def test_repo_corpus_export_rejects_non_positive_max_file_bytes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    out = tmp_path / "corpus.jsonl"

    result = run_script(
        "repo_corpus_export.py",
        str(repo),
        "--jsonl-out",
        str(out),
        "--max-file-bytes",
        "-1",
        check=False,
    )

    assert result.returncode != 0
    assert not out.exists()
    assert "positive" in result.stderr.lower()


def test_repo_scanners_do_not_follow_symlinked_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "real.py").write_text("real = 1\n", encoding="utf-8")
    outside = tmp_path / "secret.txt"
    outside.write_text("TOP-SECRET-OUTSIDE\n", encoding="utf-8")
    link = repo / "leak.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted in this environment")

    out = tmp_path / "corpus.jsonl"
    run_script("repo_corpus_export.py", str(repo), "--jsonl-out", str(out))

    text = out.read_text(encoding="utf-8")
    assert "TOP-SECRET-OUTSIDE" not in text
    paths = {json.loads(line)["path"] for line in text.splitlines() if line.strip()}
    assert "leak.txt" not in paths


def test_ioc_extract_bounds_items_per_category(tmp_path: Path) -> None:
    evidence = tmp_path / "flood.txt"
    evidence.write_text(
        "\n".join(f"http://host{i}.example/path" for i in range(5000)) + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "iocs.json"

    run_script("ioc_extract.py", str(evidence), "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload.get("network", [])) <= 1000
    assert payload.get("truncated") is True


def test_ioc_extract_marks_truncated_for_overlong_lines(tmp_path: Path) -> None:
    evidence = tmp_path / "long-line.txt"
    evidence.write_text("A" * 20_000 + " http://late.example/path\n", encoding="utf-8")
    out = tmp_path / "iocs.json"

    run_script("ioc_extract.py", str(evidence), "--json-out", str(out), "--max-line-chars", "1024")

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload.get("truncated") is True
    assert "network" not in payload


def test_ioc_extract_does_not_mark_exact_cap_line_as_truncated(tmp_path: Path) -> None:
    evidence = tmp_path / "exact-line.txt"
    evidence.write_text("A" * 16, encoding="utf-8")
    out = tmp_path / "iocs.json"

    run_script("ioc_extract.py", str(evidence), "--json-out", str(out), "--max-line-chars", "16")

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload.get("truncated") is False


def test_android_api_scan_skips_oversized_files(tmp_path: Path) -> None:
    src = tmp_path / "Api.kt"
    src.write_text('val u = "https://api.example.test/v1/ping"\n' * 5, encoding="utf-8")
    out = tmp_path / "android.json"

    run_script("android_api_scan.py", str(tmp_path), "--max-file-bytes", "20", "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "Api.kt" in payload.get("skipped_files", [])
    assert payload["endpoints"] == []
    assert payload["base_urls"] == []


def test_repo_corpus_symbols_ignore_docstring_definitions(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "m.py").write_text(
        '"""\n'
        "def fake_in_docstring():\n"
        "    pass\n"
        '"""\n'
        "import real_module\n"
        "def real_fn():\n"
        "    pass\n",
        encoding="utf-8",
    )
    out = tmp_path / "c.jsonl"
    run_script("repo_corpus_export.py", str(repo), "--jsonl-out", str(out))

    record = next(
        json.loads(line)
        for line in out.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line)["path"] == "m.py"
    )
    assert "real_fn" in record["symbols"]
    assert "fake_in_docstring" not in record["symbols"]
    assert "real_module" in record["imports"]


def test_repo_map_python_imports_and_routes_use_ast(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "api.py").write_text(
        '"""\n'
        "import evil_in_docstring\n"
        '@app.get("/fake-route")\n'
        "def fake():\n"
        "    pass\n"
        '"""\n'
        "import real_dep\n"
        '@app.get("/real-route")\n'
        "def real():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    out = tmp_path / "map.json"
    run_script("repo_map.py", str(repo), "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    import_names = {name for entry in payload["imports"] for name in entry["imports"]}
    route_paths = {route["path"] for route in payload["routes"]}
    assert "real_dep" in import_names
    assert "evil_in_docstring" not in import_names
    assert "/real-route" in route_paths
    assert "/fake-route" not in route_paths
