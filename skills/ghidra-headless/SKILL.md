---
name: ghidra-headless
description: Ghidra and PyGhidra headless reverse engineering workflow for static binary analysis. Use when the user asks to import binaries into Ghidra, run analyzeHeadless, export function/import/string summaries, use PyGhidra scripts, or plan repeatable Ghidra analysis without GUI interaction.
---

# Ghidra Headless

Guide repeatable static analysis with a local Ghidra installation. The plugin does not install Ghidra and does not execute analyzed samples.

## Workflow

1. Confirm Ghidra or PyGhidra is installed locally.
   - Prefer `python3 scripts/re_tool_check.py --json` and inspect the `adapters.ghidra` and `adapters.reva` records.
   - Adapter discovery is PATH lookup only; it does not authorize running Ghidra.
2. Create or reuse a headless project outside the analyzed sample directory.
3. Use `analyzeHeadless` with `-import`, `-scriptPath`, and `-postScript` when appropriate.
4. Use `scripts/ghidra_export_summary.py` as a PyGhidra/Ghidra script to export program metadata, functions, imports, exports, strings, and warnings.

Example shape:

```bash
python3 scripts/ghidra_export_summary.py --json-out ghidra_summary.json
```

This script exits cleanly with a diagnostic outside a Ghidra/PyGhidra runtime.

## Safety

- Do not execute the analyzed binary.
- Do not assume decompiler output is source-equivalent.
- State tool versions and project paths when available.
- If a requested Ghidra step would execute code, debug a live process, run malware, or contact external infrastructure, respond with `PAUSE` and require explicit sandbox approval.

## Output

Return a Markdown summary and attach the JSON path. Include limitations when Ghidra is unavailable or when only syntax validation was possible.
