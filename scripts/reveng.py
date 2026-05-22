from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def run_script(name: str, *args: object) -> None:
    """Run a bundled RevEng helper script, inheriting stdio.

    Only RevEng's own static helper scripts are launched here; no analyzed
    sample, repository code, or external adapter is ever executed.
    """
    command = [sys.executable, str(SCRIPTS / name), *(str(arg) for arg in args)]
    subprocess.run(command, check=True)


def cmd_analyze_repo(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    inventory = out / "repo_inventory.json"
    repo_map = out / "repo_map.json"
    corpus = out / "repo_corpus.jsonl"
    manifest = out / "case_manifest.json"

    run_script("repo_inventory.py", args.repo, "--json-out", inventory)
    run_script("repo_map.py", args.repo, "--json-out", repo_map)
    run_script("repo_corpus_export.py", args.repo, "--repo-map", repo_map, "--jsonl-out", corpus)
    run_script(
        "case_manifest.py",
        "--case-dir",
        out,
        "--target",
        args.repo,
        "--target-kind",
        "source_repo",
        "--artifact",
        f"repo_inventory={inventory}",
        "--artifact",
        f"repo_map={repo_map}",
        "--artifact",
        f"repo_corpus={corpus}",
        "--json-out",
        manifest,
    )
    print(f"Static case written to {out}")
    return 0


def cmd_check_tools(args: argparse.Namespace) -> int:
    extra: list[object] = []
    if args.json:
        extra.append("--json")
    if args.tools:
        extra.extend(["--tools", *args.tools])
    run_script("re_tool_check.py", *extra)
    return 0


def cmd_triage_binary(args: argparse.Namespace) -> int:
    extra: list[object] = [args.sample, "--json-out", args.out]
    if args.max_read_bytes is not None:
        extra.extend(["--max-read-bytes", args.max_read_bytes])
    run_script("static_triage.py", *extra)
    return 0


def cmd_extract_iocs(args: argparse.Namespace) -> int:
    run_script("ioc_extract.py", args.evidence, "--json-out", args.out)
    return 0


def cmd_android_scan(args: argparse.Namespace) -> int:
    run_script("android_api_scan.py", args.source_root, "--json-out", args.out)
    return 0


def cmd_serve_corpus(args: argparse.Namespace) -> int:
    extra: list[object] = ["--corpus", args.corpus]
    if args.repo_map:
        extra.extend(["--repo-map", args.repo_map])
    run_script("repo_corpus_mcp.py", *extra)
    return 0


def cmd_ghidra_smoke(args: argparse.Namespace) -> int:
    extra: list[object] = []
    if args.json_out:
        extra.extend(["--json-out", args.json_out])
    if args.run:
        extra.append("--run")
    if args.sample:
        extra.extend(["--sample", args.sample])
    if args.export_json:
        extra.extend(["--export-json", args.export_json])
    if args.project_dir:
        extra.extend(["--project-dir", args.project_dir])
    if args.project_name:
        extra.extend(["--project-name", args.project_name])
    if args.analyze_headless:
        extra.extend(["--analyze-headless", args.analyze_headless])
    if args.timeout is not None:
        extra.extend(["--timeout", args.timeout])
    run_script("ghidra_smoke.py", *extra)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reveng",
        description="RevEng unified CLI. Static-first: never executes analyzed samples, repository code, or external adapters.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze-repo", help="Full static case: inventory + map + corpus(+graph_refs) + case_manifest")
    analyze.add_argument("repo", help="Repository directory to analyze")
    analyze.add_argument("--out", required=True, help="Case/output directory")
    analyze.set_defaults(func=cmd_analyze_repo)

    check = sub.add_parser("check-tools", help="Detect local RE tools/adapters (PATH discovery only)")
    check.add_argument("--json", action="store_true")
    check.add_argument("--tools", nargs="*")
    check.set_defaults(func=cmd_check_tools)

    triage = sub.add_parser("triage-binary", help="Static binary triage")
    triage.add_argument("sample")
    triage.add_argument("--out", required=True)
    triage.add_argument("--max-read-bytes")
    triage.set_defaults(func=cmd_triage_binary)

    iocs = sub.add_parser("extract-iocs", help="Extract defensive IOCs from evidence text")
    iocs.add_argument("evidence")
    iocs.add_argument("--out", required=True)
    iocs.set_defaults(func=cmd_extract_iocs)

    android = sub.add_parser("android-scan", help="Scan decompiled Android source for API surfaces")
    android.add_argument("source_root")
    android.add_argument("--out", required=True)
    android.set_defaults(func=cmd_android_scan)

    serve = sub.add_parser("serve-corpus", help="Serve repo_corpus.jsonl over the read-only MCP stdio server")
    serve.add_argument("corpus")
    serve.add_argument("--repo-map")
    serve.set_defaults(func=cmd_serve_corpus)

    ghidra = sub.add_parser("ghidra-smoke", help="Discovery-only Ghidra smoke; launches analyzeHeadless only with --run")
    ghidra.add_argument("--json-out", required=True)
    ghidra.add_argument("--run", action="store_true")
    ghidra.add_argument("--sample")
    ghidra.add_argument("--export-json")
    ghidra.add_argument("--project-dir")
    ghidra.add_argument("--project-name", default="reveng-smoke")
    ghidra.add_argument("--analyze-headless")
    ghidra.add_argument("--timeout", type=int, default=120)
    ghidra.set_defaults(func=cmd_ghidra_smoke)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
