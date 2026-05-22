from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from typing import Any


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


def check_tools(tools: list[str]) -> dict[str, Any]:
    return {
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
            "platform": platform.platform(),
        },
        "tools": {tool: shutil.which(tool) for tool in tools},
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

