# Reverse Engineering Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete Codex plugin for defensive, authorized reverse engineering workflows covering binary triage, IOC extraction, unpacking assessment, Android API extraction, Ghidra/PyGhidra headless analysis, and adversarial parity review.

**Architecture:** The plugin is a small suite of focused skills plus deterministic helper scripts. A router skill chooses the correct workflow, specialized skills define analyst procedures and output contracts, and Python scripts collect static evidence without executing unknown samples. Ghidra is integrated as an external local tool via `analyzeHeadless` or PyGhidra; it is not bundled.

**Tech Stack:** Codex plugin manifest, Codex skill markdown, Python 3.10+ standard library scripts, pytest tests, optional external tools (`file`, `strings`, `objdump`, `readelf`, `jadx`, `Ghidra`, `pyghidra`, `capa`, `floss`, `yara`).

---

## HAT 1 STOP

**Role declaration:** Codex is the active author of this plan. A separate reviewer, or the next agent turn acting as counter-reviewer, must challenge the plan before implementation. Codex must not issue ACCEPT on this plan.

**Operator gate:** Implementation begins only after the operator gives GO on this plan.

**Pre-survey evidence:**

- `hackersifu/reverse-engineering-skills` cloned at `5e675640e0ec94372298c57bb335ecf047360688`, MIT. Useful patterns: evidence-first IOC extraction, static-first unpacking, no live validation.
- `SimoneAvogadro/android-reverse-engineering-skill` cloned at `6a31ed3fa2fc96d2366e057dcf13bbf5c2bdcdaa`, Apache-2.0. Useful patterns: APK/XAPK/JAR/AAR decompilation phases, API endpoint extraction, Windows and POSIX tool support.
- `Arteriogramtrombiculiasis120/claude-code-reverse-engineering` cloned at `d0929746bfdbead9518e620caf77ff53acd43c0d`, MIT. Useful patterns: architecture-first documentation, permission/security modeling, extension system decomposition.
- `meyz664K/auto-re-agent` cloned at `78b489e1aeae71b85b168c91402ff8dcbfef94a7`, MIT. Useful patterns: backend abstraction, reverser/checker loop, function-level parity scoring, report tracking.
- `NationalSecurityAgency/ghidra` inspected from GitHub official docs on 2026-05-22. Useful patterns: Ghidra as SRE framework, headless batch mode, PyGhidra CPython integration, script/extension model.

**Safety scope:**

- Defensive and authorized analysis only.
- No unknown sample execution outside an explicit sandbox gate.
- No evasion, persistence, malware modification, credential theft, exploit chaining, or bypass guidance.
- No invented IOCs, endpoints, function names, artifacts, or parity matches.
- Every claim must cite source evidence, local path, command output, or analyst-provided artifact.

**Source-use decision:** Do not vendor third-party repo code in this plugin. Implement new scripts and docs from scratch, credit inspected sources in `references/source-provenance.md`, and keep license obligations explicit.

## Brainstorming Outcome

Three feasible designs were considered:

1. **Single mega-skill:** one large `SKILL.md` for all reverse engineering. This is easy to install but hard to trigger precisely, hard to test, and likely to mix Android, Ghidra, malware triage, and parity workflows.
2. **Thin plugin wrapping upstream skills:** mostly copy existing skills and scripts. This is fast, but it creates licensing and maintenance risk and does not provide one coherent Codex-native contract.
3. **Recommended: focused skill suite with shared references and helper scripts:** one router skill plus domain skills, deterministic static scripts, shared schemas, and explicit verification gates. This gives precise activation, easier review, and testable behavior.

Use option 3.

## Skill and Plugin Selection Register

Use the smallest skill set that fits the current step. Do not keep every skill active mentally at once; select by gate.

| Skill or plugin | Source | Use for this plan | Use when | Do not use when |
| --- | --- | --- | --- | --- |
| `superpowers:brainstorming` | Superpowers plugin | Requirements shaping, scope split, architecture alternatives | Starting or revising the design, choosing between mega-skill, copied upstream skills, or focused suite | Writing final implementation steps after the design is fixed |
| `brainstorming` | Local user skill | Same role as Superpowers brainstorming; local copy confirms the same hard gate | The user explicitly asks for idea shaping or when the plan needs scope correction | Duplicating the same process after the Superpowers version already covered it |
| `superpowers:writing-plans` | Superpowers plugin | Required plan format, file map, task breakdown, test commands, handoff | Writing or revising this implementation plan | Implementing files directly |
| `superpowers:verification-before-completion` | Superpowers plugin | Evidence-before-claims discipline | Before saying the plan is saved, validated, complete, passing, or ready for implementation | Before verification commands or file checks have actually run |
| `adversarial-pairing:adversarial-pairing` | `adversarial-pairing` plugin | HAT 1 STOP, counter-review checklist, no self-certification | Planning gates, implementation gates, closure review, failure-mode analysis | Issuing ACCEPT on artifacts authored in the same pass |
| `plugin-creator` | System skill | Codex plugin scaffold, manifest, marketplace, validation command | Creating/updating `.codex-plugin/plugin.json`, marketplace entries, or plugin structure | Writing individual skill bodies after plugin structure is already known |
| `skill-creator` | System skill | Individual `SKILL.md` design: frontmatter, concise body, references/scripts, validation | Creating or updating each focused skill in `skills/*/SKILL.md` | Writing user-facing README or broad plugin plan prose |
| `openai-docs` | System skill | Official OpenAI/Codex docs verification if local plugin spec is insufficient or conflicts | Checking current Codex skill/plugin behavior, OpenAI product docs, or API-related guidance | General reverse engineering methodology or non-OpenAI tool docs |
| `Claude Code Guide` | Local skill | Optional compatibility notes for Claude Code slash-command style only | Adding explicit Claude Code portability guidance after Codex support works | Codex-only plugin implementation |
| `agent-evaluation` | Local skill | Optional forward-test design for skill behavior | Designing realistic evaluation prompts after skills exist | Before there are concrete skill artifacts to evaluate |

**Selection sequence for implementation:**

1. Use `adversarial-pairing:adversarial-pairing` to open HAT 1 and identify assumptions, confounders, and reviewer obligations.
2. Use `superpowers:brainstorming` only if requirements or architecture change.
3. Use `superpowers:writing-plans` when editing this plan.
4. Use `plugin-creator` for manifest, marketplace, and plugin validation.
5. Use `skill-creator` for every `skills/*/SKILL.md` file and to keep skill bodies concise.
6. Use `openai-docs` only if a Codex/OpenAI contract cannot be verified from local plugin-creator or skill-creator references.
7. Use `superpowers:verification-before-completion` before any completion or readiness claim.
8. Use `agent-evaluation` after the first implementation pass if forward-testing is approved.

## File Structure

Create or modify the following files under `C:\Users\Test-User\plugins\reverse-engineering`:

- Modify `.codex-plugin/plugin.json`: validated manifest metadata, skill path, interface prompts, security category.
- Create `README.md`: user-facing installation, scope, workflows, dependencies, and examples.
- Create `LICENSE`: local plugin license.
- Create `references/safety-scope.md`: allowed and disallowed use, sandbox gates, analyst approval templates.
- Create `references/source-provenance.md`: inspected sources, commit hashes, licenses, what was reused conceptually, and what was not vendored.
- Create `references/output-schemas.md`: Markdown and JSON/YAML schemas for triage, IOC, Android API, Ghidra, and parity reports.
- Create `references/toolchain.md`: dependency matrix and graceful-degradation rules.
- Create `skills/reverse-engineering/SKILL.md`: router/orchestrator skill.
- Create `skills/binary-triage/SKILL.md`: static binary triage workflow.
- Create `skills/ioc-extraction/SKILL.md`: defensive IOC extraction workflow.
- Create `skills/unpacking-analysis/SKILL.md`: static-first packing and unpacking assessment.
- Create `skills/android-reverse-engineering/SKILL.md`: Android decompile/API extraction workflow.
- Create `skills/ghidra-headless/SKILL.md`: Ghidra and PyGhidra headless workflow.
- Create `skills/re-parity-review/SKILL.md`: adversarial parity review workflow.
- Create `scripts/re_tool_check.py`: dependency discovery and JSON report.
- Create `scripts/static_triage.py`: hashes, size, magic, strings snippets, entropy, optional external tool capture.
- Create `scripts/ioc_extract.py`: deterministic IOC extraction from provided evidence files.
- Create `scripts/android_api_scan.py`: deterministic scan over decompiled Android source trees.
- Create `scripts/ghidra_export_summary.py`: PyGhidra-compatible static summary exporter.
- Create `tests/test_tool_check.py`: dependency script tests.
- Create `tests/test_static_triage.py`: static triage tests on synthetic files.
- Create `tests/test_ioc_extract.py`: IOC extraction tests with de-obfuscation and traceability.
- Create `tests/test_android_api_scan.py`: Android endpoint extraction tests on synthetic Java/Kotlin files.
- Create `tests/test_markdown_contracts.py`: frontmatter, forbidden placeholders, and required section checks.

## Immutable Surfaces

- Do not change the plugin directory name `reverse-engineering`.
- Do not remove `.codex-plugin/plugin.json`.
- Do not create `.mcp.json` unless a real MCP server is implemented.
- Do not declare asset paths in `plugin.json` unless files exist and validation passes.
- Do not add scripts that execute analyzed samples.

## Task 1: Manifest and Marketplace Metadata

**Files:**

- Modify: `C:\Users\Test-User\plugins\reverse-engineering\.codex-plugin\plugin.json`
- Inspect: `C:\Users\Test-User\.agents\plugins\marketplace.json`

- [ ] **Step 1: Replace scaffold manifest with final metadata**

Write `.codex-plugin/plugin.json` exactly in this shape:

```json
{
  "name": "reverse-engineering",
  "version": "0.1.0",
  "description": "Defensive reverse engineering workflows for binary triage, IOC extraction, Android API extraction, Ghidra headless analysis, and parity review.",
  "author": {
    "name": "Local developer"
  },
  "license": "MIT",
  "keywords": [
    "reverse-engineering",
    "malware-analysis",
    "binary-analysis",
    "android",
    "ghidra",
    "ioc"
  ],
  "skills": "./skills/",
  "interface": {
    "displayName": "Reverse Engineering",
    "shortDescription": "Defensive RE workflows with evidence-first reports.",
    "longDescription": "A local Codex plugin for authorized reverse engineering: static binary triage, IOC extraction, unpacking assessment, Android API extraction, Ghidra or PyGhidra headless analysis, and adversarial parity review. Unknown samples are never executed automatically.",
    "developerName": "Local developer",
    "category": "Security",
    "capabilities": [
      "Read",
      "Write",
      "Interactive"
    ],
    "defaultPrompt": [
      "Triage this binary statically and report evidence.",
      "Extract traceable IOCs from these logs.",
      "Plan a Ghidra headless analysis workflow."
    ],
    "brandColor": "#256D5A"
  }
}
```

- [ ] **Step 2: Verify plugin manifest schema**

Run:

```powershell
python C:\Users\Test-User\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py C:\Users\Test-User\plugins\reverse-engineering
```

Expected: exit code `0`, no placeholder errors, no missing manifest errors.

- [ ] **Step 3: Verify marketplace entry remains valid**

Run:

```powershell
Get-Content -Raw C:\Users\Test-User\.agents\plugins\marketplace.json | python -m json.tool
```

Expected: valid JSON containing a `reverse-engineering` entry with category `Security`.

## Task 2: Governance and Reference Documents

**Files:**

- Create: `C:\Users\Test-User\plugins\reverse-engineering\README.md`
- Create: `C:\Users\Test-User\plugins\reverse-engineering\LICENSE`
- Create: `C:\Users\Test-User\plugins\reverse-engineering\references\safety-scope.md`
- Create: `C:\Users\Test-User\plugins\reverse-engineering\references\source-provenance.md`
- Create: `C:\Users\Test-User\plugins\reverse-engineering\references\output-schemas.md`
- Create: `C:\Users\Test-User\plugins\reverse-engineering\references\toolchain.md`

- [ ] **Step 1: Write safety reference**

`references/safety-scope.md` must include these sections:

```markdown
# Safety Scope

## Allowed

- Authorized malware triage, incident response, forensics, vulnerability research, interoperability analysis, education, and CTF analysis.
- Static analysis of files, logs, strings, decompiled source, manifests, and Ghidra/PyGhidra analysis outputs.
- Dynamic analysis only after explicit operator approval and only inside an isolated sandbox or VM with snapshot and logging.

## Disallowed

- Running unknown samples on a host system.
- Malware modification, stealth, evasion, persistence, credential theft, exploit deployment, or instructions to bypass monitoring.
- Live validation of suspicious infrastructure unless the operator explicitly provides a controlled environment and legal authorization.
- Inventing indicators, endpoints, artifacts, attribution, or function behavior not supported by evidence.

## Execution Gate

When execution is requested or required, respond with:

> PAUSE: This step requires executing an unknown or untrusted sample. I will not proceed automatically. Confirm sandbox approval, snapshot state, network posture, logging tools, and artifact storage path before continuing.
```

- [ ] **Step 2: Write source provenance**

`references/source-provenance.md` must list the five inspected sources, commit hashes where available, license, and a clear statement that no third-party source code was vendored.

- [ ] **Step 3: Write output schemas**

`references/output-schemas.md` must define:

- `triage_report` JSON fields: `sample`, `hashes`, `file_type`, `size_bytes`, `entropy`, `strings_summary`, `tool_outputs`, `limitations`.
- `ioc_report` YAML groups: `hashes`, `network`, `file_paths`, `file_names`, `process_names`, `registry`, `mutexes`, `user_agents`, `emails`, `certificates`, `notes`.
- `android_api_report` JSON fields: `base_urls`, `endpoints`, `auth_headers`, `call_flows`, `source_files`, `limitations`.
- `ghidra_report` JSON fields: `program`, `language_id`, `compiler_spec_id`, `functions`, `imports`, `exports`, `strings`, `analysis_warnings`.
- `parity_report` JSON fields: `target_function`, `source_candidates`, `signals`, `score`, `verdict`, `review_notes`.

- [ ] **Step 4: Write dependency matrix**

`references/toolchain.md` must separate required, optional, and workflow-specific tools:

- Required for scripts: Python 3.10+.
- Optional native binary tools: `file`, `strings`, `objdump`, `readelf`, `otool`, `diec`, `capa`, `floss`, `yara`.
- Android tools: JDK 17+, `jadx`; optional `apktool`, `dex2jar`, Vineflower.
- Ghidra tools: Ghidra release with JDK 21 for current official releases, `analyzeHeadless`, optional `pyghidra`.

## Task 3: Router Skill

**Files:**

- Create: `C:\Users\Test-User\plugins\reverse-engineering\skills\reverse-engineering\SKILL.md`

- [ ] **Step 1: Write router frontmatter**

Use this frontmatter:

```markdown
---
name: reverse-engineering
description: Route authorized reverse engineering requests to focused defensive workflows: binary triage, IOC extraction, unpacking analysis, Android API extraction, Ghidra headless analysis, and parity review. Use when the user asks to reverse engineer, triage, decompile, extract indicators, analyze APKs, use Ghidra, or compare recovered code to source.
---
```

- [ ] **Step 2: Write routing table**

The skill body must include:

```markdown
## Routing

| User intent | Use skill |
| --- | --- |
| Unknown binary triage, hashes, strings, entropy, imports | `binary-triage` |
| Extract IOCs from strings, sandbox logs, network logs, RE notes | `ioc-extraction` |
| Packed or obfuscated sample assessment | `unpacking-analysis` |
| APK, XAPK, JAR, AAR decompilation and API endpoint extraction | `android-reverse-engineering` |
| Ghidra, PyGhidra, headless analysis, function summaries | `ghidra-headless` |
| Recovered code versus source, function matching, confidence scoring | `re-parity-review` |
```

- [ ] **Step 3: Add universal guardrails**

Add a section requiring static-first analysis, evidence snippets, no sample execution, explicit sandbox gate, and report limitations.

## Task 4: Static Binary Triage

**Files:**

- Create: `C:\Users\Test-User\plugins\reverse-engineering\skills\binary-triage\SKILL.md`
- Create: `C:\Users\Test-User\plugins\reverse-engineering\scripts\re_tool_check.py`
- Create: `C:\Users\Test-User\plugins\reverse-engineering\scripts\static_triage.py`
- Create: `C:\Users\Test-User\plugins\reverse-engineering\tests\test_tool_check.py`
- Create: `C:\Users\Test-User\plugins\reverse-engineering\tests\test_static_triage.py`

- [ ] **Step 1: Write failing tests for tool discovery**

Create `tests/test_tool_check.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_tool_check_emits_json():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "re_tool_check.py"), "--json"],
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert "python" in payload
    assert "tools" in payload
    assert isinstance(payload["tools"], dict)
```

- [ ] **Step 2: Write failing tests for static triage**

Create `tests/test_static_triage.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_static_triage_reports_hashes_and_entropy(tmp_path):
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"MZ" + b"A" * 64 + b"https://example.test/path\x00")
    out = tmp_path / "triage.json"

    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "static_triage.py"), str(sample), "--json-out", str(out)],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["sample"]["path"] == str(sample)
    assert payload["hashes"]["sha256"]
    assert payload["size_bytes"] == sample.stat().st_size
    assert payload["entropy"]["overall"] >= 0
    assert "https://example.test/path" in "\n".join(payload["strings_summary"]["ascii_preview"])
```

- [ ] **Step 3: Implement `re_tool_check.py`**

The script must use `shutil.which`, emit JSON by default when `--json` is provided, never install tools, and include `python.version`, `python.executable`, and tool paths or `null`.

- [ ] **Step 4: Implement `static_triage.py`**

The script must:

- Refuse directories.
- Compute MD5, SHA1, SHA256.
- Compute Shannon entropy for the full file and 4 KiB chunks.
- Extract printable ASCII strings with a minimum length of 4.
- Optionally run available tools from `file`, `strings`, `objdump`, and `readelf` with timeouts.
- Write JSON atomically to `--json-out`.
- Never execute the sample as a program.

- [ ] **Step 5: Write binary triage skill**

`skills/binary-triage/SKILL.md` must instruct the agent to run:

```powershell
python C:\Users\Test-User\plugins\reverse-engineering\scripts\re_tool_check.py --json
python C:\Users\Test-User\plugins\reverse-engineering\scripts\static_triage.py <sample> --json-out <sample>.triage.json
```

It must require a final report with hashes, file type, entropy interpretation, string findings, tool limitations, and recommended next skill.

- [ ] **Step 6: Verify**

Run:

```powershell
python -m pytest C:\Users\Test-User\plugins\reverse-engineering\tests\test_tool_check.py C:\Users\Test-User\plugins\reverse-engineering\tests\test_static_triage.py -q
```

Expected: 2 tests pass.

## Task 5: IOC Extraction

**Files:**

- Create: `C:\Users\Test-User\plugins\reverse-engineering\skills\ioc-extraction\SKILL.md`
- Create: `C:\Users\Test-User\plugins\reverse-engineering\scripts\ioc_extract.py`
- Create: `C:\Users\Test-User\plugins\reverse-engineering\tests\test_ioc_extract.py`

- [ ] **Step 1: Write failing IOC tests**

Create `tests/test_ioc_extract.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_ioc_extract_preserves_evidence_and_normalizes_obfuscated_url(tmp_path):
    evidence = tmp_path / "evidence.txt"
    evidence.write_text(
        "sha256: " + "a" * 64 + "\n"
        "callback hxxps://Bad[.]Example/path?q=1\n"
        "User-Agent: ExampleAgent/1.0\n",
        encoding="utf-8",
    )
    out = tmp_path / "iocs.json"

    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ioc_extract.py"), str(evidence), "--json-out", str(out)],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["hashes"][0]["value"] == "a" * 64
    values = {item["value"] for item in payload["network"]}
    assert "hxxps://Bad[.]Example/path?q=1" in values
    assert "https://bad.example/path?q=1" in values
    assert payload["user_agents"][0]["evidence_snippet"] == "User-Agent: ExampleAgent/1.0"
```

- [ ] **Step 2: Implement `ioc_extract.py`**

The extractor must use regexes for hashes, URLs, domains, IPv4, registry paths, Windows paths, mutex-like labels, emails, and user agents. Every emitted item must include `value`, `confidence`, `source`, `evidence_snippet`, and type-specific fields. It must perform only reversible normalization such as `hxxp` to `http` and `[.]` to `.`.

- [ ] **Step 3: Write IOC skill**

The skill must require two outputs:

- Markdown table columns: `Type`, `Indicator`, `Confidence`, `Context`, `Evidence`.
- YAML or JSON structured output following `references/output-schemas.md`.

- [ ] **Step 4: Verify**

Run:

```powershell
python -m pytest C:\Users\Test-User\plugins\reverse-engineering\tests\test_ioc_extract.py -q
```

Expected: 1 test passes.

## Task 6: Unpacking Analysis

**Files:**

- Create: `C:\Users\Test-User\plugins\reverse-engineering\skills\unpacking-analysis\SKILL.md`

- [ ] **Step 1: Write the unpacking skill**

The skill must define:

- Inputs: triage JSON, section table, strings, imports, optional sandbox notes.
- Signals: high entropy, low strings, unusual sections, minimal imports, packer signatures, UPX markers, runtime unpacking telemetry.
- Static-first decision tree.
- Sandbox-only gate for dynamic unpacking.
- Report format: verdict, confidence, evidence excerpts, plan, artifacts, validation.

- [ ] **Step 2: Add UPX-specific guardrail**

Include: use `upx -d` only when evidence explicitly indicates UPX, and validate the result by comparing hashes, strings count, imports, and entropy.

- [ ] **Step 3: Verify by contract scan**

Run:

```powershell
Select-String -Path C:\Users\Test-User\plugins\reverse-engineering\skills\unpacking-analysis\SKILL.md -Pattern "PAUSE","static-first","UPX","evidence"
```

Expected: all four patterns are present.

## Task 7: Android Reverse Engineering

**Files:**

- Create: `C:\Users\Test-User\plugins\reverse-engineering\skills\android-reverse-engineering\SKILL.md`
- Create: `C:\Users\Test-User\plugins\reverse-engineering\scripts\android_api_scan.py`
- Create: `C:\Users\Test-User\plugins\reverse-engineering\tests\test_android_api_scan.py`

- [ ] **Step 1: Write failing Android API scan test**

Create `tests/test_android_api_scan.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_android_api_scan_finds_retrofit_and_okhttp(tmp_path):
    source = tmp_path / "ApiService.kt"
    source.write_text(
        '@GET("v1/users/{id}")\n'
        'suspend fun user(@Path("id") id: String): User\n'
        'val base = "https://api.example.test/"\n'
        'Request.Builder().url("https://api.example.test/v1/ping")\n',
        encoding="utf-8",
    )
    out = tmp_path / "android-api.json"

    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "android_api_scan.py"), str(tmp_path), "--json-out", str(out)],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "https://api.example.test/" in payload["base_urls"]
    endpoint_paths = {endpoint["path"] for endpoint in payload["endpoints"]}
    assert "v1/users/{id}" in endpoint_paths
    assert "https://api.example.test/v1/ping" in endpoint_paths
```

- [ ] **Step 2: Implement `android_api_scan.py`**

The script must recursively scan `.java`, `.kt`, `.xml`, `.properties`, and `.gradle` files. It must detect Retrofit annotations, hardcoded URLs, common auth headers, OkHttp request builders, Volley request usage, and source file paths with line numbers.

- [ ] **Step 3: Write Android skill**

The skill must define phases:

1. Dependency check: JDK 17+, `jadx`, optional `apktool`, `dex2jar`, Vineflower.
2. Decompile APK/XAPK/JAR/AAR with user-approved tools.
3. Inspect manifest, permissions, launcher activity, application class.
4. Trace call flow from UI to ViewModel/Presenter/Repository/API service.
5. Run `android_api_scan.py` over decompiled source.
6. Produce endpoint report with source lines and limitations.

- [ ] **Step 4: Verify**

Run:

```powershell
python -m pytest C:\Users\Test-User\plugins\reverse-engineering\tests\test_android_api_scan.py -q
```

Expected: 1 test passes.

## Task 8: Ghidra Headless and PyGhidra

**Files:**

- Create: `C:\Users\Test-User\plugins\reverse-engineering\skills\ghidra-headless\SKILL.md`
- Create: `C:\Users\Test-User\plugins\reverse-engineering\scripts\ghidra_export_summary.py`

- [ ] **Step 1: Write Ghidra skill**

The skill must cover:

- `analyzeHeadless` project creation/import, `-import`, `-postScript`, `-scriptPath`, and output collection.
- PyGhidra path for Python-native workflows when `pyghidra` is installed.
- External dependency discovery without downloading Ghidra automatically.
- Static analysis outputs: program metadata, functions, imports, exports, strings, decompiler summaries when available.
- Safe handling of large binaries and timeouts.

- [ ] **Step 2: Implement `ghidra_export_summary.py`**

The script must run inside PyGhidra or a compatible Ghidra scripting environment and emit JSON with keys defined in `references/output-schemas.md`. When imported outside Ghidra, it must print a clear error and exit non-zero instead of failing with an unhandled import error.

- [ ] **Step 3: Verify syntax without requiring Ghidra**

Run:

```powershell
python -m py_compile C:\Users\Test-User\plugins\reverse-engineering\scripts\ghidra_export_summary.py
```

Expected: exit code `0`.

## Task 9: Recovered-Code Parity Review

**Files:**

- Create: `C:\Users\Test-User\plugins\reverse-engineering\skills\re-parity-review\SKILL.md`

- [ ] **Step 1: Write parity skill**

The skill must define an analyst-in-the-loop reverser/checker workflow:

- Identify target function and evidence source.
- Gather source candidates from known source tree, symbols, strings, call graph, constants, and API usage.
- Score signals: name/symbol match, call count, constants, string references, control flow shape, data structure access, error paths, side effects, external API use, test oracle, negative evidence.
- Produce verdict: `match`, `likely_match`, `unclear`, or `not_match`.
- Require a checker pass that lists contradictions and missing evidence.

- [ ] **Step 2: Add anti-false-positive rules**

Include rules that forbid parity acceptance from names alone, one shared string alone, or LLM intuition without source-backed signals.

- [ ] **Step 3: Verify by contract scan**

Run:

```powershell
Select-String -Path C:\Users\Test-User\plugins\reverse-engineering\skills\re-parity-review\SKILL.md -Pattern "negative evidence","checker","not_match","source-backed"
```

Expected: all four patterns are present.

## Task 10: Markdown and Plugin Contract Tests

**Files:**

- Create: `C:\Users\Test-User\plugins\reverse-engineering\tests\test_markdown_contracts.py`

- [ ] **Step 1: Write markdown contract tests**

Create `tests/test_markdown_contracts.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SKILLS = [
    "reverse-engineering",
    "binary-triage",
    "ioc-extraction",
    "unpacking-analysis",
    "android-reverse-engineering",
    "ghidra-headless",
    "re-parity-review",
]

FORBIDDEN = ["T" + "BD", "TO" + "DO", "[" + "TO" + "DO", "fill " + "in later"]

def test_required_skill_files_exist_and_have_frontmatter():
    for name in REQUIRED_SKILLS:
        path = ROOT / "skills" / name / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n"), path
        assert f"name: {name}" in text, path
        assert "description:" in text, path

def test_no_forbidden_placeholders():
    paths = list((ROOT / "skills").glob("*/SKILL.md")) + list((ROOT / "references").glob("*.md")) + [ROOT / "README.md"]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN:
            assert marker not in text, f"{marker} found in {path}"

def test_safety_gate_present_in_relevant_skills():
    for name in ["binary-triage", "unpacking-analysis", "ghidra-headless"]:
        text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "PAUSE" in text
        assert "sandbox" in text.lower()
```

- [ ] **Step 2: Run all tests**

Run:

```powershell
python -m pytest C:\Users\Test-User\plugins\reverse-engineering\tests -q
```

Expected: all tests pass.

- [ ] **Step 3: Run plugin validator**

Run:

```powershell
python C:\Users\Test-User\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py C:\Users\Test-User\plugins\reverse-engineering
```

Expected: exit code `0`.

## Task 11: README and Usage Examples

**Files:**

- Create or modify: `C:\Users\Test-User\plugins\reverse-engineering\README.md`

- [ ] **Step 1: Write README sections**

The README must include:

- Purpose and defensive scope.
- Installation status: local Codex plugin at `C:\Users\Test-User\plugins\reverse-engineering`.
- Skill list and when to use each skill.
- Dependency table.
- Example prompts:
  - "Use binary-triage on this sample path and produce a static evidence report."
  - "Use ioc-extraction on these strings and return Markdown plus YAML."
  - "Use android-reverse-engineering to extract API endpoints from this APK."
  - "Use ghidra-headless to plan a headless import and function summary."
  - "Use re-parity-review to compare this decompiled function with candidate source."
- Verification commands.
- Safety disclaimer.

- [ ] **Step 2: Verify README has no forbidden placeholders**

Run:

```powershell
$patterns = @("T" + "BD", "TO" + "DO", "fill " + "in later")
Select-String -Path C:\Users\Test-User\plugins\reverse-engineering\README.md -Pattern $patterns
```

Expected: no matches.

## Task 12: HAT 3 Closure Preparation

**Files:**

- Inspect all files under: `C:\Users\Test-User\plugins\reverse-engineering`

- [ ] **Step 1: Run full verification**

Run:

```powershell
python -m pytest C:\Users\Test-User\plugins\reverse-engineering\tests -q
python C:\Users\Test-User\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py C:\Users\Test-User\plugins\reverse-engineering
```

Expected: pytest exits `0`; validator exits `0`.

- [ ] **Step 2: Perform adversarial review**

Review against these blockers:

- A skill suggests executing unknown samples without PAUSE.
- A script can execute or detonate a sample.
- An IOC can be emitted without evidence snippet.
- Android extraction invents endpoints from names rather than source lines.
- Ghidra workflow assumes Ghidra is installed without checking.
- Parity verdict can pass on a single weak signal.
- Manifest references non-existent assets or MCP files.
- Any file contains placeholder markers.

- [ ] **Step 3: Prepare final operator report**

Report:

- Files created and modified.
- Verification commands and exit codes.
- Known limitations.
- Whether a separate counter-reviewer has issued ACCEPT.
- Codex app plugin links from the marketplace entry.

## Completion Criteria

The work can be called complete only when all are true:

- Every planned skill exists with valid frontmatter.
- Every helper script has at least one focused test.
- Full pytest suite exits `0`.
- `validate_plugin.py` exits `0`.
- Safety scope is present in README, references, and relevant skills.
- Source provenance is documented with commit hashes and licenses.
- No third-party source code was copied into the plugin.
- A counter-reviewer or separate review pass has challenged the plan or implementation.
- Operator gives final GO after reviewing evidence.

## Plan Self-Review

**Spec coverage:** The plan covers plugin manifest, skills, scripts, tests, references, source provenance, safety, Android, Ghidra, unpacking, IOC extraction, and parity review.

**Placeholder scan:** This plan avoids unresolved placeholder markers and defines concrete files, commands, tests, and expected outputs.

**Type consistency:** Script names, test names, skill names, and schema keys are consistent across tasks.

**Scope check:** This is a single plugin implementation. A future real MCP server, UI companion, or Ghidra extension should be a separate plan.
