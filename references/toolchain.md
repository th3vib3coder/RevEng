# Toolchain

The helper scripts use Python standard library only.

## Required

- Python 3.10 or newer.

## Optional Static Tools

- `file`, `strings`, `objdump`, `readelf`, `otool`
- `capa`, `floss`, `yara`, `diec`, `upx`

Optional tools improve evidence quality but are not required for core JSON outputs.

## Android Tools

- JDK 17+
- `jadx`
- Optional: `apktool`, `dex2jar`, Vineflower

## Ghidra Tools

- Local Ghidra installation for `analyzeHeadless`
- Optional PyGhidra for Python-driven analysis

The plugin does not download, install, or run these tools automatically.

## External Adapter Discovery

`scripts/re_tool_check.py --json` reports optional adapter availability under `adapters` using PATH lookup only. It does not start MCP servers, disassemblers, debuggers, containers, or eval surfaces.

Current adapter ids:

- `idac`
- `ida-pro-mcp`
- `r2mcp`
- `reva`
- `ghidra`
- `binary-ninja-headless-mcp`

Safety classes are documented in `references/external-adapter-schema.md`. `mutation_commit`, `execution`, and `raw_eval` capabilities require explicit PAUSE-gated operator approval before use.

## MCP Corpus Server

`scripts/repo_corpus_mcp.py` is a zero-dependency stdio MCP server over `repo_corpus.jsonl`.

Example:

```bash
python scripts/repo_corpus_mcp.py --corpus repo_corpus.jsonl
```

Pass `--repo-map repo_map.json` to enable module-graph and general repo-graph tools.

It is read-only, newline-delimited JSON-RPC over stdio, and exposes paginated corpus/graph tools only. It does not execute repository code, package managers, binaries, containers, or network calls.
