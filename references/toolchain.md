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

## MCP Corpus Server

`scripts/repo_corpus_mcp.py` is a zero-dependency stdio MCP server over `repo_corpus.jsonl`.

Example:

```bash
python scripts/repo_corpus_mcp.py --corpus repo_corpus.jsonl
```

It is read-only, newline-delimited JSON-RPC over stdio, and exposes paginated corpus tools only. It does not execute repository code, package managers, binaries, containers, or network calls.
