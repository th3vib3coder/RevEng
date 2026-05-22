# Repo Analysis Playbook

Use this playbook when analyzing a local downloaded or cloned repository.

## Static-First Workflow

1. Confirm the target is a directory and identify the repository root.
2. Run `scripts/repo_inventory.py` to collect language, file, manifest, and size evidence.
3. Run `scripts/repo_map.py` to collect entrypoints, dependencies, routes, plugin surfaces, config files, static risks, Python module graph, and general repo graph.
4. Run `scripts/repo_corpus_export.py --repo-map repo_map.json` to emit a JSONL corpus suitable for RAG/MCP ingestion with `graph_refs`.
5. Read the generated JSON/JSONL and produce a Markdown report with evidence-backed claims and graph-backed architecture relationships.

## Report Sections

- Apparent purpose.
- Repository structure and major modules.
- Entrypoints and main flows.
- Dependencies and toolchain.
- API, CLI, MCP, plugin, and service surfaces.
- Security and supply-chain risk signals.
- Observed test/build strategy.
- Limitations and next analysis steps.

## Execution Boundary

Do not run `npm install`, `pip install`, build scripts, tests, Docker, shell scripts, Make targets, binaries, or repo-provided CLIs unless the operator explicitly approves the exact command and sandbox constraints.
