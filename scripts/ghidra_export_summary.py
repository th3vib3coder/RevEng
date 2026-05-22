from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def fail_outside_ghidra(json_out: str | None) -> int:
    payload = {
        "error": "This script must run inside a Ghidra or PyGhidra environment with currentProgram available.",
        "analysis_warnings": ["No Ghidra runtime detected; no binary analysis was performed."],
    }
    if json_out:
        out = Path(json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    return 2


def collect_summary() -> dict[str, Any]:
    program = globals().get("currentProgram")
    if program is None:
        raise RuntimeError("currentProgram is unavailable")
    listing = program.getListing()
    warnings: list[str] = []

    functions: list[dict[str, Any]] = []
    try:
        for func in listing.getFunctions(True):
            functions.append({"name": str(func.getName()), "entry": str(func.getEntryPoint())})
            if len(functions) >= 5000:
                break
    except Exception as exc:  # pragma: no cover - requires Ghidra runtime
        warnings.append(f"function extraction failed: {exc}")

    symbol_table = None
    try:
        symbol_table = program.getSymbolTable()
    except Exception as exc:  # pragma: no cover - requires Ghidra runtime
        warnings.append(f"symbol table unavailable: {exc}")

    imports: list[dict[str, Any]] = []
    if symbol_table is not None:
        try:
            for sym in symbol_table.getExternalSymbols():
                namespace = sym.getParentNamespace()
                imports.append(
                    {
                        "name": str(sym.getName()),
                        "library": str(namespace.getName()) if namespace is not None else None,
                    }
                )
                if len(imports) >= 5000:
                    break
        except Exception as exc:  # pragma: no cover - requires Ghidra runtime
            warnings.append(f"import extraction failed: {exc}")

    exports: list[dict[str, Any]] = []
    if symbol_table is not None:
        try:
            for addr in symbol_table.getExternalEntryPointIterator():
                sym = symbol_table.getPrimarySymbol(addr)
                exports.append(
                    {"name": str(sym.getName()) if sym is not None else None, "address": str(addr)}
                )
                if len(exports) >= 5000:
                    break
        except Exception as exc:  # pragma: no cover - requires Ghidra runtime
            warnings.append(f"export extraction failed: {exc}")

    strings: list[dict[str, Any]] = []
    try:
        from ghidra.program.util import DefinedDataIterator

        for data in DefinedDataIterator.definedStrings(program):
            strings.append({"address": str(data.getAddress()), "value": str(data.getValue())[:200]})
            if len(strings) >= 5000:
                break
    except Exception as exc:  # pragma: no cover - requires Ghidra runtime
        warnings.append(f"string extraction failed or unsupported: {exc}")

    return {
        "program": str(program.getName()),
        "language_id": str(program.getLanguageID()),
        "compiler_spec_id": str(program.getCompilerSpec().getCompilerSpecID()),
        "functions": functions,
        "imports": imports,
        "exports": exports,
        "strings": strings,
        "analysis_warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a static Ghidra summary as JSON")
    parser.add_argument("--json-out")
    args = parser.parse_args()
    try:
        payload = collect_summary()
    except Exception:
        return fail_outside_ghidra(args.json_out)
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
