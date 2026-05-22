from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
EVAL_SCHEMA = "reveng.golden_evals.v1"
METRIC_KEYS = ("assertions", "false_positives", "false_negatives", "missing_evidence", "unsafe_actions")


class EvalFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvalFailure(message)


def missing_count(expected: set[str], actual: set[str]) -> int:
    return len(expected - actual)


def unexpected_count(rejected: set[str], actual: set[str]) -> int:
    return len(rejected & actual)


def metrics(
    *,
    assertions: int,
    false_positives: int = 0,
    false_negatives: int = 0,
    missing_evidence: int = 0,
    unsafe_actions: int = 0,
) -> dict[str, int]:
    return {
        "assertions": assertions,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "missing_evidence": missing_evidence,
        "unsafe_actions": unsafe_actions,
    }


def assert_clean_metrics(case_metrics: dict[str, int], case_name: str) -> None:
    for key in ("false_positives", "false_negatives", "missing_evidence", "unsafe_actions"):
        require(case_metrics.get(key, 0) == 0, f"{case_name} reported {key}={case_metrics.get(key)}")


def eval_result(capability: str, details: dict[str, Any], case_metrics: dict[str, int]) -> dict[str, Any]:
    assert_clean_metrics(case_metrics, capability)
    return {"capability": capability, "metrics": case_metrics, "details": details}


def merge_metrics(items: list[dict[str, int]]) -> dict[str, int]:
    merged = {key: 0 for key in METRIC_KEYS}
    for item in items:
        for key in METRIC_KEYS:
            merged[key] += int(item.get(key, 0))
    return merged


def load_script_module(script_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(script_name.removesuffix(".py"), SCRIPT_DIR / script_name)
    if spec is None or spec.loader is None:
        raise EvalFailure(f"cannot load script module: {script_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_script(script: str, *args: str | Path) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT_DIR / script), *(str(arg) for arg in args)]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise EvalFailure(
            f"{script} failed with exit {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


class McpSession:
    def __init__(self, corpus: Path, repo_map: Path | None = None) -> None:
        command = [sys.executable, str(SCRIPT_DIR / "repo_corpus_mcp.py"), "--corpus", str(corpus)]
        if repo_map is not None:
            command.extend(["--repo-map", str(repo_map)])
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.next_id = 1

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.process.stdin is None or self.process.stdout is None:
            raise EvalFailure("MCP process stdio unavailable")
        request_id = self.next_id
        self.next_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise EvalFailure(f"MCP server produced no response; stderr={stderr}")
        response = json.loads(line)
        if response.get("id") != request_id:
            raise EvalFailure(f"MCP response id mismatch: {response}")
        return response

    def close(self) -> None:
        if self.process.stdin is not None:
            self.process.stdin.close()
        self.process.terminate()
        self.process.wait(timeout=5)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_repo_fixture(root: Path) -> Path:
    repo = root / "repo"
    write_text(
        repo / "pyproject.toml",
        """
[project]
name = "golden-repo"
dependencies = [
  "requests>=2",
  "pydantic>=2",
]

[project.scripts]
golden-cli = "pkg.cli:main"
""".strip()
        + "\n",
    )
    write_text(
        repo / "pkg" / "cli.py",
        """
'''
import smuggled_import
def smuggled_symbol():
    pass
'''
from fastapi import FastAPI
from pkg.helpers import format_value
import requests

app = FastAPI()

@app.get("/items/{item_id}")
def read_item(item_id: str):
    return {"item_id": item_id}

def main():
    return format_value("ok")
""".lstrip(),
    )
    write_text(
        repo / "pkg" / "helpers.py",
        """
def format_value(value: str) -> str:
    return value.upper()
""".lstrip(),
    )
    write_text(
        repo / "package.json",
        json.dumps(
            {
                "name": "golden-node",
                "main": "src/server.js",
                "scripts": {"test": "node --test"},
                "dependencies": {"express": "^4.18.0"},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    write_text(
        repo / "src" / "server.js",
        """
import { health } from "./util.js";
const express = require("express");
const app = express();
// app.get("/commented", (req, res) => res.send("no"));
/*
router.post("/block-comment", handler);
*/
const fake = "router.delete('/string-literal', handler)";
app.get("/health", (req, res) => res.send("ok"));
module.exports = app;
""".lstrip(),
    )
    write_text(
        repo / "src" / "util.js",
        """
// import ignored from "./comment-only.js";
export function health() {
  return "ok";
}
""".lstrip(),
    )
    write_text(repo / ".codex-plugin" / "plugin.json", '{"name":"golden"}\n')
    write_text(repo / ".claude-plugin" / "plugin.json", '{"name":"golden"}\n')
    write_text(repo / ".github" / "workflows" / "ci.yml", "name: ci\n")
    write_text(repo / ".env.example", "API_KEY=example\n")
    write_text(repo / "node_modules" / "ignored.js", "throw new Error('must be ignored')\n")
    return repo


def eval_repo_analysis(workdir: Path) -> dict[str, Any]:
    repo = make_repo_fixture(workdir)
    out_dir = workdir / "repo-out"
    inventory_out = out_dir / "repo_inventory.json"
    map_out = out_dir / "repo_map.json"
    corpus_out = out_dir / "repo_corpus.jsonl"
    manifest_out = out_dir / "case_manifest.json"

    run_script("repo_inventory.py", repo, "--json-out", inventory_out)
    run_script("repo_map.py", repo, "--json-out", map_out)
    run_script("repo_corpus_export.py", repo, "--repo-map", map_out, "--jsonl-out", corpus_out)
    run_script(
        "case_manifest.py",
        "--case-dir",
        out_dir,
        "--target",
        repo,
        "--artifact",
        f"repo_inventory={inventory_out}",
        "--artifact",
        f"repo_map={map_out}",
        "--artifact",
        f"repo_corpus={corpus_out}",
        "--cap",
        "repo_corpus_max_file_bytes=500000",
        "--json-out",
        manifest_out,
    )

    inventory = read_json(inventory_out)
    repo_map = read_json(map_out)
    case_manifest = read_json(manifest_out)
    corpus = read_jsonl(corpus_out)

    manifest_paths = {item["path"] for item in inventory["manifests"]}
    require("generated_at" not in inventory, "repo_inventory must be deterministic by default")
    require("node_modules/ignored.js" not in {item["path"] for item in inventory["files"]}, "ignored dirs leaked into inventory")
    require("pyproject.toml" in manifest_paths, "pyproject manifest not detected")
    require(".codex-plugin/plugin.json" in manifest_paths, "Codex plugin manifest not detected")
    require(".claude-plugin/plugin.json" in manifest_paths, "Claude plugin manifest not detected")
    require(inventory["languages"]["Python"]["files"] >= 1, "Python language count missing")
    require(inventory["languages"]["JavaScript"]["files"] >= 1, "JavaScript language count missing")
    require(case_manifest["schema"] == "reveng.case_manifest.v1", "case manifest schema missing")
    require(case_manifest["target"]["content_sha256"], "case manifest target content hash missing")
    require(case_manifest["safety"]["executed_target_code"] is False, "case manifest must preserve static-first boundary")
    require(
        {item["name"] for item in case_manifest["artifacts"]} == {"repo_inventory", "repo_map", "repo_corpus"},
        "case manifest did not index all repo artifacts",
    )

    deps = {item["name"] for item in repo_map["dependencies"]}
    routes = {item["path"] for item in repo_map["routes"]}
    entrypoints = {item["name"] for item in repo_map["entrypoints"]}
    plugin_paths = {item["path"] for item in repo_map["plugins"]}
    risks = {item["kind"] for item in repo_map["risks"]}
    graph_edges = {(item["from"], item["to"], item["import"]) for item in repo_map["module_graph"]["edges"]}
    graph_external = {(item["from"], item["import"]) for item in repo_map["module_graph"]["external_imports"]}
    expected_deps = {"requests>=2", "pydantic>=2", "express"}
    expected_routes = {"/items/{item_id}", "/health"}
    rejected_routes = {"/commented", "/block-comment", "/string-literal"}
    expected_entrypoints = {"golden-cli", "test"}
    require(expected_deps.issubset(deps), f"missing dependencies: {deps}")
    require(expected_routes.issubset(routes), f"missing routes: {routes}")
    require(not rejected_routes & routes, f"comment/string JS routes leaked: {routes}")
    require(expected_entrypoints.issubset(entrypoints), f"missing entrypoints: {entrypoints}")
    require({".codex-plugin/plugin.json", ".claude-plugin/plugin.json"}.issubset(plugin_paths), "plugin surfaces missing")
    require("secret_pattern" in risks, "secret-like risk not detected")
    require(("pkg.cli", "pkg.helpers", "pkg.helpers") in graph_edges, f"missing internal Python module edge: {graph_edges}")
    require(("src.server", "src.util", "./util.js") in graph_edges, f"missing internal JavaScript module edge: {graph_edges}")
    require(("pkg.cli", "requests") in graph_external, f"missing external Python import: {graph_external}")
    require(("src.server", "express") in graph_external, f"missing external JavaScript import: {graph_external}")
    require(("src.util", "./comment-only.js") not in graph_external, f"comment-only JavaScript import leaked: {graph_external}")
    module_metrics = repo_map["module_graph"]["metrics"]
    require(module_metrics["fan_out"].get("pkg.cli", 0) >= 1, f"module graph fan_out missing: {module_metrics['fan_out']}")
    require(module_metrics["fan_in"].get("pkg.helpers", 0) >= 1, f"module graph fan_in missing: {module_metrics['fan_in']}")
    require(module_metrics["cycles"] == [], f"unexpected import cycle in acyclic fixture: {module_metrics['cycles']}")
    repo_graph = repo_map["graph"]
    repo_graph_nodes = {item["id"] for item in repo_graph["nodes"]}
    repo_graph_edges = {item["id"] for item in repo_graph["edges"]}
    require(repo_graph["schema"] == "reveng.repo_graph.v1", "repo graph schema missing")
    require("file:pkg/cli.py" in repo_graph_nodes, "repo graph file node missing")
    require("module:pkg.cli" in repo_graph_nodes, "repo graph module node missing")
    require("symbol:pkg/cli.py#main" in repo_graph_nodes, "repo graph symbol node missing")
    require("route:GET:/items/{item_id}" in repo_graph_nodes, "repo graph FastAPI route node missing")
    require("edge:module_imports_module:module:pkg.cli->module:pkg.helpers" in repo_graph_edges, "repo graph module edge missing")
    require("edge:module_imports_module:module:src.server->module:src.util" in repo_graph_edges, "repo graph JavaScript module edge missing")
    require("edge:file_defines_symbol:file:pkg/cli.py->symbol:pkg/cli.py#main" in repo_graph_edges, "repo graph symbol edge missing")
    require(
        "edge:route_bound_to_symbol:route:GET:/items/{item_id}->symbol:pkg/cli.py#read_item" in repo_graph_edges,
        "repo graph route-to-handler edge missing",
    )

    records = {record["path"]: record for record in corpus}
    require("pkg/cli.py" in records, "Python source missing from corpus")
    require("src/server.js" in records, "JS source missing from corpus")
    cli_hash = hashlib.sha256((repo / "pkg" / "cli.py").read_bytes()).hexdigest()
    require(records["pkg/cli.py"]["sha256"] == cli_hash, "corpus hash mismatch")
    require("main" in records["pkg/cli.py"]["symbols"], "Python symbol missing from corpus")
    require("requests" in records["pkg/cli.py"]["imports"], "Python import missing from corpus")
    require("smuggled_symbol" not in records["pkg/cli.py"]["symbols"], "AST symbols leaked a docstring def")
    require("smuggled_import" not in records["pkg/cli.py"]["imports"], "AST imports leaked a docstring import")
    graph_refs = records["pkg/cli.py"]["graph_refs"]
    require("file:pkg/cli.py" in graph_refs["nodes"], "corpus graph_refs file node missing")
    require("module:pkg.cli" in graph_refs["nodes"], "corpus graph_refs module node missing")
    require("symbol:pkg/cli.py#main" in graph_refs["nodes"], "corpus graph_refs symbol node missing")
    require("edge:file_defines_symbol:file:pkg/cli.py->symbol:pkg/cli.py#main" in graph_refs["edges"], "corpus graph_refs symbol edge missing")

    mcp = McpSession(corpus_out, map_out)
    try:
        init = mcp.request("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "golden", "version": "0"}})
        require(init["result"]["capabilities"]["tools"]["listChanged"] is False, "MCP initialize did not expose tools capability")
        search = mcp.request(
            "tools/call",
            {"name": "reveng.search_corpus", "arguments": {"query": "format_value", "limit": 1}},
        )["result"]
        require(search["isError"] is False, "MCP corpus search returned error")
        require(search["structuredContent"]["records"], "MCP corpus search returned no records")
        require(search["structuredContent"]["nextCursor"], "MCP corpus search did not paginate at limit=1")
        record = mcp.request(
            "tools/call",
            {"name": "reveng.get_record", "arguments": {"path": "pkg/cli.py"}},
        )["result"]["structuredContent"]["record"]
        require(record["path"] == "pkg/cli.py", "MCP get_record returned wrong path")
        schema_error = mcp.request(
            "tools/call",
            {"name": "reveng.search_corpus", "arguments": {"query": "x", "limit": 5000}},
        )["result"]
        require(schema_error["isError"] is True, "MCP invalid arguments were not tool-visible errors")
        graph = mcp.request(
            "tools/call",
            {"name": "reveng.module_graph", "arguments": {"module": "pkg.cli", "direction": "dependencies"}},
        )["result"]
        require(graph["isError"] is False, "MCP module_graph returned error")
        graph_metrics = graph["structuredContent"]["metrics"]
        require(graph_metrics["fan_out"] == {"pkg.cli": 1}, f"MCP module_graph fan_out missing: {graph_metrics}")
        require(graph_metrics["fan_in"] == {"pkg.cli": 0}, f"MCP module_graph fan_in missing: {graph_metrics}")
        require(graph_metrics["cycles"] == [], f"MCP module_graph cycles unexpected: {graph_metrics}")
        require(graph_metrics["truncated"] is False, f"MCP module_graph metrics unexpectedly truncated: {graph_metrics}")
        graph_nodes = mcp.request(
            "tools/call",
            {"name": "reveng.list_graph_nodes", "arguments": {"kind": "module", "query": "pkg.cli"}},
        )["result"]
        require(graph_nodes["isError"] is False, "MCP list_graph_nodes returned error")
        require(
            [item["id"] for item in graph_nodes["structuredContent"]["nodes"]] == ["module:pkg.cli"],
            f"MCP list_graph_nodes did not filter module node: {graph_nodes}",
        )
        graph_edges_mcp = mcp.request(
            "tools/call",
            {"name": "reveng.list_graph_edges", "arguments": {"kind": "module_imports_module", "from": "module:pkg.cli"}},
        )["result"]
        require(graph_edges_mcp["isError"] is False, "MCP list_graph_edges returned error")
        require(
            "edge:module_imports_module:module:pkg.cli->module:pkg.helpers"
            in {item["id"] for item in graph_edges_mcp["structuredContent"]["edges"]},
            f"MCP list_graph_edges missing module edge: {graph_edges_mcp}",
        )
        graph_neighbors = mcp.request(
            "tools/call",
            {"name": "reveng.graph_neighbors", "arguments": {"node_id": "module:pkg.cli", "direction": "out"}},
        )["result"]
        require(graph_neighbors["isError"] is False, "MCP graph_neighbors returned error")
        require(
            "module:pkg.helpers" in {item["id"] for item in graph_neighbors["structuredContent"]["nodes"]},
            f"MCP graph_neighbors missing adjacent module: {graph_neighbors}",
        )
    finally:
        mcp.close()

    required_graph_nodes = {
        "file:pkg/cli.py",
        "module:pkg.cli",
        "symbol:pkg/cli.py#main",
        "route:GET:/items/{item_id}",
    }
    required_graph_edges = {
        "edge:module_imports_module:module:pkg.cli->module:pkg.helpers",
        "edge:file_defines_symbol:file:pkg/cli.py->symbol:pkg/cli.py#main",
        "edge:route_bound_to_symbol:route:GET:/items/{item_id}->symbol:pkg/cli.py#read_item",
    }
    missing_evidence = missing_count({"file:pkg/cli.py", "module:pkg.cli", "symbol:pkg/cli.py#main"}, set(graph_refs["nodes"]))
    missing_evidence += missing_count(
        {"edge:file_defines_symbol:file:pkg/cli.py->symbol:pkg/cli.py#main"},
        set(graph_refs["edges"]),
    )
    repo_metrics = metrics(
        assertions=53,
        false_positives=unexpected_count(rejected_routes, routes),
        false_negatives=(
            missing_count(expected_deps, deps)
            + missing_count(expected_routes, routes)
            + missing_count(expected_entrypoints, entrypoints)
            + missing_count(required_graph_nodes, repo_graph_nodes)
            + missing_count(required_graph_edges, repo_graph_edges)
        ),
        missing_evidence=missing_evidence,
        unsafe_actions=0 if case_manifest["safety"]["executed_target_code"] is False else 1,
    )

    return eval_result(
        "source repository graph/corpus/MCP analysis",
        {
            "inventory_files": inventory["file_count"],
            "dependencies": sorted(deps),
            "routes": sorted(routes),
            "module_edges": len(graph_edges),
            "repo_graph_nodes": len(repo_graph_nodes),
            "repo_graph_edges": len(repo_graph_edges),
            "case_id": case_manifest["case_id"],
            "mcp_tools_checked": True,
            "corpus_records": len(corpus),
        },
        repo_metrics,
    )


def eval_binary_triage(workdir: Path) -> dict[str, Any]:
    sample = workdir / "sample.bin"
    payload = b"MZ" + b"A" * 4094 + b"https://golden.example/ping\x00" + b"B" * 4096
    sample.write_bytes(payload)
    out = workdir / "triage.json"

    run_script("static_triage.py", sample, "--max-read-bytes", "1024", "--json-out", out)
    triage = read_json(out)

    require(triage["file_type"] == "PE/DOS MZ", "binary type guess failed")
    require(triage["size_bytes"] == len(payload), "true binary size not reported")
    require(triage["bytes_analyzed"] == 1024, "bounded bytes_analyzed not honored")
    require(triage["hashes"]["sha256"] == hashlib.sha256(payload).hexdigest(), "streamed sha256 mismatch")
    require(any("Only the first" in item for item in triage["limitations"]), "truncation limitation missing")
    binary_metrics = metrics(
        assertions=5,
        false_negatives=0 if triage["file_type"] == "PE/DOS MZ" else 1,
        missing_evidence=0 if triage["hashes"]["sha256"] else 1,
        unsafe_actions=0,
    )
    return eval_result(
        "bounded binary triage",
        {"size_bytes": triage["size_bytes"], "bytes_analyzed": triage["bytes_analyzed"]},
        binary_metrics,
    )


def eval_ioc_extraction(workdir: Path) -> dict[str, Any]:
    evidence = workdir / "evidence.txt"
    evidence.write_text(
        "sha256: " + "a" * 64 + "\n"
        "callback hxxps://Bad[.]Example/path?q=1\n"
        "library version 1.2.3.4 released\n"
        + ("X" * 20_000)
        + " http://too-late.example/path\n",
        encoding="utf-8",
    )
    out = workdir / "iocs.json"

    run_script("ioc_extract.py", evidence, "--max-line-chars", "1024", "--json-out", out)
    iocs = read_json(out)

    network = iocs.get("network", [])
    network_values = {item["value"] for item in network}
    version_ips = [item for item in network if item["value"] == "1.2.3.4"]
    require(iocs.get("truncated") is True, "overlong IOC evidence did not mark truncated")
    require("hxxps://Bad[.]Example/path?q=1" in network_values, "defanged URL missing")
    require("https://bad.example/path?q=1" in network_values, "normalized URL missing")
    require(version_ips and version_ips[0]["confidence"] == "contextual", "version-like IPv4 not contextual")
    require("http://too-late.example/path" not in network_values, "overlong-line suffix was scanned past cap")
    ioc_metrics = metrics(
        assertions=5,
        false_positives=1 if "http://too-late.example/path" in network_values else 0,
        false_negatives=missing_count({"hxxps://Bad[.]Example/path?q=1", "https://bad.example/path?q=1"}, network_values),
        missing_evidence=0 if all(item.get("evidence_snippet") for item in network) else 1,
        unsafe_actions=0,
    )
    return eval_result("IOC extraction adversarial strings", {"network_items": len(network), "truncated": iocs["truncated"]}, ioc_metrics)


def eval_android_scan(workdir: Path) -> dict[str, Any]:
    source_root = workdir / "android-src"
    write_text(
        source_root / "ApiService.kt",
        '@GET("v1/users/{id}")\n'
        'suspend fun user(@Path("id") id: String): User\n'
        'val base = "https://api.golden.example/"\n'
        'Request.Builder().url("https://api.golden.example/v1/ping")\n'
        'builder.addHeader("Authorization", token)\n',
    )
    write_text(source_root / "Huge.kt", "val url = \"https://skip.example\"\n" * 100)
    out = workdir / "android.json"

    run_script("android_api_scan.py", source_root, "--max-file-bytes", "1024", "--json-out", out)
    android = read_json(out)

    endpoint_paths = {item["path"] for item in android["endpoints"]}
    require("https://api.golden.example/" in android["base_urls"], "Android base URL missing")
    require("v1/users/{id}" in endpoint_paths, "Retrofit endpoint missing")
    require("https://api.golden.example/v1/ping" in endpoint_paths, "OkHttp endpoint missing")
    require("Huge.kt" in android["skipped_files"], "oversized Android file not skipped")
    require(android["auth_headers"], "auth header evidence missing")
    android_metrics = metrics(
        assertions=4,
        false_positives=1 if "https://skip.example" in endpoint_paths else 0,
        false_negatives=missing_count({"v1/users/{id}", "https://api.golden.example/v1/ping"}, endpoint_paths),
        missing_evidence=0 if android["auth_headers"] else 1,
        unsafe_actions=0,
    )
    return eval_result(
        "Android static API scan",
        {"endpoints": len(android["endpoints"]), "skipped_files": android["skipped_files"]},
        android_metrics,
    )


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


class FakeGhidraProgram:
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


def eval_ghidra_fake_graph_export(workdir: Path) -> dict[str, Any]:
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

    payload = ghidra.collect_summary(FakeGhidraProgram([entry, helper]))
    out = workdir / "ghidra_summary.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    call_edges = {(item["from"], item["to"]) for item in payload["call_graph"]["edges"]}
    cfg_edges = {(item["from"], item["to"]) for item in payload["function_cfgs"][0]["edges"]}
    require(("entry", "helper") in call_edges, f"fake Ghidra call edge missing: {call_edges}")
    require(("0x1000", "0x1010") in cfg_edges, f"fake Ghidra CFG edge missing: {cfg_edges}")
    require(payload["graph_summaries"], "fake Ghidra graph summaries missing")
    require(any("xrefs unavailable" in item for item in payload["analysis_warnings"]), "xrefs warning missing")

    ghidra_metrics = metrics(
        assertions=4,
        false_negatives=missing_count({"entry->helper"}, {f"{source}->{target}" for source, target in call_edges}),
        missing_evidence=0 if payload["graph_summaries"] else 1,
        unsafe_actions=0,
    )
    return eval_result(
        "Ghidra fake graph export",
        {
            "functions": len(payload["functions"]),
            "call_edges": len(payload["call_graph"]["edges"]),
            "cfgs": len(payload["function_cfgs"]),
            "artifact": str(out),
        },
        ghidra_metrics,
    )


def eval_safety_prompt_contract(workdir: Path) -> dict[str, Any]:
    files = [
        ROOT / "skills" / "repo-reverse-engineering" / "SKILL.md",
        ROOT / "skills" / "binary-triage" / "SKILL.md",
        ROOT / "references" / "report-templates.md",
        ROOT / "references" / "external-adapter-schema.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    required_terms = {"PAUSE", "static-first", "Negative Evidence", "Alternate Hypotheses", "raw_eval"}
    present = {term for term in required_terms if term in combined}
    require(required_terms.issubset(present), f"safety/reporting terms missing: {required_terms - present}")

    prompt_metrics = metrics(
        assertions=len(required_terms),
        false_negatives=missing_count(required_terms, present),
        missing_evidence=0,
        unsafe_actions=0,
    )
    return eval_result(
        "OCP safety and reporting prompt contract",
        {"checked_files": [str(path.relative_to(ROOT)) for path in files], "required_terms": sorted(required_terms)},
        prompt_metrics,
    )


def run_cases(workdir: Path) -> tuple[list[dict[str, Any]], int]:
    cases: list[tuple[str, Callable[[Path], dict[str, Any]]]] = [
        ("repo_analysis", eval_repo_analysis),
        ("binary_triage", eval_binary_triage),
        ("ioc_extraction", eval_ioc_extraction),
        ("android_scan", eval_android_scan),
        ("ghidra_fake_graph_export", eval_ghidra_fake_graph_export),
        ("ocp_safety_prompt_contract", eval_safety_prompt_contract),
    ]
    results: list[dict[str, Any]] = []
    failures = 0
    for name, case in cases:
        case_dir = workdir / name
        case_dir.mkdir(parents=True, exist_ok=True)
        try:
            payload = case(case_dir)
            results.append(
                {
                    "name": name,
                    "status": "passed",
                    "capability": payload["capability"],
                    "metrics": payload["metrics"],
                    "details": payload["details"],
                }
            )
        except Exception as exc:
            failures += 1
            results.append(
                {
                    "name": name,
                    "status": "failed",
                    "capability": name,
                    "metrics": metrics(assertions=0, false_negatives=1),
                    "error": str(exc),
                }
            )
    return results, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Run end-to-end golden evaluations for RevEng")
    parser.add_argument("--workdir", help="Directory for generated eval fixtures and outputs; defaults to a temp dir")
    parser.add_argument("--json-out", help="Write eval summary JSON to this path")
    parser.add_argument("--keep", action="store_true", help="Keep the generated temporary workdir")
    args = parser.parse_args()

    if args.workdir:
        workdir = Path(args.workdir).resolve()
        workdir.mkdir(parents=True, exist_ok=True)
        if any(workdir.iterdir()):
            raise SystemExit(f"--workdir must be empty so eval fixtures cannot overwrite existing files: {workdir}")
    else:
        workdir = Path(tempfile.mkdtemp(prefix="reveng-golden-"))

    results, failures = run_cases(workdir)
    summary_metrics = merge_metrics([item["metrics"] for item in results])
    summary = {
        "schema": EVAL_SCHEMA,
        "status": "failed" if failures else "passed",
        "workdir": str(workdir),
        "passed": sum(1 for item in results if item["status"] == "passed"),
        "failed": failures,
        "metrics": summary_metrics,
        "cases": results,
    }

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))

    if not args.keep and not args.workdir:
        shutil.rmtree(workdir, ignore_errors=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
