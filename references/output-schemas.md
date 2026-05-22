# Output Schemas

## repo_report

Markdown report with these sections:

- Apparent purpose.
- Structure and major modules.
- Entrypoints and flows.
- Dependencies and toolchain.
- API, CLI, MCP, plugin, and service surfaces.
- Security and supply-chain risk signals.
- Test/build strategy observed from files.
- Limitations and next steps.

Every non-obvious claim should cite a repository-relative path and, when possible, a line number.

## repo_corpus

Structured outputs:

- `repo_inventory.json`
- `repo_map.json`
- `repo_corpus.jsonl`

See `references/repo-analysis-schema.md` for field definitions.

## triage_report

JSON with `sample`, `hashes`, `file_type`, `size_bytes`, `bytes_analyzed`, `entropy`, `strings_summary`, `tool_outputs`, and `limitations`. `bytes_analyzed` may be smaller than `size_bytes` for very large files: entropy/strings/type use the first `--max-read-bytes` bytes (default 64 MiB) while hashes always stream the whole file. A truncation note is added to `limitations` when this happens.

## ioc_report

JSON/YAML groups: `hashes`, `network`, `file_paths`, `file_names`, `process_names`, `registry`, `mutexes`, `user_agents`, `emails`, `certificates`, and `notes`. Every item must include `value`, `confidence`, `source`, and `evidence_snippet`. Defanged and normalized variants are separate records when normalization is reversible. A top-level `truncated` boolean is `true` when a per-category cap (1000 items) dropped indicators or an overlong evidence line was clipped, so a report never looks complete while silently discarding evidence.

## android_api_report

JSON with `base_urls`, `endpoints`, `auth_headers`, `source_files`, and `limitations`. Endpoint records include source file and line when available.

## ghidra_report

JSON with `program`, `language_id`, `compiler_spec_id`, `functions`, `imports`, `exports`, `strings`, and `analysis_warnings`.

## parity_report

JSON with `target_function`, `source_candidates`, `signals`, `score`, `verdict`, and `review_notes`. Valid verdicts are `match`, `likely_match`, `unclear`, and `not_match`.
