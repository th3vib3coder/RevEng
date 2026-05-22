# Agentic Reverse Engineering Research Index

Date: 2026-05-22

This directory turns the current agentic reverse-engineering source survey into small, indexed design notes for RevEng upgrades. It is intentionally not a literature dump. Each note captures reusable ideas, rejects weak or risky sources, and keeps source links attached to every project or paper discussed.

## Source Policy

- Prefer primary sources: upstream GitHub repositories, official project documentation, arXiv/NDSS pages, and vendor research posts.
- Do not vendor upstream code into RevEng from this research pass.
- Treat third-party aggregators, Reddit posts, marketplace mirrors, and reverse-engineered provider proxies as secondary context only.
- Keep every actionable idea traceable to at least one source URL.
- Separate observed source facts from RevEng decisions.

## File Map

| File | Purpose |
| --- | --- |
| `001-selection-matrix.md` | Which projects/papers matter, which are only tracked, and which are discarded. |
| `010-ida-ecosystem.md` | IDA/idac/MCP ideas: agent-native CLI, batches, previews, session isolation, exact math tools. |
| `020-ghidra-ecosystem.md` | Ghidra/ReVa/GhidraMCP ideas: headless mode, context-rot control, schema tolerance, HATEOAS, pagination. |
| `030-binja-radare-ecosystem.md` | Binary Ninja and radare2 ideas: read-only defaults, transactions, fake backends, sandbox knobs. |
| `040-pipelines-and-benchmarks.md` | Agentic malware pipelines and academic evaluation targets. |
| `050-security-and-mcp-patterns.md` | MCP/agent security patterns required before adding more power. |
| `060-atomic-ideas-for-reveng.md` | Atomic upgrade ideas with source, action, and priority. |
| `070-reveng-upgrade-plan.md` | Concrete vNext upgrade plan derived from the selected ideas. |

## Current RevEng Baseline

RevEng already provides:

- Portable Codex + Claude Code plugin manifests.
- Static-first skills for source repos, binaries, Android, Ghidra, IOC extraction, unpacking, and parity review.
- Deterministic Python helpers using the standard library.
- RAG/MCP-ready source repository corpus generation.
- A read-only stdio MCP server over `repo_corpus.jsonl`.
- Golden evals and CI across Windows/Linux.
- Basic hostile-input hardening: bounded reads, deterministic outputs, symlink guarding, capped IOC output.

## Research Decisions

Use these tags across the notes:

- `ADOPT`: implement a RevEng version of the idea.
- `ADAPT`: keep the pattern but simplify it for RevEng's zero-dependency/static-first model.
- `TRACK`: valuable, but not in the immediate upgrade.
- `REJECT`: not appropriate for RevEng's safety, portability, or licensing model.

## Highest-Value Upgrade Themes

1. Graph-aware evidence: repo call/import graphs now, binary CFG/FCG later through Ghidra/export adapters.
2. Token-safe MCP: cursor pagination, compact summaries, structured content, hard caps, deterministic IDs.
3. Tool/session isolation: explicit case directories, external tool probes, no hidden ambient state.
4. Schema-tolerant errors: invalid tool inputs should return structured diagnostics, not crashes.
5. Evaluation discipline: golden evals must measure behavior, not just schema presence.
6. Safety before capability: no write/mutate/debug/run paths without PAUSE, sandbox, and rollback.

