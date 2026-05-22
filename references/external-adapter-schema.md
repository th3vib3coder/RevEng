# External Adapter Schema

RevEng core helpers are standard-library and static-first. External reverse-engineering adapters are optional evidence providers and are never invoked by `scripts/re_tool_check.py`.

## Output Contract

`scripts/re_tool_check.py --json` includes:

- `adapter_schema`: currently `reveng.external_adapters.v1`.
- `adapters`: adapter reports keyed by stable adapter id.
- `execution_policy`: proof fields showing that discovery did not execute adapters, samples, or network calls.
- `warnings`: non-fatal discovery notes.

Each adapter report includes:

- `id`: stable adapter id.
- `name`: human-readable adapter name.
- `category`: `ida`, `ghidra`, `radare2`, or `binary_ninja`.
- `available`: true when at least one known entrypoint is found on `PATH`.
- `entrypoints`: detected command names and absolute paths from `shutil.which`.
- `capabilities`: capability records with safety metadata.
- `safety_classes`: unique safety classes represented by the adapter.
- `invoked`: always false during discovery.
- `detection_method`: always PATH lookup only.
- `notes`: short operator guidance.

## Adapter IDs

Current adapter ids:

- `idac`
- `ida-pro-mcp`
- `r2mcp`
- `reva`
- `ghidra`
- `binary-ninja-headless-mcp`

## Safety Classes

- `read_only`: expected to retrieve static evidence without changing databases or running target code.
- `mutation_preview`: dry-run or preview-only mutation planning. Still cite evidence and avoid automatic commit.
- `mutation_commit`: changes a disassembler database, patch, symbol, type, or project state. Requires explicit operator approval.
- `execution`: starts a headless analyzer, debugger, emulator, container, or runtime workflow. Requires PAUSE and sandbox details.
- `raw_eval`: exposes arbitrary scripting/eval/call surfaces. Highest risk; never automatic.

Capability fields:

- `name`: stable capability label.
- `safety_class`: one of the classes above.
- `requires_pause`: true for `mutation_commit`, `execution`, and `raw_eval`.
- `enabled_by_default`: true only for `read_only`.

## Interpretation Rules

- Treat adapter availability as planning evidence, not permission to use the adapter.
- Missing adapters are not failures; RevEng core scripts continue to work.
- Do not call adapter commands, start MCP servers, import binaries into GUI/headless tools, mutate databases, or use eval surfaces without an explicit workflow and PAUSE gate where required.
- Record adapter versions and exact commands only after an approved adapter workflow actually runs.

## Source-Informed Design Notes

This schema is derived from the adapter patterns summarized in `docs/research/agentic-re/010-ida-ecosystem.md`, `020-ghidra-ecosystem.md`, `030-binja-radare-ecosystem.md`, and `050-security-and-mcp-patterns.md`.

Relevant upstream families include:

- Trail of Bits `idac`: agent-oriented IDA CLI with structured output and dry-run style workflows.
- IDA MCP bridge family: IDA/idalib-backed read, mutation, and debugger surfaces.
- ReVa / Ghidra assistant family: Ghidra and PyGhidra MCP-assisted static analysis.
- radare2 MCP / r2 AI family: lightweight radare-backed static and dynamic analysis surfaces.
- Binary Ninja MCP family: read-only queries plus transactional mutation and raw eval/script surfaces.
