# RevEng

**RevEng is a portable, static-first reverse-engineering plugin for Codex and Claude Code.** It gives an AI agent a coherent, repeatable set of workflows — and a small library of deterministic Python helpers — for analyzing unfamiliar source repositories, opaque binaries, Android applications, IOC evidence, packed samples, recovered/decompiled code, and Ghidra projects. Everything ships in one repository that both agents can install and use the same way.

The plugin's defining property is that **it never executes the artifact it is analyzing**. It will read, hash, parse, scan, map and describe — but it will not run an unknown binary, install dependencies, invoke a package manager, contact suspected infrastructure, or evaluate untrusted code. The one place where it can launch an external analyzer at all (Ghidra's headless static analyzer) is gated behind an explicit operator flag and is documented as such in every output it produces. This is not an aesthetic choice; it is the only sound default for a tool that an LLM will drive autonomously on input the user does not yet trust.

## Why "static-first" matters

Agentic reverse engineering puts a model in a position to act, not just describe. If the action surface includes "run this binary" or "fetch from this URL," a single bad inference becomes a security incident — sandbox escape, exfiltration, lateral movement. Static-first inverts that risk: every workflow assumes the input is hostile until the operator has personally moved the analysis into an isolated environment. The agent can still recommend dynamic steps and produce a sandbox plan; it simply cannot take those steps on its own. The cost is real (no runtime behavior is observed), but the trust model is tractable.

A second consequence of static-first is that RevEng's value lies less in "reverse engineering" in the classical sense (recovering meaning from compiled artifacts without source) and more in **structured comprehension** of whatever input is given. For an open-source repository, that comprehension *is* the audit; for a stripped binary, it is static triage and Ghidra-driven inspection. The plugin reflects both modes.

## What it actually does

When pointed at a **source repository** (cloned from GitHub, downloaded, or sitting locally), RevEng produces a self-contained case directory: an inventory of every file with language and hashes; an architecture map of entrypoints, dependencies, package manifests, routes, configs, plugins, and supply-chain risk signals; a Python module dependency graph built from AST imports — including correct handling of `src/`-layout packages — and an analogous JavaScript/TypeScript graph built from relative imports (using Tree-sitter when available, or a comment-aware static scanner when not); a general evidence graph that ties files, modules, symbols, routes, entrypoints, dependencies, plugins, and external imports into one queryable structure with per-module fan-in/fan-out and import-cycle detection; a per-file JSONL corpus with symbols, imports, summary, line-anchored evidence excerpts, and graph references; and a deterministic case manifest that records the analyzed target's content hash, every artifact's size and SHA-256, helper script hashes, traversal ignore rules, and an explicit static-first safety posture. The corpus is RAG-ready, and the same case can be served over a read-only MCP stdio server so an agent can interrogate it tool-by-tool with hard-capped pagination and a uniform result envelope.

When pointed at a **binary**, RevEng computes MD5/SHA-1/SHA-256 across the full file, guesses the file type from magic bytes, measures overall and per-chunk entropy, extracts printable strings, and optionally captures the output of standard local tools (`file`, `objdump`, `readelf`, `otool`, ...) when they exist on the path. Reads are bounded so an oversized or hostile sample cannot exhaust memory; hashes still cover the whole file via streaming. The sample itself is never executed, only read.

For **IOC evidence** (logs, strings, decompiled snippets, analyst notes), RevEng extracts hashes, URLs (defanged and refanged), IPv4 addresses with version-string suppression, emails, registry keys, file paths, and User-Agent strings. Every indicator carries a verbatim `evidence_snippet`, a `confidence`, and the source file/line so the report is traceable end-to-end. Inputs are read in bounded chunks with per-line truncation; output is capped per category and explicitly flagged `truncated: true` whenever a cap or an overlong line clipped evidence.

For **Android source trees** (decompiled with `jadx`, `apktool`, or equivalent), RevEng scans for Retrofit annotations, OkHttp URL builders, Volley request patterns, hardcoded base URLs, auth/header/token markers, and the file-and-line where each appeared. Oversized files and symlinks are skipped with a recorded reason; nothing in the tree is executed.

For **Ghidra workflows**, RevEng provides a wrapper that runs inside Ghidra or PyGhidra to export program metadata, functions, imports, exports, strings, an analysis call graph, and per-function CFG blocks/edges. It also ships a smoke runner that performs discovery-only by default and only launches `analyzeHeadless` when invoked explicitly with `--run` and a sample path — Ghidra still performs *static* analysis of the binary; the binary is not executed by RevEng or by Ghidra.

For **recovered or decompiled code** to be compared against candidate source, RevEng provides a parity-review workflow with explicit anti-false-positive rules: matches require multiple independent signals (symbols, constants, strings, call counts, control-flow shape, data-structure access, error paths, imports, negative evidence), and parity is forbidden from a single name or a single shared string.

## Use cases at a glance

| Scenario | What you run | What you get back |
|---|---|---|
| Audit an open-source repo before adopting or porting code | `reveng analyze-repo <repo> --out case/` | Full static case directory + MCP-queryable corpus |
| Triage an unknown binary received in IR | `reveng triage-binary <sample> --out triage.json` | Hashes, type, entropy profile, strings, optional tool outputs |
| Extract IOCs from a sandbox/EDR/proxy log | `reveng extract-iocs evidence.txt --out iocs.json` | Grouped IOCs with evidence snippets and traceability |
| Map an APK's API surface from decompiled source | `reveng android-scan decompiled/ --out android.json` | Endpoints, base URLs, auth markers, file:line |
| Check what local RE tools / MCP adapters are available | `reveng check-tools --json` | Tool paths and external adapter safety classes (discovery only) |
| Run a real Ghidra smoke on a benign file (with Ghidra installed) | `reveng ghidra-smoke --run --sample <bin> --json-out smoke.json` | Status, return code, exported summary, explicit policy record |
| Let an agent query a case interactively | `reveng serve-corpus case/repo_corpus.jsonl --repo-map case/repo_map.json` | MCP server over stdio with eight read-only tools |

## Quick start

Clone the repository, then run an analysis from the repo root:

```bash
git clone https://github.com/th3vib3coder/RevEng.git
cd RevEng
python3 scripts/reveng.py analyze-repo /path/to/some/repo --out case/
```

On Windows, use `python` if `python3` is not available. No third-party Python packages are required for the default workflows; the helpers run on Python 3.10+.

To install RevEng as a local plugin for either agent, see the [Installation](#installation) section below; both `.codex-plugin/` and `.claude-plugin/` manifests are already in this repository.

## The unified `reveng` CLI

`scripts/reveng.py` is a single, static-first entry point that dispatches to the helper scripts in this repository. It only launches RevEng's own helpers — never the analyzed sample, repository code, or external adapter — and inherits stdio so subcommand output passes through cleanly.

| Subcommand | Purpose |
|---|---|
| `analyze-repo` | Run inventory then map then corpus (with `--repo-map` so each record gets `graph_refs`) then `case_manifest` in one call |
| `triage-binary` | Static binary triage with bounded reads and streamed hashes |
| `extract-iocs` | Defensive IOC extraction with bounded reads and per-category caps |
| `android-scan` | Decompiled-Android source scan |
| `check-tools` | Detect local RE tools and the optional external adapter inventory (PATH only) |
| `serve-corpus` | Serve a `repo_corpus.jsonl` over the read-only stdio MCP server |
| `ghidra-smoke` | Discovery-only Ghidra smoke; launches `analyzeHeadless` only with `--run` |

Example end-to-end repository audit:

```bash
python3 scripts/reveng.py analyze-repo ./auto-re-agent --out case/
python3 scripts/reveng.py serve-corpus case/repo_corpus.jsonl --repo-map case/repo_map.json
```

The first command writes `case/repo_inventory.json`, `case/repo_map.json`, `case/repo_corpus.jsonl`, and `case/case_manifest.json`. The second turns that case into an interactive MCP server an agent can query.

## What you get back: the case directory

A typical `analyze-repo` run produces four deterministic JSON artifacts. The plugin is reproducible by design — given the same input, repeated runs produce byte-identical outputs (no wall-clock timestamps are written unless explicitly requested).

**`repo_inventory.json`** is the structural overview: per-file path, size, SHA-256, language, kind (`source`, `manifest`, `plugin_manifest`, `config`, `docs`, `test`, or `other`), and a boolean indicating whether the content looked like text. It aggregates file counts and bytes per language, lists detected manifests, and records the traversal ignore set so the boundary of analysis is explicit.

**`repo_map.json`** is the architecture: entrypoints recovered from `pyproject.toml`, `package.json`, and similar manifests; dependency declarations across Python and Node ecosystems; route candidates pulled via Python AST decorators and a JavaScript/TypeScript scanner that skips comments and strings; plugin manifest surfaces (Codex `.codex-plugin/`, Claude Code `.claude-plugin/`, MCP `.mcp.json`); CI, Docker, and env-file configs; per-file import lists; static supply-chain and execution-risk observations (postinstall/preinstall scripts, fetch-like tokens in manifests, secret-like patterns in env files); a Python module dependency graph with `modules`, `edges`, `external_imports`, and a `metrics` block carrying per-module `fan_in`/`fan_out` plus import `cycles` detected via iterative Tarjan SCC; an analogous JavaScript/TypeScript graph (using Tree-sitter when installed); and a unified general evidence graph that ties everything together.

**`repo_corpus.jsonl`** is one JSON record per included file: `path`, `kind`, `language`, `sha256`, a one-line `summary`, statically extracted `symbols`, `imports`, line-anchored `evidence` excerpts, and `graph_refs` pointing to the relevant nodes and edges in the general graph. Binary files and oversized files are skipped with a recorded threshold. This file is designed to be consumed by a downstream RAG/MCP system.

**`case_manifest.json`** is the reproducibility index: `schema` (`reveng.case_manifest.v1`), a `case_id` derived deterministically from the analyzed target's content hash plus caps plus schema, a `target` record with the operator-provided path, its type (`directory` or `file`), and a deterministic content hash, every artifact's name/path/kind/size/SHA-256, the helper-script hashes in use, the ignored-directory list, and an explicit `safety` block declaring `static_first: true`, `executed_target_code: false`, `network_contacted: false`. Two different operators analyzing the same content get the same `case_id`, regardless of where the output directory lives.

## The MCP corpus server

`scripts/repo_corpus_mcp.py` is a read-only stdio MCP server over the case directory. It speaks JSON-RPC 2.0 with batch support and exposes eight tools: `corpus_summary`, `search_corpus`, `get_record`, `list_symbols`, `module_graph`, `list_graph_nodes`, `list_graph_edges`, and `graph_neighbors`. Every tool returns a compact text summary alongside full `structuredContent`, every paginated tool uses cursor-based pagination with hard caps, and every result wraps a uniform metadata envelope (`result_count`, `offset`, `next_offset`, `truncated`, `warnings`). Argument validation failures come back as tool-visible structured errors with codes (`invalid_arguments`, `not_found`, `graph_unavailable`) so the calling agent can correct itself without dropping protocol state.

The server only reads the corpus JSONL and the optional `--repo-map` JSON. It does not run any code in the analyzed repository, does not contact the network, and treats every string in the corpus — including anything that looks like a prompt — strictly as data.

Start the server with:

```bash
python3 scripts/reveng.py serve-corpus case/repo_corpus.jsonl --repo-map case/repo_map.json
```

## Skills

RevEng ships eight skills under `skills/`, each as a `SKILL.md` shared by both Codex and Claude Code.

- **`reverse-engineering`** is the router. It picks the narrowest workflow for the request and enforces static-first guardrails everywhere.
- **`repo-reverse-engineering`** is the deep-audit engine for downloaded source repositories.
- **`binary-triage`** runs static triage on unknown binaries.
- **`ioc-extraction`** extracts traceable defensive IOCs from evidence text.
- **`unpacking-analysis`** assesses packing/obfuscation static-first and produces a safe unpacking plan; dynamic unpacking is sandbox-gated.
- **`android-reverse-engineering`** maps API surfaces in decompiled Android source.
- **`ghidra-headless`** guides repeatable Ghidra/PyGhidra static workflows.
- **`re-parity-review`** compares recovered code to candidate source with anti-false-positive rules.

The skill markdown is what makes RevEng usable from inside an agent: each file documents inputs, expected outputs, guardrails, and the exact command(s) the agent should run.

## Architecture and implementation notes

A handful of design choices distinguish RevEng from a bag of regex scripts. Each one has been validated on real repositories — most notably on `meyz664K/auto-re-agent` and `expressjs/express`, used as live targets during development.

**Python analysis goes through the AST**, not line-anchored regexes. Symbols, imports, and route decorators are extracted via `ast.walk`, with a regex fallback only when `ast.parse` raises `SyntaxError`. The practical consequence is that definitions hidden inside docstrings, string literals, or comments are not falsely surfaced as real code. A unit and golden eval guard this: a smuggled `def smuggled_symbol():` inside a module docstring must never appear in the corpus.

**`src/`-layout repositories are detected and renamed correctly.** When a `pyproject.toml` declares `tool.setuptools.packages.find.where = ["src"]`, `tool.setuptools.package-dir`, or `tool.hatch.build.targets.wheel.packages`, or when `src/` simply contains a package directory with `__init__.py`, RevEng treats `src/` as the import root. Modules are named `re_agent.core.models`, not `src.re_agent.core.models`, so internal imports like `from re_agent.core.models import ...` resolve correctly. On a real repository this turned a `module_graph.edges` count of zero into one hundred and thirty-two.

**JavaScript and TypeScript route and import extraction is comment-aware and quote-aware** even without Tree-sitter. A small hand-rolled scanner walks the source, skips `//` and `/* ... */` blocks, skips string literals (including template strings, recognizing escapes), and only matches `app.get( ... )` / `router.post( ... )` patterns at non-identifier boundaries — so `myapp.get(...)` never produces a false route. Tree-sitter, if installed via `pip install -r requirements-optional.txt`, replaces the scanner with a real parser; the same tests cover both paths.

**Reads are bounded across every input path.** `static_triage` reads up to `--max-read-bytes` (default 64 MiB) for entropy/strings/type while hashes still stream the full file. `repo_common.read_text` and `android_api_scan` open files with `open().read(max_bytes)` rather than slicing whole-file reads. `ioc_extract` uses `readline(max+1)` with bounded drain, so a single multi-gigabyte newline-free line cannot blow up memory. Every cap is reflected in the output (`bytes_analyzed`, `truncated`, `skipped_files`).

**The IOC extractor dedupes in O(1) per call.** A persistent per-category `seen` set replaces the original O(n^2) rebuild, and the per-category hard cap (1000) flips a top-level `truncated: true` when it kicks in, so a flooded input never silently truncates evidence.

**Symlinks are excluded from repository walks.** `iter_repo_files` uses `os.walk(followlinks=False)` and explicitly skips symlinked files. The scanner cannot be tricked into reading content outside the analyzed directory via a planted symlink — a relevant property when the input is a malicious or compromised package.

**Outputs are deterministic by default.** `repo_inventory.json` does not embed a wall-clock timestamp (use `--generated-at` to opt in); cycles, fan-in/fan-out, and modules are sorted; the case manifest's `case_id` is content-addressed. Running `analyze-repo` twice on the same input produces byte-identical artifacts.

**The plugin is portable across Codex and Claude Code.** A single repository carries both `.codex-plugin/plugin.json` and `.claude-plugin/plugin.json`; the skill bodies, scripts, and references are shared. There is no platform-specific code path in any helper.

**No subprocess can run an analyzed artifact.** A grep across all scripts shows three uses of `subprocess`: `static_triage.py` runs only whitelisted local tools (`file`, `objdump`, `readelf`) with the sample as an argument; `reveng.py` spawns only this repository's own helper scripts; `run_golden_evals.py` is the evaluation harness. There is no shell invocation of operating-system commands, no raw code evaluation, and no network use (`socket`, `urllib`, `requests`) anywhere in the helpers. The one place that can spawn an *external analyzer* is `ghidra_smoke.py --run`, and only with explicit operator approval; even then, Ghidra performs static disassembly, not execution.

## Safety model

RevEng is intended for lawful work: incident response, malware triage, forensics, interoperability research, software audit, education, CTF analysis. Outside of those scopes it should not be used; the skills include explicit "disallowed" sections covering modifying malware, producing evasion guidance, fabricating indicators, contacting live infrastructure without authorization, or running unknown samples.

By default, RevEng will not:

- run unknown binaries or repository code
- run package managers, installers, build systems, tests, or containers from the analyzed input
- contact suspected infrastructure or validate live indicators
- install or auto-start external analyzers, MCP servers, debuggers, or raw eval surfaces
- modify malware or output anything resembling evasion guidance

When a workflow requires execution, the corresponding skill stops at a `PAUSE` gate: it tells the operator exactly what would run, where, with what side effects, and waits for explicit approval before continuing. The Ghidra smoke runner enforces this in code: without `--run`, it never spawns a subprocess.

Even with `--run`, a hostile sample being parsed by Ghidra is not zero-risk — input parsers can have bugs of their own. For untrusted artifacts, the operator should still execute the smoke inside an isolated VM or sandbox.

## External tools and adapters

`reveng check-tools --json` produces two layers of inventory. The first is the traditional list of static tools detected on `PATH` (`file`, `objdump`, `readelf`, `otool`, `diec`, `capa`, `floss`, `yara`, `upx`, `jadx`, `apktool`, `analyzeHeadless`, `pyghidra`). The second is an inventory of recognized agent-driven external adapters — Trail of Bits' `idac`, the `ida-pro-mcp` family, `r2mcp`, ReVa, Ghidra, the headless Binary Ninja MCP — annotated with safety classes:

- `read_only` — enabled by default
- `mutation_preview` — show a dry run, do not commit
- `mutation_commit` — requires `PAUSE` and operator approval
- `execution` — requires `PAUSE` and sandbox approval
- `raw_eval` — equivalent to running arbitrary code; requires `PAUSE`

Detection is `shutil.which` only. RevEng never starts an adapter, never connects to a server, and never executes an adapter capability on the operator's behalf. The inventory exists so the agent can plan, not act.

## Optional dependencies

The default workflows run on a clean Python 3.10+ install with no third-party packages. Optional enhancements:

- **Tree-sitter** for JavaScript and TypeScript graphs. `pip install -r requirements-optional.txt` installs `tree_sitter`, `tree_sitter_javascript`, and `tree_sitter_typescript`. The same code paths work without them.
- **Local system tools** for richer binary triage (`file`, `objdump`, `readelf`, `otool`). RevEng records them as unavailable when missing and does not require them.
- **Ghidra and/or PyGhidra** for actual binary headless analysis. RevEng does not download or install Ghidra; it discovers it via `GHIDRA_HOME`, `GHIDRA_ANALYZE_HEADLESS`, or `PATH`, and only spawns it from `ghidra_smoke --run`.

## Installation

### As a Codex plugin

This repository contains `.codex-plugin/plugin.json` plus `skills/`, `scripts/`, and `references/`, which is the layout Codex expects for a local plugin. Install or link it through the Codex local-plugin flow. The validator script bundled with the Codex `plugin-creator` skill can confirm the manifest:

```bash
python3 /path/to/validate_plugin.py /path/to/RevEng
```

### As a Claude Code plugin

The same repository contains `.claude-plugin/plugin.json` plus the auto-discovered `skills/`, `scripts/`, and `references/` directories. Add it as a local Claude Code plugin or vendor it into the plugin directory that your Claude Code installation reads.

Because the skill markdown, scripts, and references are shared between the two manifests, both agents see and run the exact same workflows.

## Development

Run the test suite:

```bash
python3 -m pytest tests -q
```

The suite covers dual-manifest contracts, skill frontmatter and router coverage, static repo inventory/map/corpus exports, binary triage, IOC extraction with FP-precision cases, Android API scanning, Ghidra wrapper behavior outside Ghidra plus fake-object graph export, the Ghidra smoke-runner contract (including discovery-only skip), absence of local absolute paths or platform-specific commands in shipped files, golden end-to-end workflow invariants with labeled FP/FN/missing-evidence/unsafe-action metrics, and stdio MCP corpus tool discovery, paginated query behavior, split text/structured responses, and tool-visible schema errors.

Run the end-to-end golden evaluations:

```bash
python3 scripts/run_golden_evals.py
```

Emit the CI-readable evaluation summary:

```bash
python3 scripts/run_golden_evals.py --json-out evals/golden-summary.json
```

Validate the Codex manifest:

```bash
python3 /path/to/validate_plugin.py /path/to/RevEng
```

CI runs on every push and pull request across Ubuntu and Windows on Python 3.10 and 3.12 (see `.github/workflows/ci.yml`).

## Output schema reference

Detailed schemas live in `references/`:

- `output-schemas.md` — top-level output contracts for every helper
- `repo-analysis-schema.md` — fields for `repo_inventory.json`, `repo_map.json`, `repo_corpus.jsonl`
- `graph-analysis-schema.md` — the general evidence graph node and edge taxonomy
- `case-manifest-schema.md` — `case_manifest.json` fields and the `case_id` derivation
- `external-adapter-schema.md` — adapter inventory and safety classes
- `report-templates.md` — evidence-table, hypothesis, negative-evidence, and blocker templates the agent uses when writing reports
- `safety-scope.md` — allowed/disallowed work and the PAUSE template
- `toolchain.md` — required, optional, and workflow-specific tools
- `source-provenance.md` — inspected sources with commit hashes and licenses

## Provenance and inspirations

RevEng was designed from inspected public reverse-engineering skill and tool repositories. No third-party source code is vendored. The implementation is original Python standard-library code; the upstream projects whose ideas informed it are credited below with the commit hashes they were read at:

- `hackersifu/reverse-engineering-skills` @ `5e675640` (MIT) — evidence-first IOC extraction, static-first unpacking
- `SimoneAvogadro/android-reverse-engineering-skill` @ `6a31ed3f` (Apache-2.0) — Android decompile/API extraction
- `Arteriogramtrombiculiasis120/claude-code-reverse-engineering` @ `d0929746` (MIT) — architecture-first documentation and plugin-system analysis
- `meyz664K/auto-re-agent` @ `78b489e1` (MIT) — backend abstraction and reverser/checker parity ideas
- `NationalSecurityAgency/ghidra` — Ghidra and PyGhidra conceptual reference for headless workflows

See `references/source-provenance.md` for the full list and reuse policy.

## Limitations

Static analysis is honest about what it can and cannot see. It can miss dynamic imports, runtime route registration, generated code, packed payloads, encrypted configs, and any behavior that only appears at execution time. Ghidra requires its own installation and the real smoke test requires a Ghidra-equipped machine. Android decompilation requires `jadx` (or equivalent) to produce the source tree that RevEng then scans. IOC extraction does not perform live validation or enrichment. Dynamic unpacking and runtime testing are out of scope without an explicit, operator-approved sandbox. JavaScript/TypeScript graphs do not currently resolve TypeScript path aliases (`tsconfig.paths`) or `node_modules` imports. For any artifact whose source ships in a separate compiled form (a vendored `.so`/`.dll`/wasm, a stripped binary, obfuscated minified code), the appropriate companion is the binary side of RevEng or a true RE tool; the repo-analysis side is a deep audit engine, not a decompiler.

## License

MIT. See `LICENSE`.
