# Agentic Pipelines And Benchmarks

Scope: orchestration patterns and evaluation targets that should make RevEng stronger rather than merely larger.

## Sources

- `mrphrazer/agentic-malware-analysis`: https://github.com/mrphrazer/agentic-malware-analysis
- `Karib0u/kernagent`: https://github.com/Karib0u/kernagent
- `louisgthier/decompai`: https://github.com/louisgthier/decompai
- `aayush0325/reverse-engineering-agent`: https://github.com/aayush0325/reverse-engineering-agent
- HELIOS: https://arxiv.org/abs/2601.14598
- CREBench: https://arxiv.org/abs/2604.03750
- BinMetric: https://arxiv.org/abs/2505.07360
- ReCopilot: https://arxiv.org/abs/2505.16366
- SoK LLMs for RE: https://arxiv.org/abs/2509.21821
- LLM-resistant software protection: https://www.ndss-symposium.org/ndss-paper/auto-draft-657/

## `agentic-malware-analysis`

Observed facts:

- Provides an agentic malware analysis environment with MCP-connected disassemblers and structured workflows for Claude Code and Codex CLI.
- Uses Docker assets, Codex/Claude helper skills, MCP configuration helpers, examples, YARA assets, and status templates.
- Separates app/runtime files from `agent_helpers` for Claude and Codex.

Atomic ideas for RevEng:

- `ADOPT`: introduce a standard `case/` directory layout for every deep analysis.
- `ADAPT`: add status templates and report sections for triage, hypotheses, evidence, blockers, and next steps.
- `ADOPT`: make agent configuration explicit and reproducible instead of hidden in chat context.
- `TRACK`: large Kali-style bundled tool images are a separate project, not core RevEng.

## `kernagent`

Observed facts:

- Headless by design.
- Emphasizes deterministic snapshots, portability, model-agnostic LLM endpoints, and evidence-cited answers.
- Does not require MCP or GUI automation.

Atomic ideas for RevEng:

- `ADOPT`: make RevEng case artifacts reproducible enough to diff between runs.
- `ADOPT`: every high-level report section should cite the artifact/file/function/path that supports it.
- `ADAPT`: add snapshot manifests for repository and binary export inputs.

## `decompai`

Observed facts:

- LangGraph/Gradio LLM agent for binary analysis and decompilation.
- Uses Docker runner containers and integrates tools like objdump, gdb, and Ghidra.
- Notes that runner containers may require privileged execution.

Atomic ideas for RevEng:

- `TRACK`: UI and LangGraph orchestration are useful but not part of plugin core.
- `ADAPT`: short-lived runner containers are a good sandbox pattern if dynamic analysis is added later.
- `REJECT`: privileged runner mode as a default.

## `reverse-engineering-agent`

Observed facts:

- Small WIP crackme-solving system.
- Uses multi-agent Planning, Execution, Observation, and Criticism roles.
- Integrates pexpect and GDB for interactive/dynamic analysis.

Atomic ideas for RevEng:

- `ADAPT`: use Plan/Observe/Critique as a report workflow, not autonomous execution.
- `TRACK`: dynamic crackme solving stays out of core defensive vNext.

## HELIOS

Observed facts:

- Argues that text-only decompilation ignores CFG/FCG structure.
- Supplies hierarchical graph summaries with basic blocks, successors, loops, conditionals, and raw decompiler output.
- Optional compiler-in-the-loop feedback improves compilability and correctness on benchmark tasks.

Atomic ideas for RevEng:

- `ADOPT`: define a graph summary schema independent of any one disassembler.
- `ADAPT`: implement HELIOS-like summaries for exported Ghidra JSON and source repository call/import graphs.
- `TRACK`: compiler-in-the-loop should be explicit and sandboxed; not automatic for untrusted code.

## CREBench, BinMetric, ReCopilot, SoK

Observed facts:

- CREBench evaluates cryptographic binary RE over algorithm identification, key/IV extraction, wrapper reimplementation, and flag recovery.
- BinMetric introduces a multi-task benchmark over real open-source projects for binary analysis tasks.
- ReCopilot emphasizes call graph and variable data flow context for binary analysis tasks.
- The SoK highlights inconsistent definitions/evaluation and reproducibility gaps across LLM-for-RE work.

Atomic ideas for RevEng:

- `ADOPT`: add small, labeled eval fixtures for each RevEng capability.
- `ADAPT`: create task-specific scoring rather than a single "analysis passed" bit.
- `ADOPT`: record false positives, false negatives, and evidence quality.
- `TRACK`: large academic benchmark reproduction is outside vNext.

## LLM-Resistant Software Protection

Observed facts:

- Models agent RE failures through Observe-Comprehend-Plan.
- Identifies training bias, over-trust in observations, context limitation, and plan persistence.
- Notes that agents can sometimes analyze assembly effectively without a decompiler.

Atomic ideas for RevEng:

- `ADOPT`: add adversarial eval prompts that force hypothesis invalidation.
- `ADOPT`: require negative evidence and alternate hypotheses in deep reports.
- `ADAPT`: add "raw view vs decompiler view" comparison fields when binary graph exports exist.

## Upgrade Implications

Immediate:

- Extend `evals/` with labeled tasks and failure-mode checks.
- Add `case_manifest.json` generation for deep analysis outputs.
- Add graph summary fixtures before requiring real Ghidra/Binary Ninja/IDA installs.

Later:

- Add optional dynamic analysis only as a separate sandboxed phase with explicit operator approval.

