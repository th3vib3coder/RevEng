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
import requests

class Runner:
    pass

def main():
    return "ok"
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
const express = require("express");
const app = express();
app.get("/health", (req, res) => res.send("ok"));
module.exports = app;
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
    assert payload["languages"]["Python"]["files"] == 2
    assert payload["languages"]["JavaScript"]["files"] == 1
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
    assert ".codex-plugin/plugin.json" in plugin_paths
    assert ".claude-plugin/plugin.json" in plugin_paths
    assert payload["limitations"]


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
    assert "requests" in cli_record["imports"]
    assert cli_record["evidence"]
