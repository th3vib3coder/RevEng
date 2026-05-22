from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import repo_corpus_mcp as mcp  # noqa: E402


def sample_repo_graph() -> dict:
    return {
        "schema": "reveng.repo_graph.v1",
        "nodes": [
            {"id": "file:pkg/cli.py", "kind": "file", "label": "pkg/cli.py", "path": "pkg/cli.py"},
            {"id": "module:pkg.cli", "kind": "module", "label": "pkg.cli", "path": "pkg/cli.py"},
            {"id": "symbol:pkg/cli.py#main", "kind": "symbol", "label": "main", "path": "pkg/cli.py"},
            {"id": "module:pkg.helpers", "kind": "module", "label": "pkg.helpers", "path": "pkg/helpers.py"},
            {"id": "dependency:python:requests>=2", "kind": "dependency", "label": "requests>=2"},
        ],
        "edges": [
            {
                "id": "edge:file_represents_module:file:pkg/cli.py->module:pkg.cli",
                "from": "file:pkg/cli.py",
                "to": "module:pkg.cli",
                "kind": "file_represents_module",
                "evidence": [{"source": "pkg/cli.py"}],
            },
            {
                "id": "edge:file_defines_symbol:file:pkg/cli.py->symbol:pkg/cli.py#main",
                "from": "file:pkg/cli.py",
                "to": "symbol:pkg/cli.py#main",
                "kind": "file_defines_symbol",
                "evidence": [{"source": "pkg/cli.py"}],
            },
            {
                "id": "edge:module_imports_module:module:pkg.cli->module:pkg.helpers",
                "from": "module:pkg.cli",
                "to": "module:pkg.helpers",
                "kind": "module_imports_module",
                "evidence": [{"source": "pkg/cli.py"}],
            },
        ],
    }


def test_graph_node_tool_filters_by_kind_and_query() -> None:
    result = mcp.tool_list_graph_nodes(sample_repo_graph(), {"kind": "module", "query": "cli"})

    assert result["isError"] is False
    sc = result["structuredContent"]
    assert [node["id"] for node in sc["nodes"]] == ["module:pkg.cli"]
    assert sc["done"] is True
    assert sc["meta"] == {
        "case_id": None,
        "result_count": 1,
        "offset": 0,
        "next_offset": None,
        "truncated": False,
        "warnings": [],
    }


def test_graph_edge_tool_filters_by_kind_and_endpoint() -> None:
    result = mcp.tool_list_graph_edges(
        sample_repo_graph(),
        {"kind": "module_imports_module", "from": "module:pkg.cli"},
    )

    assert result["isError"] is False
    sc = result["structuredContent"]
    assert [edge["id"] for edge in sc["edges"]] == ["edge:module_imports_module:module:pkg.cli->module:pkg.helpers"]


def test_graph_neighbors_tool_returns_adjacent_edges_and_nodes() -> None:
    result = mcp.tool_graph_neighbors(sample_repo_graph(), {"node_id": "file:pkg/cli.py", "direction": "out"})

    assert result["isError"] is False
    sc = result["structuredContent"]
    assert {edge["to"] for edge in sc["edges"]} == {"module:pkg.cli", "symbol:pkg/cli.py#main"}
    assert {node["id"] for node in sc["nodes"]} == {"module:pkg.cli", "symbol:pkg/cli.py#main"}


def test_graph_tools_error_when_graph_unavailable() -> None:
    result = mcp.tool_list_graph_nodes(None, {})

    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "graph_unavailable"
    assert result["structuredContent"]["meta"]["truncated"] is False


def test_module_graph_tool_filters_dependencies() -> None:
    graph = {
        "edges": [
            {"from": "pkg.a", "to": "pkg.b", "import": "pkg.b"},
            {"from": "pkg.c", "to": "pkg.a", "import": "pkg.a"},
        ],
        "external_imports": [{"from": "pkg.a", "import": "requests"}],
        "metrics": {
            "fan_in": {"pkg.a": 1, "pkg.b": 1, "pkg.c": 0},
            "fan_out": {"pkg.a": 1, "pkg.b": 0, "pkg.c": 1},
            "cycles": [["pkg.a", "pkg.b"]],
        },
    }
    result = mcp.tool_module_graph(graph, {"module": "pkg.a", "direction": "dependencies"})
    assert result["isError"] is False
    sc = result["structuredContent"]
    edges = {(edge["from"], edge["to"]) for edge in sc["edges"]}
    assert ("pkg.a", "pkg.b") in edges
    assert ("pkg.c", "pkg.a") not in edges
    assert {item["import"] for item in sc["external_imports"]} == {"requests"}
    assert sc["metrics"]["fan_in"] == {"pkg.a": 1}
    assert sc["metrics"]["fan_out"] == {"pkg.a": 1}
    assert sc["metrics"]["cycles"] == [["pkg.a", "pkg.b"]]
    assert sc["metrics"]["truncated"] is False


def test_module_graph_tool_exposes_global_metrics_without_module_filter() -> None:
    graph = {
        "edges": [],
        "external_imports": [],
        "metrics": {
            "fan_in": {"pkg.a": 1, "pkg.b": 1},
            "fan_out": {"pkg.a": 1, "pkg.b": 1},
            "cycles": [["pkg.a", "pkg.b"]],
        },
    }
    result = mcp.tool_module_graph(graph, {})
    assert result["isError"] is False
    assert result["structuredContent"]["metrics"] == {
        "fan_in": {"pkg.a": 1, "pkg.b": 1},
        "fan_out": {"pkg.a": 1, "pkg.b": 1},
        "cycles": [["pkg.a", "pkg.b"]],
        "truncated": False,
    }


def test_module_graph_tool_caps_global_metrics() -> None:
    graph = {
        "edges": [],
        "external_imports": [],
        "metrics": {
            "fan_in": {f"pkg.{index:03d}": index for index in range(60)},
            "fan_out": {f"pkg.{index:03d}": index for index in range(60)},
            "cycles": [[f"pkg.{index:03d}", f"pkg.{index + 1:03d}"] for index in range(60)],
        },
    }
    result = mcp.tool_module_graph(graph, {"limit": 10})
    assert result["isError"] is False
    metrics = result["structuredContent"]["metrics"]
    assert len(metrics["fan_in"]) == 10
    assert len(metrics["fan_out"]) == 10
    assert len(metrics["cycles"]) == 10
    assert metrics["truncated"] is True


def test_module_graph_tool_errors_when_unavailable() -> None:
    result = mcp.tool_module_graph(None, {})
    assert result["isError"] is True
    assert result["structuredContent"]["error"]["code"] == "graph_unavailable"


def test_module_graph_over_stdio(tmp_path: Path) -> None:
    corpus = tmp_path / "c.jsonl"
    corpus.write_text(
        json.dumps(
            {
                "path": "pkg/cli.py",
                "kind": "source",
                "language": "Python",
                "symbols": ["main"],
                "imports": ["pkg.helpers"],
                "evidence": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    repo_map = tmp_path / "map.json"
    repo_map.write_text(
        json.dumps(
            {
                "module_graph": {
                    "edges": [{"from": "pkg.cli", "to": "pkg.helpers", "import": "pkg.helpers"}],
                    "external_imports": [{"from": "pkg.cli", "import": "requests"}],
                    "metrics": {
                        "fan_in": {"pkg.cli": 0, "pkg.helpers": 1},
                        "fan_out": {"pkg.cli": 1, "pkg.helpers": 0},
                        "cycles": [],
                    },
                },
                "graph": sample_repo_graph(),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "repo_corpus_mcp.py"), "--corpus", str(corpus), "--repo-map", str(repo_map)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "reveng.module_graph", "arguments": {"module": "pkg.cli", "direction": "dependencies"}},
        },
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "reveng.graph_neighbors", "arguments": {"node_id": "module:pkg.cli", "direction": "out"}},
        },
    ]
    out, _err = proc.communicate("\n".join(json.dumps(item) for item in requests) + "\n", timeout=20)

    responses = [json.loads(line) for line in out.splitlines() if line.strip()]
    call_response = next(message for message in responses if message.get("id") == 2)
    assert call_response["result"]["isError"] is False
    sc = call_response["result"]["structuredContent"]
    assert any(edge["to"] == "pkg.helpers" for edge in sc["edges"])
    assert sc["metrics"]["fan_out"] == {"pkg.cli": 1}
    assert sc["metrics"]["cycles"] == []
    assert sc["metrics"]["truncated"] is False
    neighbor_response = next(message for message in responses if message.get("id") == 3)
    assert neighbor_response["result"]["isError"] is False
    neighbor_sc = neighbor_response["result"]["structuredContent"]
    assert [edge["id"] for edge in neighbor_sc["edges"]] == ["edge:module_imports_module:module:pkg.cli->module:pkg.helpers"]
