from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"


class EvalFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvalFailure(message)


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
    require({"requests>=2", "pydantic>=2", "express"}.issubset(deps), f"missing dependencies: {deps}")
    require({"/items/{item_id}", "/health"}.issubset(routes), f"missing routes: {routes}")
    require(not {"/commented", "/block-comment", "/string-literal"} & routes, f"comment/string JS routes leaked: {routes}")
    require({"golden-cli", "test"}.issubset(entrypoints), f"missing entrypoints: {entrypoints}")
    require({".codex-plugin/plugin.json", ".claude-plugin/plugin.json"}.issubset(plugin_paths), "plugin surfaces missing")
    require("secret_pattern" in risks, "secret-like risk not detected")
    require(("pkg.cli", "pkg.helpers", "pkg.helpers") in graph_edges, f"missing internal Python module edge: {graph_edges}")
    require(("pkg.cli", "requests") in graph_external, f"missing external Python import: {graph_external}")
    metrics = repo_map["module_graph"]["metrics"]
    require(metrics["fan_out"].get("pkg.cli", 0) >= 1, f"module graph fan_out missing: {metrics['fan_out']}")
    require(metrics["fan_in"].get("pkg.helpers", 0) >= 1, f"module graph fan_in missing: {metrics['fan_in']}")
    require(metrics["cycles"] == [], f"unexpected import cycle in acyclic fixture: {metrics['cycles']}")
    repo_graph = repo_map["graph"]
    repo_graph_nodes = {item["id"] for item in repo_graph["nodes"]}
    repo_graph_edges = {item["id"] for item in repo_graph["edges"]}
    require(repo_graph["schema"] == "reveng.repo_graph.v1", "repo graph schema missing")
    require("file:pkg/cli.py" in repo_graph_nodes, "repo graph file node missing")
    require("module:pkg.cli" in repo_graph_nodes, "repo graph module node missing")
    require("symbol:pkg/cli.py#main" in repo_graph_nodes, "repo graph symbol node missing")
    require("route:GET:/items/{item_id}" in repo_graph_nodes, "repo graph FastAPI route node missing")
    require("edge:module_imports_module:module:pkg.cli->module:pkg.helpers" in repo_graph_edges, "repo graph module edge missing")
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

    return {
        "inventory_files": inventory["file_count"],
        "dependencies": sorted(deps),
        "routes": sorted(routes),
        "module_edges": len(graph_edges),
        "repo_graph_nodes": len(repo_graph_nodes),
        "repo_graph_edges": len(repo_graph_edges),
        "case_id": case_manifest["case_id"],
        "mcp_tools_checked": True,
        "corpus_records": len(corpus),
    }


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
    return {"size_bytes": triage["size_bytes"], "bytes_analyzed": triage["bytes_analyzed"]}


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
    return {"network_items": len(network), "truncated": iocs["truncated"]}


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
    return {"endpoints": len(android["endpoints"]), "skipped_files": android["skipped_files"]}


def run_cases(workdir: Path) -> tuple[list[dict[str, Any]], int]:
    cases: list[tuple[str, Callable[[Path], dict[str, Any]]]] = [
        ("repo_analysis", eval_repo_analysis),
        ("binary_triage", eval_binary_triage),
        ("ioc_extraction", eval_ioc_extraction),
        ("android_scan", eval_android_scan),
    ]
    results: list[dict[str, Any]] = []
    failures = 0
    for name, case in cases:
        case_dir = workdir / name
        case_dir.mkdir(parents=True, exist_ok=True)
        try:
            details = case(case_dir)
            results.append({"name": name, "status": "passed", "details": details})
        except Exception as exc:
            failures += 1
            results.append({"name": name, "status": "failed", "error": str(exc)})
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
    summary = {
        "status": "failed" if failures else "passed",
        "workdir": str(workdir),
        "passed": sum(1 for item in results if item["status"] == "passed"),
        "failed": failures,
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
