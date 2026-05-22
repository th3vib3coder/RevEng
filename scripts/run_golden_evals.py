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
import requests

app = FastAPI()

@app.get("/items/{item_id}")
def read_item(item_id: str):
    return {"item_id": item_id}

def main():
    return "ok"
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

    run_script("repo_inventory.py", repo, "--json-out", inventory_out)
    run_script("repo_map.py", repo, "--json-out", map_out)
    run_script("repo_corpus_export.py", repo, "--jsonl-out", corpus_out)

    inventory = read_json(inventory_out)
    repo_map = read_json(map_out)
    corpus = read_jsonl(corpus_out)

    manifest_paths = {item["path"] for item in inventory["manifests"]}
    require("generated_at" not in inventory, "repo_inventory must be deterministic by default")
    require("node_modules/ignored.js" not in {item["path"] for item in inventory["files"]}, "ignored dirs leaked into inventory")
    require("pyproject.toml" in manifest_paths, "pyproject manifest not detected")
    require(".codex-plugin/plugin.json" in manifest_paths, "Codex plugin manifest not detected")
    require(".claude-plugin/plugin.json" in manifest_paths, "Claude plugin manifest not detected")
    require(inventory["languages"]["Python"]["files"] >= 1, "Python language count missing")
    require(inventory["languages"]["JavaScript"]["files"] >= 1, "JavaScript language count missing")

    deps = {item["name"] for item in repo_map["dependencies"]}
    routes = {item["path"] for item in repo_map["routes"]}
    entrypoints = {item["name"] for item in repo_map["entrypoints"]}
    plugin_paths = {item["path"] for item in repo_map["plugins"]}
    risks = {item["kind"] for item in repo_map["risks"]}
    require({"requests>=2", "pydantic>=2", "express"}.issubset(deps), f"missing dependencies: {deps}")
    require({"/items/{item_id}", "/health"}.issubset(routes), f"missing routes: {routes}")
    require({"golden-cli", "test"}.issubset(entrypoints), f"missing entrypoints: {entrypoints}")
    require({".codex-plugin/plugin.json", ".claude-plugin/plugin.json"}.issubset(plugin_paths), "plugin surfaces missing")
    require("secret_pattern" in risks, "secret-like risk not detected")

    records = {record["path"]: record for record in corpus}
    require("pkg/cli.py" in records, "Python source missing from corpus")
    require("src/server.js" in records, "JS source missing from corpus")
    cli_hash = hashlib.sha256((repo / "pkg" / "cli.py").read_bytes()).hexdigest()
    require(records["pkg/cli.py"]["sha256"] == cli_hash, "corpus hash mismatch")
    require("main" in records["pkg/cli.py"]["symbols"], "Python symbol missing from corpus")
    require("requests" in records["pkg/cli.py"]["imports"], "Python import missing from corpus")
    require("smuggled_symbol" not in records["pkg/cli.py"]["symbols"], "AST symbols leaked a docstring def")
    require("smuggled_import" not in records["pkg/cli.py"]["imports"], "AST imports leaked a docstring import")

    return {
        "inventory_files": inventory["file_count"],
        "dependencies": sorted(deps),
        "routes": sorted(routes),
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
