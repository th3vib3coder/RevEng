---
name: re-parity-review
description: Adversarial parity review between recovered/decompiled functions and candidate source code. Use when the user asks whether a recovered function matches source, to compare behavior, map symbols, score evidence, or avoid false-positive reverse-engineering matches.
---

# Recovered-Code Parity Review

Compare recovered code to source candidates with multiple independent signals and an explicit checker pass.

## Workflow

1. Identify target function, source artifact, address/symbol if known, and candidate source files.
2. Gather signals: symbol/name, call count, constants, strings, control-flow shape, data structure access, error paths, side effects, imports/API use, tests/oracles, and negative evidence.
3. Score each candidate and record contradictions.
4. Run a checker pass: list weak assumptions, missing evidence, and plausible non-matches.

## Anti-False-Positive Rules

- Do not accept parity from a name alone.
- Do not accept parity from one shared string alone.
- Do not accept parity from LLM intuition without source-backed signals.
- Treat negative evidence as first-class evidence.

## Verdicts

- `match`
- `likely_match`
- `unclear`
- `not_match`

## Output

Return a parity report with `target_function`, `source_candidates`, `signals`, `score`, `verdict`, and `review_notes`.
