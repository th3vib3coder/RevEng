---
name: ioc-extraction
description: Extract and normalize defensive indicators of compromise from analyst-provided evidence such as strings output, sandbox logs, network logs, file paths, registry traces, decompiled snippets, or reverse engineering notes. Use when the user asks for IOCs, hunting lists, blocklists, YAML/JSON indicators, or evidence-backed security reporting.
---

# IOC Extraction

Extract only indicators present in evidence. Do not validate infrastructure live and do not invent missing values.

## Workflow

From the plugin root:

```bash
python3 scripts/ioc_extract.py evidence.txt --json-out iocs.json
```

Use `python` on Windows if `python3` is absent.

## Rules

- Every IOC must include a verbatim `evidence_snippet`.
- Preserve defanged values and emit normalized variants only when the transform is reversible, such as `hxxp` to `http` and `[.]` to `.`.
- Do not resolve domains, visit URLs, contact IPs, or enrich live infrastructure.
- Label ambiguous or partial values as `candidate` or `incomplete`.

## Output

Return:

- Markdown table: `Type`, `Indicator`, `Confidence`, `Context`, `Evidence`.
- Structured JSON or YAML grouped by type following `references/output-schemas.md`.

