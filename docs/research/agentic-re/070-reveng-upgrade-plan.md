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

Status: planned.

Tasks:

- Add `references/case-manifest-schema.md`.
- Add a helper to create `case_manifest.json` for repo and binary analysis outputs.
- Record input paths, hashes, script versions, output artifact paths, caps, ignored paths, and warnings.
- Update repo skill to require a case directory for deep analysis.

Tests:

- Manifest is deterministic across repeated runs.
- Manifest includes every expected artifact.
- Manifest does not include local absolute plugin paths unless explicitly reporting operator input.

Acceptance:

- A user can rerun an analysis and diff the manifest and artifacts.

## Phase 2: Graph-Aware Source Repository Analysis

Status: planned.

Tasks:

- Extend `repo_map.py` with stable graph nodes and edges:
  - file -> imports -> internal module
  - file -> symbol definitions
  - route -> handler
  - CLI entrypoint -> target callable when statically resolvable
- Extend `repo_corpus_export.py` records with `graph_refs`.
- Add MCP tools:
  - `reveng.list_graph_nodes`
  - `reveng.list_graph_edges`
  - `reveng.graph_neighbors`
- Add `references/graph-analysis-schema.md`.

Tests:

- Python AST fixture with real imports, classes, async functions, FastAPI routes, and fake docstring symbols.
- Node fixture with Express route and package scripts.
- Cross-file fixture proving internal import edges.
- MCP pagination and cap tests for graph tools.

Acceptance:

- Repo reports can cite a compact graph neighborhood instead of dumping file lists.

## Phase 3: Token-Safe MCP Hardening

Status: planned.

Tasks:

- Add standard MCP response envelope fields:
  - `case_id`
  - `result_count`
  - `offset`
  - `next_offset`
  - `truncated`
  - `warnings`
- Add structured error codes:
  - `invalid_arguments`
  - `not_found`
  - `limit_exceeded`
  - `unsupported_operation`
  - `corpus_load_error`
- Add read-only/idempotent metadata in tool descriptions.
- Add tests for injection-looking strings remaining inert data.

Tests:

- Invalid calls return `isError: true` and expected schema.
- Large result sets never exceed configured caps.
- Strings containing "ignore previous instructions" are returned as quoted evidence only.

Acceptance:

- MCP tools are predictable enough for agents to recover from mistakes without crashing or flooding context.

## Phase 4: External Adapter Schema

Status: planned.

Tasks:

- Add `references/external-adapter-schema.md`.
- Extend `re_tool_check.py --json` to report optional adapter capabilities:
  - `idac`
  - `ida-pro-mcp`
  - `r2mcp`
  - `reva`
  - `ghidra`
  - `binary-ninja-headless-mcp`
- Record safety class:
  - `read_only`
  - `mutation_preview`
  - `mutation_commit`
  - `execution`
  - `raw_eval`
- Update skills to use adapters only as optional evidence providers.

Tests:

- Fake PATH fixtures prove detection and non-detection.
- Dangerous adapter capabilities are reported but not invoked.
- Missing tools degrade gracefully.

Acceptance:

- RevEng can tell the agent what external RE infrastructure exists without coupling core functionality to it.

## Phase 5: Ghidra Graph Export

Status: planned.

Tasks:

- Extend `ghidra_export_summary.py` to emit best-effort:
  - function list
  - imports/exports
  - strings
  - xrefs
  - function call graph
  - basic block CFG per selected function
  - decompiler warnings
- Add HELIOS-style compact text graph summaries.
- Keep all fields optional with warnings when Ghidra APIs are unavailable.

Tests:

- Syntax compile test outside Ghidra.
- Fake Ghidra object fixture for CFG/FCG serialization.
- Golden fixture for graph summary formatting.

Acceptance:

- A Ghidra-exported artifact can feed the same graph MCP/reporting layer as source repo analysis.

## Phase 6: Evaluation Upgrade

Status: planned.

Tasks:

- Expand `evals/` into labeled mini-benchmarks:
  - source graph
  - MCP pagination
  - IOC adversarial strings
  - Android oversized source
  - Ghidra fake graph export
  - OCP failure-mode prompts
- Score:
  - pass/fail
  - false positives
  - false negatives
  - missing evidence
  - unsafe action attempted
- Add JSON eval output for CI artifacts.

Tests:

- `run_golden_evals.py` emits both human markdown and JSON summary.
- CI fails on unsafe action or missing citation.

Acceptance:

- We can say which RevEng capability improved, not merely that tests passed.

## Phase 7: Orchestration And Report Templates

Status: planned.

Tasks:

- Add `references/report-templates.md`.
- Add status templates:
  - `triage_status.md`
  - `hypotheses.md`
  - `evidence_table.md`
  - `blocked_questions.md`
  - `next_analysis.md`
- Update router and repo/binary skills to produce case-based reports.
- Add "negative evidence" and "alternate hypotheses" sections.

Tests:

- Skill contract tests require PAUSE, negative evidence, and source citations.
- Golden eval checks report sections exist and cite artifacts.

Acceptance:

- Deep analysis output becomes auditable, not just readable.

## Phase 8: Optional CLI

Status: later.

Tasks:

- Add a `reveng` CLI wrapper:
  - `reveng analyze-repo`
  - `reveng serve-corpus`
  - `reveng triage-binary`
  - `reveng extract-iocs`
  - `reveng check-tools`
- Keep existing scripts as the implementation backend.

Tests:

- CLI smoke tests call each subcommand on fixtures.
- CLI output paths are deterministic.

Acceptance:

- Operators can run RevEng without remembering every script name.

## First Implementation Slice

Start here:

1. Phase 1 case manifest schema and repo case manifest output.
2. Phase 2 source repository graph nodes/edges.
3. Phase 3 MCP structured errors and graph tools.

Reason:

- Highest value for the user's stated goal of deeply analyzing downloaded repos.
- Zero proprietary dependencies.
- Directly strengthens the already-existing corpus MCP.
- Provides testable groundwork for later Ghidra/IDA/radare adapters.

