# Safety Scope

This plugin is for authorized defensive reverse engineering, incident response, forensics, interoperability research, education, and CTF-style analysis.

## Allowed

- Static analysis of local repositories, binaries, strings, logs, manifests, decompiled source, and Ghidra outputs.
- Evidence-backed IOC extraction, architecture mapping, API inventory, and parity review.
- Dynamic analysis only after explicit operator approval in an isolated sandbox or VM.

## Disallowed

- Running unknown samples or repository code on a host system without approval.
- Malware modification, stealth, evasion, persistence, credential theft, exploit deployment, or bypass guidance.
- Live validation of suspicious infrastructure unless the operator provides a controlled environment and legal authorization.
- Inventing indicators, endpoints, functions, artifacts, attribution, or runtime behavior.

## Execution Gate

When execution is requested or required, respond:

> PAUSE: This step requires executing untrusted code or contacting external infrastructure. Confirm authorization, sandbox, network posture, snapshot/rollback state, exact command, and output path before continuing.

