# HAT 1 Counter-Review — REDIRECT

**Artifact under review:** `docs/superpowers/plans/2026-05-22-reverse-engineering-plugin.md`
**Author of artifact:** Codex
**Counter-reviewer:** Claude Code (independent agent instance)
**Date:** 2026-05-22
**Verdict:** **REDIRECT** — revise the plan before HAT 2. Per adversarial-pairing discipline, Codex must NOT self-ACCEPT this revision; Claude Code re-reviews the revised plan, then the operator issues GO.

---

## Operator decisions locked (do not relitigate)

1. **Target platforms:** the plugin must be **portable on BOTH Codex and Claude Code**.
2. **Router architecture:** **KEEP** the router skill + 6 domain skills (operator overrode the reviewer's "drop router" suggestion).

These two are settled inputs for the revision, not open questions.

## Independent verification performed (grounding)

The following were checked against reality, not taken from the plan's self-review:

- **Source provenance is ACCURATE.** All 4 cited repos return HTTP 200; all 4 commit SHAs exist (HTTP 200 on `/commits/<sha>`); licenses match the plan exactly: `hackersifu/reverse-engineering-skills` MIT, `SimoneAvogadro/android-reverse-engineering-skill` Apache-2.0, `Arteriogramtrombiculiasis120/claude-code-reverse-engineering` MIT, `meyz664K/auto-re-agent` MIT.
- **Codex manifest in Task 1 is schema-valid.** Verified against `.codex/skills/.system/plugin-creator/scripts/validate_plugin.py`: `interface.capabilities` array-of-strings OK, `brandColor #RRGGBB` OK, `defaultPrompt` accepted as array (presence-only check), `skills: "./skills/"` normalizes to `skills` OK.
- **Marketplace entry already exists.** `~/.agents/plugins/marketplace.json` already contains the `reverse-engineering` entry with `category: Security`, `policy.installation: AVAILABLE`, `policy.authentication: ON_INSTALL`.
- **Claude Code plugin format confirmed different.** 50+ installed plugins use `.claude-plugin/plugin.json` (lenient schema; `name`+`description`+`author` is enough). Path convention is `${CLAUDE_PLUGIN_ROOT}` in config files; hardcoded paths are an explicit documented anti-pattern.
- **Multi-manifest portability is an established pattern.** The superpowers plugin ships `.cursor-plugin/` alongside `.claude-plugin/` — so `.codex-plugin/` + `.claude-plugin/` coexisting in one plugin root is proven, not speculative.
- **Portable script invocation is available.** At skill invocation the runtime announces `Base directory for this skill: <abs path>`. Skills can therefore reference bundled scripts by **relative path** resolved from that base dir — no absolute paths needed.

## Preserve (do not regress during revision)

- Accurate provenance + the no-vendoring decision (license heterogeneity makes conceptual reuse + `source-provenance.md` correct).
- Structural safety model: scripts never execute the sample; `PAUSE` gates; evidence-first IOCs. This is the plan's strongest feature.
- TDD structure: per-task RED tests + verification gates.
- The schema-valid Codex `interface` manifest (Task 1).

---

## BLOCKERS (must be fixed before HAT 2)

### B1 — No Claude Code manifest
Target is Codex **+** Claude Code, but the plan only creates `.codex-plugin/plugin.json` and only validates with the Codex validator. Claude Code needs `.claude-plugin/plugin.json`.
**Required change:** add a task that creates `.claude-plugin/plugin.json` (minimum: `name`, `description`, `author`; recommended: `version`, `license`, `keywords`, `homepage`/`repository`). Keep `.codex-plugin/plugin.json`. Both coexist in the plugin root. Update **File Structure**, **Immutable Surfaces** (add: do not remove either manifest), and **Completion Criteria** accordingly.

### B2 — Hardcoded absolute paths break execution on BOTH platforms
Every skill body and the File Structure hardcode `C:\Users\Test-User\plugins\reverse-engineering\scripts\...`. This breaks the moment the plugin is installed by another user, moved, or run on macOS/Linux. It also contradicts Claude Code's documented guidance.
**Required change:** shipped SKILL.md bodies must reference bundled scripts by **relative path**, resolved from the runtime-announced skill base directory (skill dir is `<root>/skills/<name>/`, so plugin root is two levels up).

Concrete before/after for the script-invocation steps (Tasks 4, 5, 7, 8):

~~~
# BEFORE (non-portable, in shipped SKILL.md):
python C:\Users\Test-User\plugins\reverse-engineering\scripts\re_tool_check.py --json

# AFTER (portable, in shipped SKILL.md):
# Run from the plugin root (resolve it from the skill base directory the runtime announces).
python3 scripts/re_tool_check.py --json    # use `python` on Windows if `python3` is absent
~~~

**Scope note:** this applies to commands *shipped inside SKILL.md / README*. The **plan's own verification commands** that the implementer runs locally on Windows MAY keep absolute paths + PowerShell — that is the dev environment, not shipped content.

### B3 — Shipped command blocks are Windows/PowerShell-shaped
Inside shipped skills, command fences are tagged `powershell` with backslash absolute paths and bare `python`. On Claude Code/macOS/Linux these fail.
**Required change:** in shipped SKILL.md/README, use OS-neutral command blocks (forward-slash relative paths, `python3` with a Windows `python` note, no PowerShell-only cmdlets). Where a content check is needed *inside a shipped skill*, prefer a Python one-liner over `Select-String`. (Again: plan-level verification steps the implementer runs may stay PowerShell.)

---

## SHOULD-FIX

### S1 — Router kept: disambiguation requirement + a hard validator constraint
The router stays (operator decision). To avoid trigger contention among 7 model-invocable skills:
- Router `description`: explicitly framed as the **entry/dispatch** skill ("use when the request is broad or the right RE workflow is unclear").
- The 6 domain skills: **narrow, mutually disjoint** descriptions so each fires on its own signal.
- **Constraint discovered in grounding:** you CANNOT make the domain skills explicit-only via `disable-model-invocation: true`, because the Codex validator (`validate_plugin.py`, the `disable-model-invocation` check) rejects any value other than `false`/absent. So all 7 skills remain model-invocable on both platforms; disambiguation is by description wording only.

### S2 — Add a Claude Code validation gate
The plan validates only the Codex side. Add a step that validates the Claude Code side: `.claude-plugin/plugin.json` is valid JSON with required fields, and `skills/*/SKILL.md` are discoverable (the existing markdown-contract test largely covers skill frontmatter; extend it to assert the CC manifest parses).

### S3 — Add a pre-flight environment gate (Task 0)
The plan assumes `python`, `pytest`, and `pyyaml` (the Codex validator imports `yaml`). Add a pre-flight that verifies Python version, `pytest` import, and `yaml` import before HAT 2 (matches adversarial-pairing pre-flight CI verification).

### S4 — Make coverage gaps explicit
- `ghidra_export_summary.py` is only `py_compile`'d (acceptable without a Ghidra install) — state it as a **declared known limitation**, and confirm the `import ghidra` / `currentProgram` access is wrapped so it exits non-zero cleanly outside Ghidra.
- The router has no behavioral test. If routing correctness matters, plan a forward-eval (`agent-evaluation`) rather than leaving it optional.

---

## NITS / make explicit

- **N1 — IOC double-emit is a deliberate contract.** The test asserts BOTH `hxxps://Bad[.]Example/...` (defanged original) and `https://bad.example/...` (normalized) appear. Document this in `output-schemas.md` and ensure dedup does not collapse the pair; define the confidence/source semantics of the normalized variant.
- **N2 — Marketplace entry already exists.** Task 1 Step 3 should be "verify the existing `reverse-engineering`/`category: Security` entry," not "create."
- **N3 — Empty dirs present.** `skills/`, `scripts/`, `references/`, `assets/` exist empty. Create each skill subdir only together with its `SKILL.md` (the Codex validator errors on a skill dir lacking `SKILL.md`). The plan already orders tasks this way — just do not pre-create empty skill subdirs.

---

## Required plan edits — concrete task map

1. **Add Task 0 — Pre-flight** (S3): verify Python, `pytest`, `pyyaml`.
2. **Add Task 1b — Claude Code manifest + validation** (B1, S2): create `.claude-plugin/plugin.json`; add CC-side validation.
3. **Add a global section — "Path & Command Portability Contract"** (B2, B3): relative-from-base-dir script paths; OS-neutral command blocks in shipped content; `python3`/`python` note; the Windows-only carve-out for plan-level verification.
4. **Tasks 3–9:** replace every absolute path in shipped SKILL.md bodies with the relative pattern; retag `powershell` fences in shipped content to neutral shells.
5. **Task 1 Step 3:** change "create" → "verify" the marketplace entry (N2).
6. **Output schemas:** document the IOC double-emit contract (N1).
7. **Update File Structure, Immutable Surfaces, Completion Criteria** to include `.claude-plugin/plugin.json` and the dual-platform validation requirement.
8. **Router & domain descriptions** (S1): rewrite for dispatch/disjoint roles; do not use `disable-model-invocation`.

## Re-review protocol (adversarial-pairing)

After Codex applies the revision:
1. Codex marks the revised plan as authored-by-Codex and does **not** self-ACCEPT.
2. Claude Code re-runs this counter-review against the revised plan (confirm B1–B3 closed, S1–S4 addressed, affirmations preserved).
3. Only on Claude Code ACCEPT + operator GO does HAT 2 (implementation) begin.
