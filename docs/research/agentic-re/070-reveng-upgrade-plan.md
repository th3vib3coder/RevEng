# RevEng vNext Upgrade Plan

Goal: upgrade RevEng from a strong static-first plugin into a graph-aware, evidence-preserving, token-safe agentic reverse-engineering workbench while keeping the current portability and safety model.

This plan is derived from `060-atomic-ideas-for-reveng.md`. It is not an ACCEPT claim. Implementation should use RED -> GREEN tests and adversarial review before closure.

## Non-Negotiables

- Keep Codex + Claude Code portability.
- Keep Python standard library core scripts unless a phase explicitly introduces an optional dependency.
- Keep source repository analysis static-first.
- Do not execute unknown binaries, package managers, tests, builds, containers, or debuggers without PAUSE.
- Do not add raw eval/pass-through MCP tools.
- Every new report claim must cite file/function/path/tool evidence.

## Phase 1: Research Ledger And Case Manifests

Status: implemented for source-repo and file-target cases.

Tasks:

- Added `references/case-manifest-schema.md`.
- Added `scripts/case_manifest.py` to create `case_manifest.json` for source repository and file-target analysis outputs.
- Records input path, stable target-derived case ID, target content hash, artifact hashes, helper script hashes, caps, ignored paths, warnings, and static-first safety posture.
- Updated repo skill to use a case directory for deep analysis.

Tests:

- Manifest is deterministic across repeated runs.
- Manifest includes every expected artifact.
- Manifest does not include local absolute plugin paths unless explicitly reporting operator input.

Acceptance:

- A user can rerun an analysis and diff the manifest and artifacts.

## Phase 2: Graph-Aware Source Repository Analysis

Status: implemented for source-repo analysis with zero-dependency fallback and optional Tree-sitter JS/TS parsing when installed.

Implemented:

- `repo_map.py` emits a source `module_graph` with stable modules, internal import `edges`, unresolved/external imports, and graph-specific limitations.
- Python source analysis uses AST for imports, symbols, classes, functions, async functions, and route decorators when parseable.
- Python module naming handles common `src/` layouts declared in `pyproject.toml` or indicated by package markers, so imports such as `re_agent.*` resolve to `src/re_agent/*`.
- Python module naming also handles top-level script roots such as `scripts/` when files import sibling helper modules as top-level names.
- `module_graph` also includes JavaScript/TypeScript modules and resolves relative imports using optional Tree-sitter when installed, otherwise a zero-dependency comment-aware static scanner.
- `module_graph.metrics` includes per-module `fan_in`, `fan_out`, and import `cycles`.
- Cycle detection uses iterative Tarjan/SCC logic to avoid recursion-limit failures on deep graphs.
- `repo_corpus_mcp.py` exposes `reveng.module_graph` with internal edges, external imports, hard-capped graph metrics, cursor pagination, and `truncated`.
- `repo_map.py` emits `graph` with file, module, symbol, route, entrypoint, dependency, plugin, and external-import nodes.
- General graph edges include file-to-symbol, file-to-module, module-to-module imports, module-to-external imports, file-to-route, route-to-handler symbol, manifest-to-entrypoint, manifest-to-dependency, and file-to-plugin relationships.
- `repo_corpus_export.py --repo-map` adds `graph_refs` to every corpus record.
- `repo_corpus_mcp.py` exposes `reveng.list_graph_nodes`, `reveng.list_graph_edges`, and `reveng.graph_neighbors`.
- Added `references/graph-analysis-schema.md`.

Tests:

- Python AST fixture with real imports, classes, async functions, FastAPI routes, and fake docstring symbols.
- Node fixture with Express route and package scripts.
- Cross-file fixture proving internal import edges.
- MCP pagination and cap tests for graph tools.

Acceptance:

- Repo reports can cite a compact graph neighborhood instead of dumping file lists.

## Phase 3: Token-Safe MCP Hardening

Status: implemented for the current corpus and graph MCP tools.

Implemented:

- `repo_corpus_mcp.py` is read-only stdio JSON-RPC over `repo_corpus.jsonl`.
- Tool results split compact `content` text from machine-readable `structuredContent`.
- Corpus search, symbol listing, module graph edges, and module graph metrics are hard-capped and cursor-paginated where applicable.
- Invalid tool inputs return tool-visible structured errors with `isError: true`.
- `get_record` validates repository-relative paths and never reads source files from disk.
- Standard MCP result envelope fields:
  - `case_id`
  - `result_count`
  - `offset`
  - `next_offset`
  - `truncated`
  - `warnings`
- Tool-visible structured errors for invalid arguments and unavailable graph inputs; not-found lookups return a non-error result with `meta.warnings` so agents can continue.
- Query echo is capped to prevent context flooding.
- Injection-looking strings remain inert corpus evidence.

Tests:

- Invalid calls return `isError: true` and expected schema.
- Large result sets never exceed configured caps.
- Strings containing "ignore previous instructions" are returned as quoted evidence only.

Acceptance:

- MCP tools are predictable enough for agents to recover from mistakes without crashing or flooding context.

## Phase 4: External Adapter Schema

Status: implemented for discovery-only adapter inventory.

Implemented:

- Added `references/external-adapter-schema.md`.
- Extended `re_tool_check.py --json` to report optional adapter capabilities:
  - `idac`
  - `ida-pro-mcp`
  - `r2mcp`
  - `reva`
  - `ghidra`
  - `binary-ninja-headless-mcp`
- Records safety class:
  - `read_only`
  - `mutation_preview`
  - `mutation_commit`
  - `execution`
  - `raw_eval`
- Reports `execution_policy` proving discovery only uses PATH lookup and does not invoke adapters.
- Updated skills/docs to treat adapters only as optional evidence providers.

Tests:

- Fake PATH fixtures prove detection and non-detection.
- Dangerous adapter capabilities are reported but not invoked.
- Missing tools degrade gracefully.

Acceptance:

- RevEng can tell the agent what external RE infrastructure exists without coupling core functionality to it.

## Phase 5: Ghidra Graph Export

Status: implemented with fake-object fixtures, outside-Ghidra syntax validation, and a conditional real-smoke runner. Real execution still depends on a local Ghidra installation.

Implemented:

- Extended `ghidra_export_summary.py` to emit best-effort:
  - function list
  - imports/exports
  - strings
  - xrefs
  - function call graph
  - basic block CFG per selected function
  - decompiler warnings
- Added compact text graph summaries.
- Keeps all fields optional with warnings when Ghidra APIs are unavailable.

Tests:

- Syntax compile test outside Ghidra.
- Fake Ghidra object fixture for CFG/FCG serialization.
- Golden fixture for graph summary formatting.
- `ghidra_smoke.py` contract test: structured skip without local Ghidra, no invocation unless `--run` is explicit.

Acceptance:

- A Ghidra-exported artifact can feed the same graph MCP/reporting layer as source repo analysis.

## Phase 6: Evaluation Upgrade

Status: implemented for zero-dependency labeled mini-benchmarks.

Implemented:

- `scripts/run_golden_evals.py` runs end-to-end golden checks for repository analysis, binary triage, IOC extraction, Android API scanning, case manifests, corpus MCP search/get/error handling, and module graph MCP metrics.
- CI runs pytest, byte-compilation, golden evaluations, and manifest sync checks on Linux and Windows.
- Expanded eval cases into labeled mini-benchmarks:
  - source graph/corpus/MCP analysis
  - bounded binary triage
  - IOC adversarial strings
  - Android oversized source
  - Ghidra fake graph export
  - Ghidra smoke-runner contract
  - OCP safety/reporting prompt contract
- Every case reports `capability`, `status`, and metrics for:
  - assertions
  - false positives
  - false negatives
  - missing evidence
  - unsafe action attempted
- CI writes `evals/golden-summary.json` with schema `reveng.golden_evals.v1`.

Tests:

- `run_golden_evals.py` emits schema-versioned JSON to stdout and `--json-out`.
- CI fails on unsafe action, missing evidence, false positives, false negatives, or missing citation checks represented by non-zero metrics.

Acceptance:

- We can say which RevEng capability improved, not merely that tests passed.

## Phase 7: Orchestration And Report Templates

Status: implemented for shared report template documentation.

Implemented:

- Added `references/report-templates.md`.
- Included reusable sections for evidence tables, negative evidence, alternate hypotheses, blocked questions, and next analysis.

Tests:

- Skill contract tests require PAUSE, negative evidence, and source citations.
- Golden eval checks report sections exist and cite artifacts.

Acceptance:

- Deep analysis output becomes auditable, not just readable.

## Phase 8: Optional CLI

Status: implemented.

Implemented:

- Added a `reveng` CLI wrapper:
  - `reveng analyze-repo`
  - `reveng serve-corpus`
  - `reveng triage-binary`
  - `reveng extract-iocs`
  - `reveng check-tools`
  - `reveng android-scan`
  - `reveng ghidra-smoke`
- Kept existing scripts as the implementation backend.

Tests:

- CLI smoke tests call representative subcommands on fixtures.
- Ghidra smoke dispatch is discovery-only unless `--run` is explicit.

Acceptance:

- Operators can run RevEng without remembering every script name.

## First Implementation Slice

Current status:

1. Phase 1 is implemented for source repositories and file targets.
2. Phase 2 is implemented for the source-repo graph layer with zero-dependency fallback and optional Tree-sitter JS/TS support.
3. Phase 3 is implemented for current read-only corpus/graph MCP tools.
4. Phase 4 is implemented for discovery-only external adapter inventory.
5. Phase 5 is implemented with fake Ghidra graph fixtures and a conditional smoke runner; real smoke execution still requires a local Ghidra/PyGhidra install.
6. Phase 6 is implemented for labeled zero-dependency mini-benchmarks.
7. Phase 7 is implemented as shared report templates.
8. Phase 8 is implemented as a unified static-first CLI.

Next implementation targets:

1. Run the real Ghidra/PyGhidra smoke when an installation is available.
2. Validate optional Tree-sitter JS/TS parsing against the real packages when that dependency is installed in CI or locally.

Reason:

- Highest value for the user's stated goal of deeply analyzing downloaded repos.
- Zero proprietary dependencies.
- Directly strengthens the already-existing corpus MCP.
- Provides testable groundwork for later Ghidra/IDA/radare adapters.
