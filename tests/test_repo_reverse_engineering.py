from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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


def make_fixture(tmp_path: Path) -> Path:
    repo = tmp_path / "fixture-repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    (repo / ".codex-plugin").mkdir()
    (repo / ".claude-plugin").mkdir()
    (repo / ".github" / "workflows").mkdir(parents=True)

    (repo / "pyproject.toml").write_text(
        """
[project]
name = "fixture"
dependencies = ["requests>=2"]

[project.scripts]
fixture-cli = "pkg.cli:main"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (repo / "pkg" / "cli.py").write_text(
        """
from fastapi import FastAPI
from pkg.helpers import format_value
import requests

app = FastAPI()

class Runner:
    pass

@app.get("/items/{item_id}")
def read_item(item_id: str):
    return {"item_id": item_id}

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
    (repo / "pkg" / "feature.py").write_text(
        """
from .helpers import format_value

def feature():
    return format_value("feature")
""".lstrip(),
        encoding="utf-8",
    )
    (repo / "tests" / "test_cli.py").write_text("from pkg.cli import main\n", encoding="utf-8")
    (repo / "package.json").write_text(
        json.dumps(
            {
                "name": "fixture-node",
                "main": "src/server.js",
                "scripts": {"test": "node --test"},
                "dependencies": {"express": "^4.18.0"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (repo / "src" / "server.js").write_text(
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
        encoding="utf-8",
    )
    (repo / "src" / "util.js").write_text(
        """
// import ignored from "./comment-only.js";
const doc = `
import hidden from "./template-only.js";
`;
export function health() {
  return "ok";
}
""".lstrip(),
        encoding="utf-8",
    )
    (repo / ".codex-plugin" / "plugin.json").write_text('{"name":"fixture"}\n', encoding="utf-8")
    (repo / ".claude-plugin" / "plugin.json").write_text('{"name":"fixture"}\n', encoding="utf-8")
    (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    return repo


def run_script(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        text=True,
        capture_output=True,
        check=True,
    )


def test_repo_inventory_detects_languages_manifests_and_plugins(tmp_path: Path) -> None:
    repo = make_fixture(tmp_path)
    out = tmp_path / "repo_inventory.json"

    run_script("repo_inventory.py", str(repo), "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["file_count"] >= 8
    assert payload["languages"]["Python"]["files"] == 4
    assert payload["languages"]["JavaScript"]["files"] == 2
    manifest_paths = {item["path"] for item in payload["manifests"]}
    assert "pyproject.toml" in manifest_paths
    assert "package.json" in manifest_paths
    assert ".codex-plugin/plugin.json" in manifest_paths
    assert ".claude-plugin/plugin.json" in manifest_paths


def test_repo_map_extracts_entrypoints_dependencies_routes_and_plugin_surfaces(tmp_path: Path) -> None:
    repo = make_fixture(tmp_path)
    out = tmp_path / "repo_map.json"

    run_script("repo_map.py", str(repo), "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    entrypoint_names = {item["name"] for item in payload["entrypoints"]}
    dependency_names = {item["name"] for item in payload["dependencies"]}
    route_paths = {item["path"] for item in payload["routes"]}
    plugin_paths = {item["path"] for item in payload["plugins"]}
    assert "fixture-cli" in entrypoint_names
    assert "test" in entrypoint_names
    assert "requests>=2" in dependency_names
    assert "express" in dependency_names
    assert "/health" in route_paths
    assert "/items/{item_id}" in route_paths
    assert "/commented" not in route_paths
    assert "/block-comment" not in route_paths
    assert "/string-literal" not in route_paths
    assert ".codex-plugin/plugin.json" in plugin_paths
    assert ".claude-plugin/plugin.json" in plugin_paths
    assert payload["limitations"]


def test_repo_map_builds_internal_python_module_graph(tmp_path: Path) -> None:
    repo = make_fixture(tmp_path)
    out = tmp_path / "repo_map.json"

    run_script("repo_map.py", str(repo), "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    graph = payload["module_graph"]
    modules = {item["module"]: item["path"] for item in graph["modules"]}
    edges = {(item["from"], item["to"], item["import"]) for item in graph["edges"]}
    external_imports = {(item["from"], item["import"]) for item in graph["external_imports"]}
    assert modules["pkg.cli"] == "pkg/cli.py"
    assert modules["pkg.helpers"] == "pkg/helpers.py"
    assert ("pkg.cli", "pkg.helpers", "pkg.helpers") in edges
    assert ("pkg.feature", "pkg.helpers", ".helpers") in edges
    assert ("pkg.cli", "requests") in external_imports
    assert not any(edge[2] == "requests" for edge in edges)


def test_repo_map_resolves_python_src_layout_import_names(tmp_path: Path) -> None:
    repo = tmp_path / "src-layout-repo"
    (repo / "src" / "re_agent" / "backend").mkdir(parents=True)
    (repo / "src" / "re_agent" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "src" / "re_agent" / "backend" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        """
[project]
name = "src-layout-fixture"

[tool.setuptools.packages.find]
where = ["src"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (repo / "src" / "re_agent" / "backend" / "protocol.py").write_text(
        "class BackendProtocol:\n    pass\n",
        encoding="utf-8",
    )
    (repo / "src" / "re_agent" / "backend" / "registry.py").write_text(
        "from re_agent.backend.protocol import BackendProtocol\n\nREGISTRY = {}\n",
        encoding="utf-8",
    )
    out = tmp_path / "repo_map.json"

    run_script("repo_map.py", str(repo), "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    graph = payload["module_graph"]
    modules = {item["module"]: item["path"] for item in graph["modules"]}
    edges = {(item["from"], item["to"], item["import"]) for item in graph["edges"]}
    external_imports = {(item["from"], item["import"]) for item in graph["external_imports"]}

    assert "re_agent.backend.registry" in modules
    assert "src.re_agent.backend.registry" not in modules
    assert modules["re_agent.backend.registry"] == "src/re_agent/backend/registry.py"
    assert (
        "re_agent.backend.registry",
        "re_agent.backend.protocol",
        "re_agent.backend.protocol",
    ) in edges
    assert ("re_agent.backend.registry", "re_agent.backend.protocol") not in external_imports


def test_repo_map_resolves_top_level_scripts_dir_imports(tmp_path: Path) -> None:
    repo = tmp_path / "script-root-repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname = \"script-root-fixture\"\n", encoding="utf-8")
    (repo / "scripts" / "repo_common.py").write_text(
        "def helper():\n    return 1\n",
        encoding="utf-8",
    )
    (repo / "scripts" / "repo_map.py").write_text(
        "from repo_common import helper\n\n\ndef main():\n    return helper()\n",
        encoding="utf-8",
    )
    out = tmp_path / "repo_map.json"

    run_script("repo_map.py", str(repo), "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    graph = payload["module_graph"]
    modules = {item["module"]: item["path"] for item in graph["modules"]}
    edges = {(item["from"], item["to"], item["import"]) for item in graph["edges"]}
    external_imports = {(item["from"], item["import"]) for item in graph["external_imports"]}

    assert modules["repo_map"] == "scripts/repo_map.py"
    assert modules["repo_common"] == "scripts/repo_common.py"
    assert ("repo_map", "repo_common", "repo_common") in edges
    assert ("repo_map", "repo_common") not in external_imports


def test_repo_map_builds_internal_javascript_module_graph(tmp_path: Path) -> None:
    repo = make_fixture(tmp_path)
    out = tmp_path / "repo_map.json"

    run_script("repo_map.py", str(repo), "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    graph = payload["module_graph"]
    modules = {item["module"]: item for item in graph["modules"]}
    edges = {(item["from"], item["to"], item["import"]) for item in graph["edges"]}
    external_imports = {(item["from"], item["import"]) for item in graph["external_imports"]}

    assert modules["src.server"]["language"] == "JavaScript"
    assert modules["src.util"]["path"] == "src/util.js"
    assert ("src.server", "src.util", "./util.js") in edges
    assert ("src.server", "express") in external_imports
    assert ("src.util", "./comment-only.js") not in external_imports
    assert ("src.util", "./template-only.js") not in external_imports


class FakeTreeSitterNode:
    def __init__(self, text: str, node_type: str, source: str, children: list["FakeTreeSitterNode"] | None = None) -> None:
        self.type = node_type
        self.start_byte = source.index(text)
        self.end_byte = self.start_byte + len(text.encode("utf-8"))
        self.start_point = (source[: self.start_byte].count("\n"), 0)
        self.children = children or []


class FakeTreeSitterTree:
    def __init__(self, root_node: FakeTreeSitterNode) -> None:
        self.root_node = root_node


class FakeTreeSitterParser:
    def __init__(self, root_node: FakeTreeSitterNode) -> None:
        self.root_node = root_node

    def parse(self, _source: bytes) -> FakeTreeSitterTree:
        return FakeTreeSitterTree(self.root_node)


def test_tree_sitter_javascript_analysis_reads_ast_nodes_not_comments_or_strings() -> None:
    repo_map = load_script_module("repo_map.py")
    source = """
// import ignored from "./comment-only.js";
const fake = "app.get('/string-only', handler)";
import { health } from "./util.js";
const express = require("express");
app.get("/health", handler);
export function health() { return "ok"; }
""".lstrip()
    root = FakeTreeSitterNode(
        source,
        "program",
        source,
        children=[
            FakeTreeSitterNode("// import ignored from \"./comment-only.js\";", "comment", source),
            FakeTreeSitterNode('"app.get(\'/string-only\', handler)"', "string", source),
            FakeTreeSitterNode(
                'import { health } from "./util.js";',
                "import_statement",
                source,
                [FakeTreeSitterNode('"./util.js"', "string", source)],
            ),
            FakeTreeSitterNode('require("express")', "call_expression", source, [FakeTreeSitterNode('"express"', "string", source)]),
            FakeTreeSitterNode('app.get("/health", handler)', "call_expression", source, [FakeTreeSitterNode('"/health"', "string", source)]),
            FakeTreeSitterNode(
                'export function health() { return "ok"; }',
                "export_statement",
                source,
                [FakeTreeSitterNode('"ok"', "string", source)],
            ),
        ],
    )

    analysis = repo_map.tree_sitter_javascript_analysis(source, "src/server.js", FakeTreeSitterParser(root))

    assert analysis["imports"] == ["./util.js", "express"]
    assert [item["path"] for item in analysis["routes"]] == ["/health"]
    assert "./comment-only.js" not in analysis["imports"]
    assert "ok" not in analysis["imports"]
    assert "/string-only" not in {item["path"] for item in analysis["routes"]}


def test_repo_map_emits_general_repo_graph(tmp_path: Path) -> None:
    repo = make_fixture(tmp_path)
    out = tmp_path / "repo_map.json"

    run_script("repo_map.py", str(repo), "--json-out", str(out))

    payload = json.loads(out.read_text(encoding="utf-8"))
    graph = payload["graph"]
    node_ids = {node["id"] for node in graph["nodes"]}
    edges = {(edge["from"], edge["to"], edge["kind"]) for edge in graph["edges"]}
    edge_ids = {edge["id"] for edge in graph["edges"]}

    assert graph["schema"] == "reveng.repo_graph.v1"
    assert "file:pkg/cli.py" in node_ids
    assert "module:pkg.cli" in node_ids
    assert "symbol:pkg/cli.py#main" in node_ids
    assert "route:GET:/health" in node_ids
    assert "route:GET:/items/{item_id}" in node_ids
    assert "dependency:python:requests>=2" in node_ids
    assert "plugin:.codex-plugin/plugin.json" in node_ids
    assert ("file:pkg/cli.py", "symbol:pkg/cli.py#main", "file_defines_symbol") in edges
    assert ("file:pkg/cli.py", "module:pkg.cli", "file_represents_module") in edges
    assert ("module:pkg.cli", "module:pkg.helpers", "module_imports_module") in edges
    assert ("file:src/server.js", "route:GET:/health", "file_exposes_route") in edges
    assert ("route:GET:/items/{item_id}", "symbol:pkg/cli.py#read_item", "route_bound_to_symbol") in edges
    assert "edge:file_defines_symbol:file:pkg/cli.py->symbol:pkg/cli.py#main" in edge_ids
    assert graph["limitations"]


def test_pyproject_fallback_extracts_multiline_dependencies_without_tomllib() -> None:
    repo_map = load_script_module("repo_map.py")

    payload = repo_map.parse_pyproject_fallback(
        """
[project]
dependencies = [
  "requests>=2",
  "pydantic>=2",
]

[project.scripts]
fixture-cli = "pkg.cli:main"
""".strip()
    )

    project = payload["project"]
    assert project["dependencies"] == ["requests>=2", "pydantic>=2"]
    assert project["scripts"]["fixture-cli"] == "pkg.cli:main"


def test_repo_corpus_export_emits_stable_records_with_hashes(tmp_path: Path) -> None:
    repo = make_fixture(tmp_path)
    out = tmp_path / "repo_corpus.jsonl"

    run_script("repo_corpus_export.py", str(repo), "--jsonl-out", str(out))

    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    paths = {record["path"] for record in records}
    cli_record = next(record for record in records if record["path"] == "pkg/cli.py")
    expected_hash = hashlib.sha256((repo / "pkg" / "cli.py").read_bytes()).hexdigest()
    assert "pyproject.toml" in paths
    assert "package.json" in paths
    assert "src/server.js" in paths
    assert cli_record["sha256"] == expected_hash
    assert "Runner" in cli_record["symbols"]
    assert "main" in cli_record["symbols"]
    assert "pkg.helpers" in cli_record["imports"]
    assert "requests" in cli_record["imports"]
    assert cli_record["evidence"]


def test_repo_corpus_export_links_records_to_repo_graph(tmp_path: Path) -> None:
    repo = make_fixture(tmp_path)
    map_out = tmp_path / "repo_map.json"
    corpus_out = tmp_path / "repo_corpus.jsonl"

    run_script("repo_map.py", str(repo), "--json-out", str(map_out))
    run_script("repo_corpus_export.py", str(repo), "--repo-map", str(map_out), "--jsonl-out", str(corpus_out))

    records = [json.loads(line) for line in corpus_out.read_text(encoding="utf-8").splitlines()]
    cli_record = next(record for record in records if record["path"] == "pkg/cli.py")
    refs = cli_record["graph_refs"]
    assert "file:pkg/cli.py" in refs["nodes"]
    assert "module:pkg.cli" in refs["nodes"]
    assert "symbol:pkg/cli.py#main" in refs["nodes"]
    assert "edge:file_defines_symbol:file:pkg/cli.py->symbol:pkg/cli.py#main" in refs["edges"]
    assert "edge:file_represents_module:file:pkg/cli.py->module:pkg.cli" in refs["edges"]


def test_repo_corpus_export_fails_fast_on_missing_repo_map(tmp_path: Path) -> None:
    repo = make_fixture(tmp_path)
    out = tmp_path / "repo_corpus.jsonl"
    missing = tmp_path / "missing_repo_map.json"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "repo_corpus_export.py"),
            str(repo),
            "--repo-map",
            str(missing),
            "--jsonl-out",
            str(out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "repo_map not readable" in result.stderr
