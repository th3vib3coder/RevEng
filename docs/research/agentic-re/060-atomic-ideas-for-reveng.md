# Atomic Ideas For RevEng

Each idea is intentionally small. The upgrade plan in `070-reveng-upgrade-plan.md` groups these into implementation phases.

## Core Corpus And MCP

| ID | Idea | Source | RevEng action | Priority |
| --- | --- | --- | --- | --- |
| REI-001 | Add cursor pagination to every corpus search/list tool. | 13bm GhidraMCP, binary-ninja-headless-mcp | Extend MCP APIs with `offset`/`limit` and stable `next_offset`. | P0 |
| REI-002 | Split compact text summary from structured JSON payload. | MCP patterns in ReVa/Binja tools | Keep `content.text` compact and put full machine data in `structuredContent`. | P0 |
| REI-003 | Add structured error codes and expected schema hints. | GhydraMCP | Replace ad-hoc error text with `{code,message,expected}`. | P0 |
| REI-004 | Add read-only/idempotent tool metadata. | BinAssistMCP, Binary Ninja headless MCP | Document and expose tool safety hints where supported. | P1 |
| REI-005 | Add case manifests for reproducible analysis runs. | idac, ReVa, kernagent, agentic-malware-analysis | Emit `case_manifest.json` listing inputs, outputs, commands, versions. | P0 |

## Graph And Structure

| ID | Idea | Source | RevEng action | Priority |
| --- | --- | --- | --- | --- |
| REI-010 | Add source repository call/import graph export. | ReCopilot, HELIOS | Extend `repo_map.py` with graph edges and stable node IDs. | P0 |
| REI-011 | Add HELIOS-like graph summary schema. | HELIOS | Create `references/graph-analysis-schema.md`. | P0 |
| REI-012 | Add Ghidra CFG/FCG export fields. | ReVa, GhidraMCP variants, HELIOS | Extend `ghidra_export_summary.py` best-effort exporter. | P1 |
| REI-013 | Add graph-neighborhood MCP query. | ReVa, BinAssistMCP | Query callers/callees/import neighbors by symbol/path/function. | P1 |
| REI-014 | Add raw-vs-decompiler evidence slots. | LLM-resistant protection paper | Reports must separate raw disassembly/export evidence from pseudocode inference. | P1 |

## Optional Tool Adapters

| ID | Idea | Source | RevEng action | Priority |
| --- | --- | --- | --- | --- |
| REI-020 | Define external adapter capability schema. | idac, ida-pro-mcp, r2mcp, Binja MCP | Add `references/external-adapter-schema.md`. | P0 |
| REI-021 | Add `re_tool_check.py --json` adapter inventory. | ida-pro-mcp-plus, radare2-mcp | Emit optional tool availability and safety class. | P1 |
| REI-022 | Add deterministic `int_convert` helper. | ida-pro-mcp prompt guidance | Prevent LLM hex/endian arithmetic mistakes. | P1 |
| REI-023 | Add fake adapter fixtures for CI. | binary-ninja-headless-mcp | Test adapter consumers without proprietary tool installs. | P1 |
| REI-024 | Do not add raw eval/pass-through tools. | Binary Ninja/radare security warnings | Keep raw eval out of core RevEng. | P0 |

## Evaluation

| ID | Idea | Source | RevEng action | Priority |
| --- | --- | --- | --- | --- |
| REI-030 | Add labeled golden eval tasks per domain. | SoK, BinMetric | Expand `run_golden_evals.py` beyond one fixture. | P0 |
| REI-031 | Add Observe-Comprehend-Plan failure evals. | LLM-resistant protection paper | Test training-bias, over-trust, context-limit, plan-persistence scenarios. | P1 |
| REI-032 | Add crypto mini-evals. | CREBench | Synthetic key/IV/wrapper fixtures, no malware execution. | P2 |
| REI-033 | Score false positives and negative evidence. | SoK, RevEng parity discipline | Eval reports include FP/FN and evidence quality, not only pass/fail. | P1 |

## Safety

| ID | Idea | Source | RevEng action | Priority |
| --- | --- | --- | --- | --- |
| REI-040 | Mark extracted strings as untrusted data. | Talos MCP security discussion | Add taint fields in corpus/evidence records. | P0 |
| REI-041 | Add injection-looking string tests. | Talos, MCP threat model | Ensure corpus/MCP never treats extracted text as instructions. | P0 |
| REI-042 | Require PAUSE for build/test/container/debug execution. | RevEng safety model, Talos | Keep explicit authorization gates in all new skills. | P0 |
| REI-043 | Add network transport policy. | radare2-mcp, BinjaLattice, 13bm GhidraMCP | Stdio default; localhost+token for any future TCP/HTTP. | P1 |
| REI-044 | Add maximum result caps to docs and tests. | Binary Ninja headless MCP, 13bm GhidraMCP | Test each MCP bulk endpoint for cap enforcement. | P0 |

## Orchestration

| ID | Idea | Source | RevEng action | Priority |
| --- | --- | --- | --- | --- |
| REI-050 | Add status templates for deep analysis. | agentic-malware-analysis | Structured markdown sections for hypotheses, evidence, blockers, next actions. | P1 |
| REI-051 | Add Plan/Observe/Critique workflow without autonomous execution. | reverse-engineering-agent | Use as reporting discipline, not dynamic crackme solving. | P2 |
| REI-052 | Add guided prompts per toolchain. | BinAssistMCP, ReVa | Update skills with deterministic call order and output contract. | P1 |
| REI-053 | Keep heavy Docker toolchain separate. | decompai, agentic-malware-analysis | Document future optional sandbox pack, do not bundle. | P2 |

