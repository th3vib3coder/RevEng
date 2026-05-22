from __future__ import annotations

import json
import importlib.util
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


def load_script_module(script_name: str):
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(script_name.removesuffix(".py"), ROOT / "scripts" / script_name)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_tool_check_emits_python_and_tool_map() -> None:
    result = run_script("re_tool_check.py", "--json")
    payload = json.loads(result.stdout)
    assert payload["python"]["executable"]
    assert "strings" in payload["tools"]
    assert "jadx" in payload["tools"]
    assert payload["adapter_schema"] == "reveng.external_adapters.v1"
    assert "ghidra" in payload["adapters"]


def test_tool_check_reports_external_adapter_capabilities_without_invoking_tools() -> None:
    re_tool_check = load_script_module("re_tool_check.py")
    mapping = {
        "idac": "/fake/bin/idac",
        "analyzeHeadless": "/fake/ghidra/analyzeHeadless",
        "pyghidra": "/fake/bin/pyghidra",
        "r2mcp": "/fake/bin/r2mcp",
    }
    observed: list[str] = []

    def fake_which(name: str) -> str | None:
        observed.append(name)
        return mapping.get(name)

    payload = re_tool_check.check_tools(["idac", "analyzeHeadless", "r2mcp"], which=fake_which)
    adapters = payload["adapters"]
    assert payload["execution_policy"]["adapters_invoked"] is False
    assert adapters["idac"]["available"] is True
    assert adapters["idac"]["entrypoints"][0]["path"] == "/fake/bin/idac"
    assert {"read_only", "mutation_preview", "mutation_commit"}.issubset(set(adapters["idac"]["safety_classes"]))
    assert adapters["ghidra"]["available"] is True
    assert {item["name"] for item in adapters["ghidra"]["entrypoints"]} == {"analyzeHeadless", "pyghidra"}
    assert adapters["r2mcp"]["available"] is True
    assert adapters["binary-ninja-headless-mcp"]["available"] is False
    assert "idac" in observed
    assert "binary-ninja-headless-mcp" in observed


def test_tool_check_marks_raw_eval_adapters_as_pause_required() -> None:
    re_tool_check = load_script_module("re_tool_check.py")

    def fake_which(name: str) -> str | None:
        if name == "binary-ninja-headless-mcp":
            return "/fake/bin/binary-ninja-headless-mcp"
        return None

    payload = re_tool_check.check_tools([], which=fake_which)
    adapter = payload["adapters"]["binary-ninja-headless-mcp"]
    raw_eval = next(cap for cap in adapter["capabilities"] if cap["safety_class"] == "raw_eval")
    assert adapter["available"] is True
    assert raw_eval["requires_pause"] is True
    assert raw_eval["enabled_by_default"] is False
    assert adapter["invoked"] is False


def test_tool_check_missing_adapters_degrade_gracefully() -> None:
    re_tool_check = load_script_module("re_tool_check.py")

    payload = re_tool_check.check_tools(["idac"], which=lambda _name: None)

    assert payload["tools"]["idac"] is None
    assert all(adapter["available"] is False for adapter in payload["adapters"].values())
    assert payload["warnings"]



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


class FakeAddress:
    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value


class FakeBlock:
    def __init__(self, start: str, successors: list[str]) -> None:
        self.start = FakeAddress(start)
        self.successors = [FakeAddress(item) for item in successors]

    def getFirstStartAddress(self) -> FakeAddress:
        return self.start

    def getDestinations(self, _monitor: object | None = None) -> list[FakeAddress]:
        return self.successors


class FakeFunction:
    def __init__(self, name: str, entry: str, calls: list["FakeFunction"] | None = None, blocks: list[FakeBlock] | None = None) -> None:
        self.name = name
        self.entry = FakeAddress(entry)
        self.calls = calls or []
        self.blocks = blocks or []

    def getName(self) -> str:
        return self.name

    def getEntryPoint(self) -> FakeAddress:
        return self.entry

    def getCalledFunctions(self, _monitor: object | None = None) -> list["FakeFunction"]:
        return self.calls

    def getBasicBlocks(self) -> list[FakeBlock]:
        return self.blocks


class FakeListing:
    def __init__(self, functions: list[FakeFunction]) -> None:
        self.functions = functions

    def getFunctions(self, _forward: bool) -> list[FakeFunction]:
        return self.functions


class FakeCompilerSpec:
    def getCompilerSpecID(self) -> str:
        return "gcc"


class FakeProgram:
    def __init__(self, functions: list[FakeFunction]) -> None:
        self.functions = functions

    def getName(self) -> str:
        return "fake.bin"

    def getLanguageID(self) -> str:
        return "x86:LE:64:default"

    def getCompilerSpec(self) -> FakeCompilerSpec:
        return FakeCompilerSpec()

    def getListing(self) -> FakeListing:
        return FakeListing(self.functions)

    def getSymbolTable(self) -> None:
        return None


def test_ghidra_summary_exports_fake_call_graph_cfg_and_text_summary() -> None:
    ghidra = load_script_module("ghidra_export_summary.py")
    helper = FakeFunction("helper", "0x2000")
    entry = FakeFunction(
        "entry",
        "0x1000",
        calls=[helper],
        blocks=[
            FakeBlock("0x1000", ["0x1010", "0x1020"]),
            FakeBlock("0x1010", ["0x1030"]),
            FakeBlock("0x1020", ["0x1030"]),
            FakeBlock("0x1030", []),
        ],
    )
    payload = ghidra.collect_summary(FakeProgram([entry, helper]))

    assert payload["call_graph"]["nodes"] == [
        {"entry": "0x1000", "name": "entry"},
        {"entry": "0x2000", "name": "helper"},
    ]
    assert payload["call_graph"]["edges"] == [{"from": "entry", "from_entry": "0x1000", "to": "helper", "to_entry": "0x2000"}]
    assert payload["xrefs"] == []
    assert any("xrefs unavailable" in item for item in payload["analysis_warnings"])
    cfg = payload["function_cfgs"][0]
    assert cfg["function"] == "entry"
    assert {"from": "0x1000", "to": "0x1010"} in cfg["edges"]
    assert any("CFG entry" in item for item in payload["graph_summaries"])
