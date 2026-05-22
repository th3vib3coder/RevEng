from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import repo_corpus_mcp as mcp  # noqa: E402


def test_module_graph_tool_filters_dependencies() -> None:
    graph = {
        "edges": [
            {"from": "pkg.a", "to": "pkg.b", "import": "pkg.b"},
            {"from": "pkg.c", "to": "pkg.a", "import": "pkg.a"},
        ],
        "external_imports": [{"from": "pkg.a", "import": "requests"}],
    }
    result = mcp.tool_module_graph(graph, {"module": "pkg.a", "direction": "dependencies"})
    assert result["isError"] is False
    sc = result["structuredContent"]
    edges = {(edge["from"], edge["to"]) for edge in sc["edges"]}
    assert ("pkg.a", "pkg.b") in edges
    assert ("pkg.c", "pkg.a") not in edges
    assert {item["import"] for item in sc["external_imports"]} == {"requests"}


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
                }
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
    ]
    out, _err = proc.communicate("\n".join(json.dumps(item) for item in requests) + "\n", timeout=20)

    responses = [json.loads(line) for line in out.splitlines() if line.strip()]
    call_response = next(message for message in responses if message.get("id") == 2)
    assert call_response["result"]["isError"] is False
    sc = call_response["result"]["structuredContent"]
    assert any(edge["to"] == "pkg.helpers" for edge in sc["edges"])
