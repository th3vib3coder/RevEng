---
name: repo-reverse-engineering
description: Static-first reverse engineering of downloaded or cloned source repositories. Use when Codex or Claude Code needs to deeply analyze an unfamiliar repo, map architecture, entrypoints, dependencies, API/CLI/MCP/plugin surfaces, security and supply-chain risks, and produce both a Markdown report and RAG/MCP-ready corpus outputs.
---

# Repo Reverse Engineering

Analyze a local source repository without executing its code. Produce an evidence-backed Markdown report plus structured artifacts for downstream RAG/MCP ingestion.

## Safety

- Static-first only: read files, manifests, docs, configs, tests, routes, lockfiles, and source text.
- Do not run builds, tests, installers, package managers, Docker, shell scripts, binaries, or repo-provided CLIs automatically.
- If execution is requested or required, respond:

> PAUSE: This step would execute code from the analyzed repository. Confirm sandbox, network posture, snapshot/rollback state, exact command, and output path before continuing.

## Quick Start

From the plugin root, run:

```bash
python3 scripts/repo_inventory.py /path/to/repo --json-out repo_inventory.json
python3 scripts/repo_map.py /path/to/repo --json-out repo_map.json
python3 scripts/repo_corpus_export.py /path/to/repo --jsonl-out repo_corpus.jsonl
```

When the user asks to query the corpus through an agent/MCP workflow, serve it read-only:

```bash
python3 scripts/repo_corpus_mcp.py --corpus repo_corpus.jsonl
```

On Windows, use `python` if `python3` is absent.

Read details only when needed:

- `references/repo-analysis-playbook.md`
- `references/repo-analysis-schema.md`
- `references/output-schemas.md`

## Analysis Procedure

1. Inspect `repo_inventory.json` for languages, file mix, size, ignored directories, and manifest evidence.
2. Inspect `repo_map.json` for entrypoints, dependencies, routes, plugin/MCP surfaces, configs, and risk observations.
3. Inspect `repo_map.json` `module_graph` for Python internal import edges and unresolved/external imports.
4. Sample `repo_corpus.jsonl` to verify records contain stable hashes, summaries, symbols, imports, and evidence excerpts.
5. If MCP/RAG interaction is requested, use `repo_corpus_mcp.py` and prefer cursor-paginated tools over pasting large corpus sections into chat.
6. Write the Markdown report with these sections:
   - Apparent purpose.
   - Structure and major modules.
   - Entrypoints and flows.
   - Dependencies and toolchain.
   - API, CLI, MCP, plugin, and service surfaces.
   - Security and supply-chain risk signals.
   - Test/build strategy observed from files.
   - Limitations and next steps.

## Output Contract

Always deliver:

- A Markdown report with file/line evidence for non-obvious claims.
- Paths to `repo_inventory.json`, `repo_map.json`, and `repo_corpus.jsonl`.
- If requested, MCP server startup command for querying the generated corpus.
- Limitations, especially anything not executed because of the static-first boundary.

Do not claim runtime behavior, successful builds, test status, exploitability, or production safety unless those were separately verified under an approved execution gate.
