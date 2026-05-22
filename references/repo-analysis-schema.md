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
