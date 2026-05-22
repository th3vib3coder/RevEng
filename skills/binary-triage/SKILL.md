---
name: binary-triage
description: Static-first triage of unknown or suspicious binary files such as PE, ELF, Mach-O, DLL, shared libraries, firmware blobs, or packed samples. Use when the user asks for hashes, file type, entropy, strings, imports, packer hints, or whether a binary needs deeper reverse engineering.
---

# Binary Triage

Triage binaries without executing them. Use static evidence only and record limitations.

## Safety

- Do not run the sample.
- Do not load it into tools that execute code.
- If dynamic behavior is required, stop with `PAUSE` and require sandbox approval.

## Workflow

From the plugin root:

```bash
python3 scripts/re_tool_check.py --json
python3 scripts/static_triage.py /path/to/sample --json-out sample.triage.json
```

Use `python` on Windows if `python3` is absent.

Then read `sample.triage.json` and report:

- hashes and file size
- file type and optional tool outputs
- entropy and packing indicators
- strings preview and suspicious static artifacts
- limitations and next recommended skill

## Output

Return a concise Markdown report and cite values from the JSON output. Recommend `unpacking-analysis` only when evidence supports packing or obfuscation. Recommend `ioc-extraction` when strings or logs contain extractable indicators.

