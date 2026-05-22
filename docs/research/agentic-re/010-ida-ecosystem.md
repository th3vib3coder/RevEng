# IDA Ecosystem Notes

Scope: IDA Pro integrations that inform RevEng without making IDA mandatory.

## Sources

- Trail of Bits `idac`: https://github.com/trailofbits/idac
- `mrexodia/ida-pro-mcp`: https://github.com/mrexodia/ida-pro-mcp
- `GameSecurityFrontierLib/ida-pro-mcp-plus`: https://github.com/GameSecurityFrontierLib/ida-pro-mcp-plus
- `Iamgublin/ida-codex-mcp`: https://github.com/Iamgublin/ida-codex-mcp

## `trailofbits/idac`

Observed facts:

- Presents IDA as an agent-friendly CLI rather than a classic MCP server.
- Commands can emit structured JSON.
- Mutations support preview/dry-run.
- Batch operations can run many subcommands against one shared context.
- Supports live GUI and headless database contexts selected explicitly.
- Broad commands require scoping/timeouts for context control.

Atomic ideas for RevEng:

- `ADOPT`: every RevEng script/tool should have machine-readable JSON output and stable schema fields.
- `ADAPT`: add a `--preview` convention for future mutating or report-writing helpers.
- `ADOPT`: support batch/case workflows where one manifest records every artifact path and command.
- `ADAPT`: make target context explicit (`--case-dir`, `--corpus`, `--binary`, `--repo`) instead of relying on current directory magic.
- `ADOPT`: broad discovery commands need caps and filters by default.

## `mrexodia/ida-pro-mcp`

Observed facts:

- Exposes IDA through MCP and supports many MCP clients, including Claude Code, Codex, Gemini CLI, and VS Code clients.
- Documents headless `idalib-mcp` with worker processes.
- Supports per-transport context isolation through `--isolated-contexts`.
- Provides MCP resources such as IDB metadata, segments, and entrypoints.
- Prompt guidance explicitly warns agents not to do base conversions manually and to use `int_convert`.
- Notes that decompilation alone is weak on obfuscation and recommends checking disassembly and removing common obfuscation layers first.

Atomic ideas for RevEng:

- `ADOPT`: add a deterministic integer/byte conversion helper before asking an LLM to reason about endian/hex math.
- `ADOPT`: make MCP resources first-class, not just tools.
- `ADAPT`: add session/case binding to all MCP tools so two analyses cannot silently mix.
- `ADAPT`: teach RevEng skills to cross-check decompiler output with raw assembly/export summaries when available.
- `TRACK`: IDA worker supervision is useful but depends on proprietary tooling.

## `ida-pro-mcp-plus`

Observed facts:

- Claims multi-instance analysis, headless batch via `idat.exe`, smart `.i64` caching, shared-memory IPC, 34 tools, and modular script groups.
- Exposes optional environment variables for cache directory, timeout, and shared memory size.
- Includes a complete test suite expectation for all tools.

Atomic ideas for RevEng:

- `ADAPT`: define external adapter capability manifests with `tool_name`, `available`, `version`, `transport`, `read_only`, `dangerous_tools`.
- `ADAPT`: add cache metadata to case outputs, but keep cache invalidation deterministic and explicit.
- `TRACK`: shared memory IPC is not needed for RevEng's source corpus MCP yet.
- `ADOPT`: tool suites should be modular and testable by category.

## `ida-codex-mcp`

Observed facts:

- Bridges IDA Pro 9.2 to MCP through an IDA plugin plus stdio MCP server.
- Exposes function lists, call graphs, Hex-Rays pseudocode, disassembly, imports/exports, xrefs, strings, and memory reads.
- Shows Codex CLI stdio configuration examples.
- License status is marked TBD in the README.

Atomic ideas for RevEng:

- `ADAPT`: keep stdio as the preferred local transport for RevEng MCP.
- `ADAPT`: define a minimal external-disassembler schema covering functions, call graph, pseudocode, disassembly, imports/exports, xrefs, strings, memory reads.
- `REJECT`: do not reuse code or schemas from this repo until licensing is clear.

## Upgrade Implications

Immediate:

- Add `references/external-adapter-schema.md`.
- Extend `re_tool_check.py` to emit adapter capability JSON for optional external tools.
- Add an `int_convert`-style helper or MCP tool for endian/base conversion.
- Add case manifest fields: `context_id`, `target_path`, `artifact_paths`, `created_by`, `source_tools`.

Later:

- IDA adapter docs can show how RevEng consumes exported JSON from idac/ida-pro-mcp without owning IDA automation itself.

