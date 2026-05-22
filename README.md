# RevEng

RevEng is a portable reverse-engineering plugin for Codex and Claude Code. It is designed for authorized defensive analysis of unfamiliar source repositories, binaries, Android applications, Ghidra analysis projects, IOC evidence, packed samples, and recovered/decompiled code.

The plugin is intentionally **static-first**. It can inspect files, manifests, logs, strings, decompiled source, and analysis outputs, but it does not execute untrusted samples or repository code unless an operator explicitly approves a sandboxed execution step.

## What RevEng Does

RevEng provides an agent with repeatable workflows and deterministic helper scripts for common reverse-engineering tasks:

- Deep source repository reverse engineering with architecture reports and RAG/MCP-ready corpus exports.
- Static binary triage with hashes, file-type guesses, entropy, printable strings, and optional local tool output.
- Evidence-first IOC extraction from strings, sandbox logs, proxy logs, EDR notes, decompiled snippets, and analyst notes.
- Static-first packing and obfuscation assessment, including safe unpacking plans and explicit sandbox gates.
- Android reverse engineering for decompiled APK/XAPK/JAR/AAR source trees, including API endpoint extraction.
- Ghidra and PyGhidra headless workflow guidance for repeatable static binary analysis.
- Recovered-code parity review between decompiled/recovered functions and candidate source code.

## Safety Model

RevEng is meant for lawful work such as incident response, malware triage, forensics, interoperability research, software audit, education, and CTF-style analysis.

RevEng does **not** automatically:

- run unknown binaries
- run repository scripts, tests, package managers, or containers
- contact suspected infrastructure
- validate live indicators
- install reverse-engineering tools
- modify malware or produce evasion guidance

If a workflow would require execution, the skill must stop with a gate like:

> PAUSE: This step requires executing untrusted code or contacting external infrastructure. Confirm authorization, sandbox, network posture, snapshot/rollback state, exact command, and output path before continuing.

## Plugin Layout

RevEng supports both plugin ecosystems in one repository:

- `.codex-plugin/plugin.json` for Codex.
- `.claude-plugin/plugin.json` for Claude Code.
- `skills/*/SKILL.md` shared by both agents.
- `scripts/*.py` shared deterministic helpers.
- `references/*.md` shared schemas, playbooks, provenance, and safety documentation.
- `tests/` contract and behavior tests.

No third-party source code is vendored. The implementation uses original Python standard-library scripts and documents the upstream projects that informed the design in `references/source-provenance.md`.

## Skills

### `reverse-engineering`

Router skill for broad or ambiguous reverse-engineering requests. It chooses the narrowest available workflow:

- source repo analysis
- binary triage
- IOC extraction
- unpacking assessment
- Android API extraction
- Ghidra headless analysis
- recovered-code parity review

### `repo-reverse-engineering`

Analyzes downloaded or cloned source repositories without running their code.

It maps:

- apparent purpose
- directory structure and major modules
- entrypoints and main flows
- package manifests and dependency surfaces
- Python internal module graph from static imports
- API, CLI, MCP, plugin, and service surfaces
- CI, Docker, config, and test/build strategy
- static supply-chain and execution-risk signals

It emits:

- `case_manifest.json`
- `repo_inventory.json`
- `repo_map.json`
- `repo_corpus.jsonl`
- a Markdown report written by the agent from the structured evidence

The JSONL corpus is ready for downstream RAG/MCP ingestion. RevEng also ships a read-only stdio MCP server over that corpus for agentic querying with cursor pagination, structured outputs, and a uniform result metadata envelope.

### `binary-triage`

Performs static triage of unknown binaries, including PE, ELF, Mach-O, DLL/shared library files, firmware blobs, ZIP/APK/JAR-like archives, and other opaque files.

It collects:

- MD5, SHA1, SHA256
- size
- file-type guess from magic bytes
- entropy overall and by chunk
- printable ASCII strings preview
- optional output from installed static tools such as `file`, `objdump`, and `readelf`

It never executes the sample.

### `ioc-extraction`

Extracts indicators only from evidence that exists in the input.

Supported indicator families include:

- MD5, SHA1, SHA256
- URLs, defanged URLs, domains, IPv4 addresses
- email addresses
- Windows registry keys
- Windows file paths
- User-Agent strings

Every emitted IOC includes:

- `value`
- `confidence`
- `source`
- `evidence_snippet`

Defanged and normalized variants are emitted as separate records when the normalization is reversible, for example `hxxps://Bad[.]Example/path` and `https://bad.example/path`.

### `unpacking-analysis`

Assesses whether a sample appears packed or obfuscated using static evidence:

- high entropy
- sparse strings
- unusual sections
- minimal imports
- packer signatures
- UPX markers
- provided sandbox notes

It produces a safe unpacking plan. Dynamic unpacking is not performed automatically and requires a sandbox gate.

### `android-reverse-engineering`

Supports Android reverse-engineering workflows around APK/XAPK/JAR/AAR files and decompiled source trees.

The implemented helper scans decompiled source for:

- Retrofit annotations
- OkHttp URL builders
- Volley request patterns
- hardcoded base URLs
- auth/header/token evidence
- source file and line references

The skill also guides manifest inspection, permission review, and UI-to-network call-flow tracing.

### `ghidra-headless`

Guides repeatable static analysis with a local Ghidra or PyGhidra installation.

RevEng does not bundle Ghidra. The included `ghidra_export_summary.py` is a safe wrapper that exits cleanly outside a Ghidra runtime and can emit a JSON program summary when run in a compatible Ghidra/PyGhidra context.

### `re-parity-review`

Compares recovered or decompiled functions against candidate source implementations.

It requires multiple independent signals:

- names or symbols
- constants
- string references
- call count
- control-flow shape
- data structure access
- error paths
- side effects
- imports/API use
- negative evidence

It forbids accepting parity from a name alone, one shared string alone, or model intuition without source-backed evidence.

## Helper Scripts

Run scripts from the repository root.

### Repository Analysis

```bash
mkdir -p case
python3 scripts/repo_inventory.py /path/to/repo --json-out case/repo_inventory.json
python3 scripts/repo_map.py /path/to/repo --json-out case/repo_map.json
python3 scripts/repo_corpus_export.py /path/to/repo --repo-map case/repo_map.json --jsonl-out case/repo_corpus.jsonl
python3 scripts/case_manifest.py --case-dir case --target /path/to/repo \
  --artifact repo_inventory=case/repo_inventory.json \
  --artifact repo_map=case/repo_map.json \
  --artifact repo_corpus=case/repo_corpus.jsonl \
  --cap repo_corpus_max_file_bytes=500000
```

Serve the generated corpus over a read-only MCP stdio server:

```bash
python3 scripts/repo_corpus_mcp.py --corpus case/repo_corpus.jsonl
```

The server exposes:

- `reveng.corpus_summary`
- `reveng.get_record`
- `reveng.graph_neighbors` (requires `--repo-map repo_map.json`; returns adjacent graph nodes and edges for one node id)
- `reveng.list_graph_edges` (requires `--repo-map repo_map.json`; filters general repo graph edges by kind/source/target)
- `reveng.list_graph_nodes` (requires `--repo-map repo_map.json`; filters general repo graph nodes by kind/query)
- `reveng.list_symbols`
- `reveng.module_graph` (requires `--repo-map repo_map.json`; returns internal edges, external imports, hard-capped fan-in/fan-out metrics, and cycles)
- `reveng.search_corpus`

Pass `--repo-map case/repo_map.json` to also enable module-graph and general repo-graph queries:

```bash
python3 scripts/repo_corpus_mcp.py --corpus case/repo_corpus.jsonl --repo-map case/repo_map.json
```

Each tool returns compact text plus `structuredContent`, uses hard-capped pagination, and returns validation failures as tool-visible structured errors.

### Binary Triage

```bash
python3 scripts/static_triage.py /path/to/sample --json-out sample.triage.json
```

### IOC Extraction

```bash
python3 scripts/ioc_extract.py evidence.txt --json-out iocs.json
```

### Android API Scan

```bash
python3 scripts/android_api_scan.py /path/to/decompiled/sources --json-out android_api.json
```

### Tool Availability Check

```bash
python3 scripts/re_tool_check.py --json
```

The JSON output includes ordinary static tool availability plus optional external adapter inventory under `adapters`. Adapter discovery is PATH lookup only: RevEng does not start IDA, Ghidra, radare2, Binary Ninja, MCP servers, debuggers, containers, or raw eval surfaces during this check.

### Ghidra Summary Export

```bash
python3 scripts/ghidra_export_summary.py --json-out ghidra_summary.json
```

On Windows, use `python` if `python3` is not available.

## Output Schemas

Schema and reporting documentation lives in `references/output-schemas.md`, `references/repo-analysis-schema.md`, `references/graph-analysis-schema.md`, `references/external-adapter-schema.md`, and `references/report-templates.md`.

Important outputs:

- `case_manifest.json`: deterministic case index with analyzed target hash, artifact hashes, caps, helper-script hashes, ignored directories, warnings, and static-first safety posture.
- `repo_inventory.json`: repository file inventory, language counts, manifest list, hashes.
- `repo_map.json`: entrypoints, dependencies, routes, plugin surfaces, configs, imports, Python module graph, general evidence graph, risks, limitations.
- `repo_corpus.jsonl`: one JSON record per included file with path, kind, language, SHA256, summary, symbols, imports, evidence excerpts, and optional `graph_refs`.
- `repo_corpus_mcp.py`: read-only stdio MCP server for querying `repo_corpus.jsonl`.
- `sample.triage.json`: binary hash/type/entropy/strings/tool-output report.
- `iocs.json`: grouped traceable IOC report.
- `android_api.json`: Android API surface report.
- `ghidra_summary.json`: Ghidra static summary, xrefs, call graph, and CFGs when run in Ghidra/PyGhidra.
- `re_tool_check.py --json`: local static tool and optional external adapter inventory with safety classes.

## Installation

### Codex

This repository is a local Codex plugin because it contains:

```text
.codex-plugin/plugin.json
skills/
scripts/
references/
```

Install or link it through the Codex app/plugin marketplace flow for local plugins.

### Claude Code

This repository also contains:

```text
.claude-plugin/plugin.json
skills/
scripts/
references/
```

Add it as a local Claude Code plugin or vendor it into the plugin directory used by your Claude Code installation.

## Development

Run all tests:

```bash
python3 -m pytest tests -q
```

Run end-to-end golden evaluations:

```bash
python3 scripts/run_golden_evals.py
```

Validate the Codex plugin manifest:

```bash
python3 /path/to/validate_plugin.py /path/to/RevEng
```

The test suite covers:

- dual manifest contracts
- skill frontmatter and router coverage
- static repo inventory/map/corpus exports
- binary triage
- IOC extraction
- Android API scan
- Ghidra wrapper behavior outside Ghidra
- absence of local absolute paths in shipped files
- golden end-to-end workflow invariants for repository analysis, binary triage, IOC extraction, and Android API scanning
- stdio MCP corpus tool discovery, paginated query behavior, split text/structured responses, and tool-visible schema errors

## Limitations

- Static analysis can miss dynamic imports, generated code, runtime routes, packed payloads, encrypted configs, or behavior hidden behind execution.
- Ghidra analysis requires a local Ghidra/PyGhidra installation.
- Android decompilation requires external tools such as `jadx`; RevEng only scans decompiled output.
- IOC extraction does not perform live validation or enrichment.
- Dynamic unpacking and runtime testing require explicit sandbox approval.

## License

MIT. See `LICENSE`.
