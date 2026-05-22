---
name: reverse-engineering
description: Entry and dispatch skill for broad or unclear authorized reverse engineering requests, including downloaded repository analysis, source code forensics, architecture mapping, RAG/MCP corpus creation, binary triage, IOC extraction, Android analysis, Ghidra workflows, or recovered-code parity review. Use when the user asks generally to reverse engineer or analyze an unfamiliar codebase/artifact and the specific workflow is not yet clear.
---

# Reverse Engineering Router

Use the narrowest available workflow. For downloaded or cloned source repositories, use `repo-reverse-engineering`.

## Routing

| User intent | Use skill |
| --- | --- |
| Downloaded/cloned source repo, unfamiliar codebase, architecture map, RAG/MCP corpus | `repo-reverse-engineering` |
| Recovered function versus candidate source function | `re-parity-review` |
| APK/XAPK/JAR/AAR API extraction | `android-reverse-engineering` |
| Ghidra/PyGhidra headless binary analysis | `ghidra-headless` |
| IOC extraction from evidence | `ioc-extraction` |
| Packed/obfuscated binary assessment | `unpacking-analysis` |
| Unknown binary static triage | `binary-triage` |

## Universal Guardrails

- Work static-first.
- Do not execute unknown samples or repository code automatically.
- Keep evidence traceable to files, lines, command output, or provided artifacts.
- If execution is required, stop with a `PAUSE` gate and request sandbox constraints.
- State limitations instead of filling gaps with guesses.
