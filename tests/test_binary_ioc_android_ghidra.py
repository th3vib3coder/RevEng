from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_script(script: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        text=True,
        capture_output=True,
        check=check,
    )


def test_tool_check_emits_python_and_tool_map() -> None:
    result = run_script("re_tool_check.py", "--json")
    payload = json.loads(result.stdout)
    assert payload["python"]["executable"]
    assert "strings" in payload["tools"]
    assert "jadx" in payload["tools"]


def test_static_triage_reports_hashes_entropy_and_strings(tmp_path: Path) -> None:
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"MZ" + b"A" * 64 + b"https://example.test/path\x00")
    out = tmp_path / "triage.json"

    run_script("static_triage.py", str(sample), "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["file_type"] == "PE/DOS MZ"
    assert payload["hashes"]["sha256"]
    assert payload["entropy"]["overall"] >= 0
    assert "https://example.test/path" in "\n".join(payload["strings_summary"]["ascii_preview"])
    assert "not executed" in payload["limitations"][0]


def test_ioc_extract_preserves_evidence_and_normalizes_url(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.txt"
    evidence.write_text(
        "sha256: " + "a" * 64 + "\n"
        "callback hxxps://Bad[.]Example/path?q=1\n"
        "User-Agent: ExampleAgent/1.0\n",
        encoding="utf-8",
    )
    out = tmp_path / "iocs.json"

    run_script("ioc_extract.py", str(evidence), "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["hashes"][0]["value"] == "a" * 64
    network_values = {item["value"] for item in payload["network"]}
    assert "hxxps://Bad[.]Example/path?q=1" in network_values
    assert "https://bad.example/path?q=1" in network_values
    assert payload["user_agents"][0]["evidence_snippet"] == "User-Agent: ExampleAgent/1.0"


def test_ioc_extract_marks_version_like_ipv4_as_contextual(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("library version 1.2.3.4 released\n", encoding="utf-8")
    out = tmp_path / "iocs.json"

    run_script("ioc_extract.py", str(evidence), "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    item = payload["network"][0]
    assert item["kind"] == "ipv4"
    assert item["value"] == "1.2.3.4"
    assert item["confidence"] == "contextual"


def test_android_api_scan_detects_retrofit_okhttp_auth_and_base_url(tmp_path: Path) -> None:
    source = tmp_path / "ApiService.kt"
    source.write_text(
        '@GET("v1/users/{id}")\n'
        'suspend fun user(@Path("id") id: String): User\n'
        'val base = "https://api.example.test/"\n'
        'Request.Builder().url("https://api.example.test/v1/ping")\n'
        'builder.addHeader("Authorization", token)\n',
        encoding="utf-8",
    )
    out = tmp_path / "android_api.json"

    run_script("android_api_scan.py", str(tmp_path), "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "https://api.example.test/" in payload["base_urls"]
    paths = {item["path"] for item in payload["endpoints"]}
    assert "v1/users/{id}" in paths
    assert "https://api.example.test/v1/ping" in paths
    assert payload["auth_headers"]


def test_ghidra_export_summary_fails_cleanly_outside_ghidra(tmp_path: Path) -> None:
    out = tmp_path / "ghidra.json"
    result = run_script("ghidra_export_summary.py", "--json-out", str(out), check=False)
    assert result.returncode == 2
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "Ghidra" in payload["error"]
    assert payload["analysis_warnings"]
