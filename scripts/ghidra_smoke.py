from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "reveng.ghidra_smoke.v1"
SCRIPTS = Path(__file__).resolve().parent


def write_json(path: str | None, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def ghidra_home_candidates(home: str) -> list[str]:
    support = Path(home) / "support"
    return [
        str(support / "analyzeHeadless"),
        str(support / "analyzeHeadless.bat"),
    ]


def discover_analyze_headless(
    explicit: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
    which: Any = shutil.which,
) -> dict[str, Any]:
    env = env or os.environ
    if explicit:
        return {"path": explicit, "method": "--analyze-headless", "available": True}
    env_path = env.get("GHIDRA_ANALYZE_HEADLESS")
    if env_path:
        return {"path": env_path, "method": "GHIDRA_ANALYZE_HEADLESS", "available": True}
    home = env.get("GHIDRA_HOME")
    if home:
        for candidate in ghidra_home_candidates(home):
            if Path(candidate).exists():
                return {"path": candidate, "method": "GHIDRA_HOME", "available": True}
    found = which("analyzeHeadless") or which("analyzeHeadless.bat")
    if found:
        return {"path": found, "method": "PATH", "available": True}
    return {"path": None, "method": "PATH", "available": False}


def build_analyze_headless_command(
    *,
    analyze_headless: str,
    project_dir: Path,
    project_name: str,
    sample: Path,
    export_json: Path,
) -> list[str]:
    return [
        analyze_headless,
        str(project_dir),
        project_name,
        "-import",
        str(sample),
        "-scriptPath",
        str(SCRIPTS),
        "-postScript",
        "ghidra_export_summary.py",
        "--json-out",
        str(export_json),
        "-deleteProject",
    ]


def base_payload(discovery: dict[str, Any], run_requested: bool) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "skipped",
        "available": bool(discovery["available"]),
        "discovery": {
            "analyze_headless": discovery["path"],
            "method": discovery["method"],
        },
        "run_requested": run_requested,
        "export_json": None,
        "command": [],
        "returncode": None,
        "execution_policy": {
            "ghidra_invoked": False,
            "sample_executed": False,
            "network_contacted": False,
            "policy": "Ghidra smoke imports a local sample into Ghidra only when --run is explicit; it never executes the sample.",
        },
        "warnings": [],
    }


def run_smoke(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    discovery = discover_analyze_headless(args.analyze_headless)
    payload = base_payload(discovery, args.run)
    if not discovery["available"]:
        payload["warnings"].append(
            "analyzeHeadless not found; set GHIDRA_HOME, GHIDRA_ANALYZE_HEADLESS, PATH, or --analyze-headless."
        )
        return 0, payload
    if not args.run:
        payload["warnings"].append("Ghidra was detected, but --run was not provided; no Ghidra process was launched.")
        return 0, payload
    if not args.sample:
        payload["status"] = "failed"
        payload["warnings"].append("--sample is required when --run is provided.")
        return 2, payload
    sample = Path(args.sample)
    if not sample.is_file():
        payload["status"] = "failed"
        payload["warnings"].append(f"sample not found or not a file: {sample}")
        return 2, payload

    export_json = Path(args.export_json) if args.export_json else Path(args.json_out or "ghidra_summary.json").with_name("ghidra_summary.json")
    export_json.parent.mkdir(parents=True, exist_ok=True)
    project_dir_context = None
    if args.project_dir:
        project_dir = Path(args.project_dir)
        project_dir.mkdir(parents=True, exist_ok=True)
    else:
        project_dir_context = tempfile.TemporaryDirectory(prefix="reveng-ghidra-smoke-")
        project_dir = Path(project_dir_context.name)

    command = build_analyze_headless_command(
        analyze_headless=str(discovery["path"]),
        project_dir=project_dir,
        project_name=args.project_name,
        sample=sample,
        export_json=export_json,
    )
    payload["command"] = command
    payload["export_json"] = str(export_json)
    payload["execution_policy"]["ghidra_invoked"] = True
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=args.timeout, check=False)
        payload["returncode"] = result.returncode
        payload["stdout_preview"] = result.stdout[-2000:]
        payload["stderr_preview"] = result.stderr[-2000:]
        payload["status"] = "passed" if result.returncode == 0 and export_json.is_file() else "failed"
        if payload["status"] == "failed":
            payload["warnings"].append("Ghidra analyzeHeadless returned non-zero or did not produce the export JSON.")
        return (0 if payload["status"] == "passed" else 1), payload
    except subprocess.TimeoutExpired as exc:
        payload["status"] = "failed"
        payload["warnings"].append(f"Ghidra smoke timed out after {args.timeout} seconds.")
        payload["stdout_preview"] = str(exc.stdout or "")[-2000:]
        payload["stderr_preview"] = str(exc.stderr or "")[-2000:]
        return 1, payload
    except OSError as exc:
        payload["status"] = "failed"
        payload["warnings"].append(f"failed to launch analyzeHeadless: {exc}")
        payload["stderr_preview"] = str(exc)[-2000:]
        return 1, payload
    finally:
        if project_dir_context is not None:
            project_dir_context.cleanup()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Conditionally run a real Ghidra headless smoke export")
    parser.add_argument("--json-out", help="Write smoke result JSON here")
    parser.add_argument("--run", action="store_true", help="Actually launch analyzeHeadless. Without this, the smoke is discovery-only.")
    parser.add_argument("--sample", help="Benign local file to import into Ghidra when --run is set")
    parser.add_argument("--export-json", help="Where ghidra_export_summary.py should write its export when --run is set")
    parser.add_argument("--project-dir", help="Temporary Ghidra project directory. Defaults to a temp dir.")
    parser.add_argument("--project-name", default="reveng-smoke")
    parser.add_argument("--analyze-headless", help="Explicit path to analyzeHeadless/analyzeHeadless.bat")
    parser.add_argument("--timeout", type=int, default=120)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    code, payload = run_smoke(args)
    write_json(args.json_out, payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
