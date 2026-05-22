---
name: unpacking-analysis
description: Static-first assessment of packed or obfuscated binaries and safe unpacking planning. Use when entropy, section names, import scarcity, packer signatures, UPX markers, or sandbox notes suggest a binary may unpack or decrypt code before behavior.
---

# Unpacking Analysis

Assess packing with evidence and produce a safe unpacking plan. Do not execute the sample automatically.

## Inputs

- `static_triage.py` JSON
- section/import output from tools such as `objdump`, `readelf`, `diec`, `capa`, or `floss`
- optional sandbox notes provided by the analyst

## Static-First Decision Tree

1. Check entropy, file type, strings density, section names, imports, and packer signatures.
2. If evidence indicates UPX, plan `upx -d` as an offline attempt and validate by comparing hashes, strings, imports, and entropy.
3. If static unpacking is not supported, stop at planning unless the operator approves sandbox execution.

## Execution Gate

If unpacking requires running the sample, respond:

> PAUSE: Unpacking now requires executing the sample. Confirm isolated VM or sandbox, snapshot state, network posture, monitoring tools, dump path, and exact commands before continuing.

## Output

Return:

- verdict: `packed`, `likely_packed`, `unclear`, or `not_packed`
- confidence and evidence excerpts
- prioritized unpacking plan
- artifact provenance template
- validation criteria and next steps

