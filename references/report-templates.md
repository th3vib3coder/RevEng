# Report Templates

Use these templates to keep RevEng output auditable. Keep claims tied to artifacts, paths, line numbers, graph nodes, or tool output.

## Repository Analysis Report

### Scope

- Target:
- Artifacts:
- Static-first boundary:
- Commands run:

### Apparent Purpose

State observed purpose with evidence. Separate observation from inference.

### Architecture And Major Components

Use `repo_map.json`, `graph`, and `module_graph`.

| Component | Evidence | Role | Confidence |
| --- | --- | --- | --- |
| | | | |

### Entrypoints And Flows

| Entrypoint | Target | Evidence | Notes |
| --- | --- | --- | --- |
| | | | |

### API, CLI, MCP, Plugin, And Service Surfaces

| Surface | Path/Route/Command | Evidence | Risk |
| --- | --- | --- | --- |
| | | | |

### Dependencies And Toolchain

| Ecosystem | Dependency | Source | Notes |
| --- | --- | --- | --- |
| | | | |

### Evidence Table

| Claim | Evidence | Artifact | Confidence |
| --- | --- | --- | --- |
| | | | |

### Negative Evidence

Record what was checked and not found. Do not turn absence into proof.

| Question | Checked Evidence | Result | Residual Risk |
| --- | --- | --- | --- |
| | | | |

### Alternate Hypotheses

| Hypothesis | Supporting Evidence | Contradicting Evidence | Next Check |
| --- | --- | --- | --- |
| | | | |

### Security And Supply-Chain Signals

| Signal | Evidence | Severity | Recommended Follow-Up |
| --- | --- | --- | --- |
| | | | |

### Blocked Questions

| Question | Why Blocked | Required Authorization/Artifact |
| --- | --- | --- |
| | | |

### Next Analysis

List concrete next steps. Mark anything requiring execution with PAUSE.

## Binary Triage Report

### Scope

- Sample:
- Hashes:
- Size:
- Static tools used:

### Type, Entropy, And Strings

| Finding | Evidence | Limitation |
| --- | --- | --- |
| | | |

### Negative Evidence

- No execution was performed.
- No network contact was made.
- No unpacking/debugging was performed unless separately approved.

### Alternate Hypotheses

Use when packer/static evidence is ambiguous.

### Next Analysis

Use `unpacking-analysis`, `ioc-extraction`, or `ghidra-headless` only when evidence supports it.

## Ghidra Graph Report

### Scope

- Program:
- Ghidra/PyGhidra runtime:
- Export artifact:

### Function Call Graph

| Caller | Callee | Evidence | Limitation |
| --- | --- | --- | --- |
| | | | |

### CFG Highlights

| Function | Basic Blocks | Edges | Notes |
| --- | --- | --- | --- |
| | | | |

### Negative Evidence

List functions/edges unavailable because the Ghidra API, decompiler, or analysis state did not expose them.

### Blocked Questions

State when a real Ghidra smoke test, debugger, emulator, or dynamic analysis is required.
