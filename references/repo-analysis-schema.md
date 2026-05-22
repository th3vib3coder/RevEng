# Repo Analysis Schema

## repo_inventory.json

- `root`: absolute analyzed repository path.
- `generated_at`: optional provenance timestamp. It is omitted by default so repeated static runs over the same repository are byte-reproducible; pass `--generated-at` when wall-clock provenance is required.
- `ignored_directories`: directory names skipped during traversal.
- `files`: file records with `path`, `size_bytes`, `sha256`, `language`, `kind`, and `is_text`.
- `languages`: counts and bytes by language.
- `manifests`: detected dependency, package, plugin, CI, Docker, and config manifests.

## repo_map.json

- `root`: absolute analyzed repository path.
- `entrypoints`: CLI, package, module, server, plugin, and script entrypoints observed from manifests or source.
- `dependencies`: dependency declarations extracted from package manifests.
- `routes`: API/server route candidates with method, path, source file, line, and framework hint.
- `plugins`: Codex, Claude Code, MCP, and app/plugin manifest surfaces.
- `configs`: CI, Docker, env, settings, and workflow files.
- `imports`: source-level import hints by file.
- `module_graph`: source module graph with `modules`, internal import `edges`, unresolved/external `external_imports`, `metrics` (per-module `fan_in`/`fan_out` plus import `cycles` as strongly-connected components and self-loops), and graph-specific `limitations`. Python imports use AST when parseable; JavaScript/TypeScript relative imports use a zero-dependency comment-aware static scanner.
- `graph`: general static evidence graph. Nodes include files, Python modules, symbols, routes, entrypoints, dependencies, plugins, and external imports. Edges include file-to-symbol, file-to-module, module-imports-module, module-imports-external, file-to-route, route-to-handler symbol, manifest-to-entrypoint, manifest-to-dependency, and file-to-plugin relationships. See `references/graph-analysis-schema.md`.
- `risks`: static supply-chain and execution-risk observations.
- `limitations`: what was not executed or could not be inferred.

## repo_corpus.jsonl

Each line is a JSON object:

- `path`: repository-relative path.
- `kind`: manifest, source, test, docs, config, plugin_manifest, or other.
- `language`: detected language.
- `sha256`: file content hash.
- `summary`: deterministic one-line summary from file metadata and first meaningful text.
- `symbols`: statically extracted symbols such as classes, functions, exports, and route handlers.
- `imports`: statically extracted import/dependency hints.
- `evidence`: short line-numbered excerpts used for traceability.
- `graph_refs`: optional stable node/edge ids from `repo_map.json` `graph`, present when `repo_corpus_export.py` is run with `--repo-map`.

## case_manifest.json

See `references/case-manifest-schema.md` for the full contract.

- `schema`: currently `reveng.case_manifest.v1`.
- `case_id`: deterministic identifier derived from target content hash, caps, target kind, and schema.
- `target`: operator-provided analyzed repository path plus deterministic content hash.
- `artifacts`: indexed outputs such as `repo_inventory.json`, `repo_map.json`, and `repo_corpus.jsonl` with size and SHA256.
- `caps`: analysis limits that affected output.
- `script_hashes`: SHA256 hashes of RevEng helper scripts used for the case.
- `ignored_directories`: traversal ignore list.
- `warnings`: sorted analysis warnings.
- `safety`: static-first metadata; default repo analysis records no target code execution and no network contact.

## MCP corpus server

`scripts/repo_corpus_mcp.py` exposes a read-only stdio MCP server over `repo_corpus.jsonl`.

Tools:

- `reveng.corpus_summary`: count corpus records by kind and language.
- `reveng.search_corpus`: search path, summary, symbols, imports, and evidence with `cursor` and hard-capped `limit`.
- `reveng.get_record`: retrieve one compact record by repository-relative path.
- `reveng.list_symbols`: list symbol hints with cursor pagination.
- `reveng.module_graph`: query the Python module dependency graph (internal edges, external imports, and hard-capped `metrics` fan-in/fan-out/cycles with `truncated`) from `repo_map.json`; read-only, cursor-paginated, requires the server started with `--repo-map`.
- `reveng.list_graph_nodes`: query general repo graph nodes by `kind` and substring `query`; read-only, cursor-paginated, requires `--repo-map`.
- `reveng.list_graph_edges`: query general repo graph edges by `kind`, `from`, and `to`; read-only, cursor-paginated, requires `--repo-map`.
- `reveng.graph_neighbors`: query adjacent graph nodes/edges for a single `node_id`; read-only, cursor-paginated, requires `--repo-map`.

Tool results return compact `content` text plus full `structuredContent`. Each structured result includes a `meta` envelope with `case_id`, `result_count`, `offset`, `next_offset`, `truncated`, and `warnings`. Argument validation errors are returned as tool-visible `isError: true` results with a structured error object and the same `meta` envelope so an agent can self-correct without losing protocol state.
