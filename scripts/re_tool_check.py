from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from typing import Any, Callable


DEFAULT_TOOLS = [
    "file",
    "strings",
    "objdump",
    "readelf",
    "otool",
    "diec",
    "capa",
    "floss",
    "yara",
    "upx",
    "jadx",
    "apktool",
    "analyzeHeadless",
    "pyghidra",
]


ADAPTER_SCHEMA = "reveng.external_adapters.v1"
PAUSE_REQUIRED_CLASSES = {"mutation_commit", "execution", "raw_eval"}

ADAPTERS: list[dict[str, Any]] = [
    {
        "id": "idac",
        "name": "Trail of Bits idac",
        "category": "ida",
        "entrypoint_names": ["idac"],
        "notes": "Agent-friendly IDA command line interface. Detection only; RevEng does not invoke IDA.",
        "capabilities": [
            {"name": "structured_database_query", "safety_class": "read_only"},
            {"name": "dry_run_database_mutation", "safety_class": "mutation_preview"},
            {"name": "commit_database_mutation", "safety_class": "mutation_commit"},
        ],
    },
    {
        "id": "ida-pro-mcp",
        "name": "IDA Pro MCP",
        "category": "ida",
        "entrypoint_names": ["ida-pro-mcp", "idalib-mcp", "ida-mcp"],
        "notes": "IDA MCP bridge family. Treat mutating/debugger tools as gated even when the adapter is present.",
        "capabilities": [
            {"name": "decompile_and_xrefs", "safety_class": "read_only"},
            {"name": "database_patch_or_rename", "safety_class": "mutation_commit"},
            {"name": "debugger_control", "safety_class": "execution"},
        ],
    },
    {
        "id": "r2mcp",
        "name": "radare2 MCP",
        "category": "radare2",
        "entrypoint_names": ["r2mcp", "radare2-mcp", "r2ai"],
        "notes": "radare2-based MCP or AI bridge. Prefer read-only commands unless operator approves mutation or execution.",
        "capabilities": [
            {"name": "static_binary_query", "safety_class": "read_only"},
            {"name": "patch_or_write_commands", "safety_class": "mutation_commit"},
            {"name": "debugger_or_emulation", "safety_class": "execution"},
        ],
    },
    {
        "id": "reva",
        "name": "ReVa Ghidra Assistant",
        "category": "ghidra",
        "entrypoint_names": ["reva", "reverse-engineering-assistant", "pyghidra"],
        "notes": "Ghidra/PyGhidra assistant family. Presence enables planning only; RevEng does not start servers automatically.",
        "capabilities": [
            {"name": "ghidra_static_summary", "safety_class": "read_only"},
            {"name": "headless_project_analysis", "safety_class": "execution"},
        ],
    },
    {
        "id": "ghidra",
        "name": "Ghidra / PyGhidra",
        "category": "ghidra",
        "entrypoint_names": ["analyzeHeadless", "pyghidra"],
        "notes": "Local Ghidra installation or PyGhidra package. Used only after explicit workflow selection.",
        "capabilities": [
            {"name": "program_metadata_export", "safety_class": "read_only"},
            {"name": "imports_exports_strings_export", "safety_class": "read_only"},
            {"name": "headless_import_analysis", "safety_class": "execution"},
        ],
    },
    {
        "id": "binary-ninja-headless-mcp",
        "name": "Binary Ninja Headless MCP",
        "category": "binary_ninja",
        "entrypoint_names": ["binary-ninja-headless-mcp", "binja-headless-mcp", "binja-mcp"],
        "notes": "Binary Ninja MCP family. Raw eval/script capabilities are high-risk and never automatic.",
        "capabilities": [
            {"name": "static_binary_view_query", "safety_class": "read_only"},
            {"name": "transactional_database_mutation", "safety_class": "mutation_commit"},
            {"name": "python_eval_or_call", "safety_class": "raw_eval"},
        ],
    },
]


def annotate_capability(capability: dict[str, str]) -> dict[str, Any]:
    safety_class = capability["safety_class"]
    return {
        "name": capability["name"],
        "safety_class": safety_class,
        "requires_pause": safety_class in PAUSE_REQUIRED_CLASSES,
        "enabled_by_default": safety_class == "read_only",
    }


def adapter_report(adapter: dict[str, Any], which: Callable[[str], str | None]) -> dict[str, Any]:
    entrypoints = [
        {"name": name, "path": path}
        for name in adapter["entrypoint_names"]
        if (path := which(name))
    ]
    safety_classes = sorted({capability["safety_class"] for capability in adapter["capabilities"]})
    return {
        "id": adapter["id"],
        "name": adapter["name"],
        "category": adapter["category"],
        "available": bool(entrypoints),
        "entrypoints": entrypoints,
        "capabilities": [annotate_capability(capability) for capability in adapter["capabilities"]],
        "safety_classes": safety_classes,
        "invoked": False,
        "detection_method": "PATH lookup only via shutil.which; adapters are not executed",
        "notes": adapter["notes"],
    }


def check_tools(tools: list[str], which: Callable[[str], str | None] = shutil.which) -> dict[str, Any]:
    adapters = {adapter["id"]: adapter_report(adapter, which) for adapter in ADAPTERS}
    warnings: list[str] = []
    if not any(adapter["available"] for adapter in adapters.values()):
        warnings.append("No external RE adapters detected on PATH; core RevEng helpers still work without them.")
    return {
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
            "platform": platform.platform(),
        },
        "tools": {tool: which(tool) for tool in tools},
        "adapter_schema": ADAPTER_SCHEMA,
        "adapters": adapters,
        "execution_policy": {
            "adapters_invoked": False,
            "network_contacted": False,
            "sample_executed": False,
            "policy": "Detection uses PATH lookup only. Adapter use is optional and must obey PAUSE gates for execution, mutation, and raw eval.",
        },
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local reverse-engineering tool availability")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--tools", nargs="*", default=DEFAULT_TOOLS)
    args = parser.parse_args()

    payload = check_tools(args.tools)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for tool, path in payload["tools"].items():
            print(f"{tool}: {path or 'missing'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
