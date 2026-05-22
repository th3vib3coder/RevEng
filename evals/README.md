# Golden Evaluations

Golden evals are end-to-end checks for RevEng workflows. They create disposable fixtures, run the shipped helper scripts as subprocesses, and assert stable analyst-facing invariants across outputs.

Run from the repository root:

```bash
python scripts/run_golden_evals.py
```

To inspect generated fixtures and outputs:

```bash
python scripts/run_golden_evals.py --keep
```

The current eval cases cover:

- repository inventory, map, plugin-surface detection, route extraction, dependency extraction, risks, and corpus records
- binary triage with bounded reads and full-file streaming hashes
- IOC extraction with defanged normalization, contextual version-like IPv4 confidence, and overlong-line truncation
- Android API scanning with endpoints, auth evidence, base URLs, and oversized-file skips

These evals intentionally do not execute untrusted repository code, binaries, Android apps, package managers, containers, or network calls.
