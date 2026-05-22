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


MAX_GRAPH_FUNCTIONS = 200
MAX_BLOCKS_PER_FUNCTION = 500


def function_record(func: Any) -> dict[str, str]:
    return {"name": str(func.getName()), "entry": str(func.getEntryPoint())}


def collect_call_graph(functions: list[Any]) -> dict[str, Any]:
    nodes = [function_record(func) for func in functions[:MAX_GRAPH_FUNCTIONS]]
    known = {str(func.getEntryPoint()): str(func.getName()) for func in functions[:MAX_GRAPH_FUNCTIONS]}
    edges: list[dict[str, str]] = []
    warnings: list[str] = []
    for func in functions[:MAX_GRAPH_FUNCTIONS]:
        try:
            called = func.getCalledFunctions(None)
        except Exception as exc:  # pragma: no cover - requires Ghidra runtime
            warnings.append(f"call graph unavailable for {func.getName()}: {exc}")
            continue
        for target in called:
            target_entry = str(target.getEntryPoint())
            edges.append(
                {
                    "from": str(func.getName()),
                    "from_entry": str(func.getEntryPoint()),
                    "to": known.get(target_entry, str(target.getName())),
                    "to_entry": target_entry,
                }
            )
            if len(edges) >= 5000:
                break
    return {
        "nodes": nodes,
        "edges": sorted(edges, key=lambda item: (item["from_entry"], item["to_entry"])),
        "warnings": warnings,
        "limitations": [
            "Call graph is best-effort and static; indirect calls, thunks, and unresolved dynamic dispatch may be missing.",
        ],
    }


def block_start(block: Any) -> str:
    if hasattr(block, "getFirstStartAddress"):
        return str(block.getFirstStartAddress())
    if hasattr(block, "getMinAddress"):
        return str(block.getMinAddress())
    return str(block)


def block_destinations(block: Any) -> list[str]:
    try:
        destinations = block.getDestinations(None)
    except Exception:
        return []
    values: list[str] = []
    for destination in destinations:
        if hasattr(destination, "getDestinationAddress"):
            values.append(str(destination.getDestinationAddress()))
        else:
            values.append(str(destination))
    return values


def fake_or_runtime_blocks(program: Any, func: Any) -> tuple[list[Any], list[str]]:
    if hasattr(func, "getBasicBlocks"):
        try:
            return list(func.getBasicBlocks())[:MAX_BLOCKS_PER_FUNCTION], []
        except Exception as exc:
            return [], [f"fake/basic-block accessor failed for {func.getName()}: {exc}"]
    warnings: list[str] = []
    try:  # pragma: no cover - requires Ghidra runtime
        from ghidra.program.model.block import BasicBlockModel

        model = BasicBlockModel(program)
        blocks = list(model.getCodeBlocksContaining(func.getBody(), None))
        return blocks[:MAX_BLOCKS_PER_FUNCTION], []
    except Exception as exc:  # pragma: no cover - requires Ghidra runtime
        warnings.append(f"CFG unavailable for {func.getName()}: {exc}")
        return [], warnings


def collect_function_cfgs(program: Any, functions: list[Any]) -> tuple[list[dict[str, Any]], list[str]]:
    cfgs: list[dict[str, Any]] = []
    warnings: list[str] = []
    for func in functions[:MAX_GRAPH_FUNCTIONS]:
        blocks, block_warnings = fake_or_runtime_blocks(program, func)
        warnings.extend(block_warnings)
        block_records: list[dict[str, str]] = []
        edges: list[dict[str, str]] = []
        for block in blocks:
            start = block_start(block)
            block_records.append({"id": start, "start": start})
            for destination in block_destinations(block):
                edges.append({"from": start, "to": destination})
        if blocks:
            cfgs.append(
                {
                    "function": str(func.getName()),
                    "entry": str(func.getEntryPoint()),
                    "basic_blocks": sorted(block_records, key=lambda item: item["id"]),
                    "edges": sorted(edges, key=lambda item: (item["from"], item["to"])),
                    "limitations": [
                        "CFG is best-effort and may omit exception edges, computed jumps, and analysis-incomplete blocks.",
                    ],
                }
            )
    return cfgs, warnings


def collect_xrefs(program: Any, functions: list[Any]) -> tuple[list[dict[str, str]], list[str]]:
    warnings: list[str] = []
    xrefs: list[dict[str, str]] = []
    try:
        reference_manager = program.getReferenceManager()
    except Exception as exc:
        return [], [f"xrefs unavailable: {exc}"]
    for func in functions[:MAX_GRAPH_FUNCTIONS]:
        try:
            references = reference_manager.getReferencesTo(func.getEntryPoint())
        except Exception as exc:  # pragma: no cover - requires Ghidra runtime
            warnings.append(f"xrefs unavailable for {func.getName()}: {exc}")
            continue
        for ref in references:
            try:
                from_addr = ref.getFromAddress()
            except Exception:
                from_addr = None
            xrefs.append(
                {
                    "to_function": str(func.getName()),
                    "to_entry": str(func.getEntryPoint()),
                    "from": str(from_addr) if from_addr is not None else str(ref),
                }
            )
            if len(xrefs) >= 5000:
                return sorted(xrefs, key=lambda item: (item["to_entry"], item["from"])), warnings
    return sorted(xrefs, key=lambda item: (item["to_entry"], item["from"])), warnings


def graph_summaries(call_graph: dict[str, Any], cfgs: list[dict[str, Any]]) -> list[str]:
    summaries = [
        f"Call graph: {len(call_graph.get('nodes', []))} function node(s), {len(call_graph.get('edges', []))} call edge(s)."
    ]
    for cfg in cfgs[:25]:
        summaries.append(
            f"CFG {cfg['function']}@{cfg['entry']}: {len(cfg['basic_blocks'])} basic block(s), {len(cfg['edges'])} edge(s)."
        )
    return summaries


def collect_summary(program: Any | None = None) -> dict[str, Any]:
    if program is None:
        program = globals().get("currentProgram")
    if program is None:
        raise RuntimeError("currentProgram is unavailable")
    listing = program.getListing()
    warnings: list[str] = []

    functions: list[dict[str, Any]] = []
    function_objects: list[Any] = []
    try:
        for func in listing.getFunctions(True):
            function_objects.append(func)
            functions.append(function_record(func))
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

    call_graph = collect_call_graph(function_objects)
    cfgs, cfg_warnings = collect_function_cfgs(program, function_objects)
    xrefs, xref_warnings = collect_xrefs(program, function_objects)
    warnings.extend(call_graph.get("warnings", []))
    warnings.extend(cfg_warnings)
    warnings.extend(xref_warnings)

    return {
        "program": str(program.getName()),
        "language_id": str(program.getLanguageID()),
        "compiler_spec_id": str(program.getCompilerSpec().getCompilerSpecID()),
        "functions": functions,
        "imports": imports,
        "exports": exports,
        "strings": strings,
        "xrefs": xrefs,
        "call_graph": call_graph,
        "function_cfgs": cfgs,
        "graph_summaries": graph_summaries(call_graph, cfgs),
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
