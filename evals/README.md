# Golden Evaluations

Golden evals are end-to-end checks for RevEng workflows. They create disposable fixtures, run the shipped helper scripts as subprocesses, and assert stable analyst-facing invariants across outputs.

Run from the repository root:

```bash
python scripts/run_golden_evals.py
```

Write the machine-readable summary used by CI:

```bash
python scripts/run_golden_evals.py --json-out evals/golden-summary.json
```

To inspect generated fixtures and outputs:

```bash
python scripts/run_golden_evals.py --keep
```

The current eval cases cover:

- repository inventory, map, plugin-surface detection, route extraction, dependency extraction, risks, and corpus records
- read-only MCP stdio corpus queries with tool discovery, cursor pagination, split text/structured responses, and tool-visible schema errors
- binary triage with bounded reads and full-file streaming hashes
- IOC extraction with defanged normalization, contextual version-like IPv4 confidence, and overlong-line truncation
- Android API scanning with endpoints, auth evidence, base URLs, and oversized-file skips
- fake Ghidra graph export with call graph, CFG, warnings, and summary formatting
- OCP safety/reporting prompt contract checks for PAUSE, static-first, raw-eval gating, negative evidence, and alternate hypotheses

The JSON summary uses schema `reveng.golden_evals.v1`. Every case reports:

- `capability`
- `status`
- `metrics.assertions`
- `metrics.false_positives`
- `metrics.false_negatives`
- `metrics.missing_evidence`
- `metrics.unsafe_actions`

These evals intentionally do not execute untrusted repository code, binaries, Android apps, package managers, containers, or network calls.
