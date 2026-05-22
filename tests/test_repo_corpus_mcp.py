from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_script(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        text=True,
        capture_output=True,
        check=True,
    )


def make_corpus(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "cli.py").write_text(
        """
import requests
from pkg.helpers import format_value

def main():
    return format_value("ok")
""".lstrip(),
        encoding="utf-8",
    )
    (repo / "pkg" / "helpers.py").write_text(
        """
def format_value(value: str) -> str:
    return value.upper()
""".lstrip(),
        encoding="utf-8",
    )
    (repo / "README.md").write_text("# Fixture\n", encoding="utf-8")
    corpus = tmp_path / "repo_corpus.jsonl"
    run_script("repo_corpus_export.py", str(repo), "--jsonl-out", str(corpus))
    return corpus


class McpClient:
    def __init__(self, corpus: Path) -> None:
        self.process = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "repo_corpus_mcp.py"), "--corpus", str(corpus)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.next_id = 1

    def request(self, method: str, params: dict | None = None) -> dict:
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        request_id = self.next_id
        self.next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        assert line, "MCP server produced no response"
        response = json.loads(line)
        assert response["id"] == request_id
        return response

    def close(self) -> None:
        if self.process.stdin is not None:
            self.process.stdin.close()
        self.process.terminate()
        self.process.wait(timeout=5)


def test_repo_corpus_mcp_initialize_and_tools_list(tmp_path: Path) -> None:
    corpus = make_corpus(tmp_path)
    client = McpClient(corpus)
    try:
        init = client.request(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        )
        assert init["result"]["capabilities"]["tools"]["listChanged"] is False

        listed = client.request("tools/list")
        tool_names = [tool["name"] for tool in listed["result"]["tools"]]
        assert tool_names == sorted(tool_names)
        assert "reveng.search_corpus" in tool_names
        assert "reveng.get_record" in tool_names
        assert "reveng.graph_neighbors" in tool_names
        assert "reveng.list_graph_edges" in tool_names
        assert "reveng.list_graph_nodes" in tool_names
        assert "reveng.list_symbols" in tool_names
    finally:
        client.close()


def test_repo_corpus_mcp_search_returns_split_paginated_content(tmp_path: Path) -> None:
    corpus = make_corpus(tmp_path)
    client = McpClient(corpus)
    try:
        response = client.request(
            "tools/call",
            {
                "name": "reveng.search_corpus",
                "arguments": {"query": "format_value", "limit": 1},
            },
        )
        result = response["result"]
        assert result["isError"] is False
        assert result["content"][0]["type"] == "text"
        assert "match" in result["content"][0]["text"].lower()
        structured = result["structuredContent"]
        assert structured["records"][0]["path"] in {"pkg/cli.py", "pkg/helpers.py"}
        assert structured["nextCursor"]
        assert structured["done"] is False
        assert structured["meta"]["result_count"] == 1
        assert structured["meta"]["offset"] == 0
        assert structured["meta"]["next_offset"] == int(structured["nextCursor"])
        assert structured["meta"]["truncated"] is True
        assert structured["meta"]["warnings"] == []

        second = client.request(
            "tools/call",
            {
                "name": "reveng.search_corpus",
                "arguments": {"query": "format_value", "limit": 1, "cursor": structured["nextCursor"]},
            },
        )
        assert second["result"]["structuredContent"]["records"]
    finally:
        client.close()


def test_repo_corpus_mcp_get_record_and_symbol_lookup(tmp_path: Path) -> None:
    corpus = make_corpus(tmp_path)
    client = McpClient(corpus)
    try:
        record = client.request(
            "tools/call",
            {"name": "reveng.get_record", "arguments": {"path": "pkg/cli.py"}},
        )["result"]["structuredContent"]["record"]
        assert record["path"] == "pkg/cli.py"
        assert "main" in record["symbols"]

        symbols = client.request(
            "tools/call",
            {"name": "reveng.list_symbols", "arguments": {"query": "main"}},
        )["result"]["structuredContent"]["matches"]
        assert symbols[0]["path"] == "pkg/cli.py"
        assert symbols[0]["symbol"] == "main"
    finally:
        client.close()


def test_repo_corpus_mcp_schema_error_is_tool_visible(tmp_path: Path) -> None:
    corpus = make_corpus(tmp_path)
    client = McpClient(corpus)
    try:
        response = client.request(
            "tools/call",
            {"name": "reveng.search_corpus", "arguments": {"query": "x", "limit": 5000}},
        )
        result = response["result"]
        assert result["isError"] is True
        assert result["structuredContent"]["error"]["code"] == "invalid_arguments"
        assert "limit" in result["structuredContent"]["error"]["message"]
        assert result["structuredContent"]["meta"]["result_count"] == 0
        assert result["structuredContent"]["meta"]["warnings"]
    finally:
        client.close()


def test_repo_corpus_mcp_jsonrpc_batch_returns_response_array(tmp_path: Path) -> None:
    corpus = make_corpus(tmp_path)
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "repo_corpus_mcp.py"), "--corpus", str(corpus)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(
            json.dumps(
                [
                    {"jsonrpc": "2.0", "id": 1, "method": "ping"},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                ]
            )
            + "\n"
        )
        process.stdin.flush()
        response = json.loads(process.stdout.readline())
        assert isinstance(response, list)
        assert [item["id"] for item in response] == [1, 2]
        assert response[0]["result"] == {}
        assert response[1]["result"]["tools"]
    finally:
        if process.stdin is not None:
            process.stdin.close()
        process.terminate()
        process.wait(timeout=5)
