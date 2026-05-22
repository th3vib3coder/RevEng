# Source Selection Matrix

This matrix decides what RevEng should learn from and what it should ignore. "Decision" is about RevEng's upgrade path, not a judgment on the upstream project.

## Selection Criteria

| Criterion | Meaning |
| --- | --- |
| Direct utility | Helps RevEng become stronger without becoming a proprietary-tool wrapper only. |
| Portability | Works conceptually across Codex and Claude Code, Windows and Linux, source repos and binaries. |
| Safety | Supports read-only defaults, isolation, bounded output, or explicit mutation gates. |
| Evidence quality | Primary source is clear enough to support a design decision. |
| Implementation cost | Can be implemented in RevEng without large dependencies or unclear licensing. |

## Adopt Or Adapt

| Source | Evidence | Decision | Why it matters |
| --- | --- | --- | --- |
| `trailofbits/idac` | GitHub README: https://github.com/trailofbits/idac | ADAPT | Agent-native CLI, JSON output, preview/dry-run, batch files, explicit context selection. |
| `mrexodia/ida-pro-mcp` | GitHub README: https://github.com/mrexodia/ida-pro-mcp | ADAPT | Headless `idalib` sessions, context isolation, MCP resources, exact integer conversion guidance. |
| `GameSecurityFrontierLib/ida-pro-mcp-plus` | GitHub README: https://github.com/GameSecurityFrontierLib/ida-pro-mcp-plus | TRACK/ADAPT | Multi-instance, shared-memory IPC, caching, modular tools. Useful pattern, but IDA-specific and not vNext core. |
| `Iamgublin/ida-codex-mcp` | GitHub README: https://github.com/Iamgublin/ida-codex-mcp | TRACK | Simple IDA plugin + stdio MCP bridge. Useful as minimal adapter reference; license is unclear/TBD. |
| `cyberkaida/reverse-engineering-assistant` | GitHub README: https://github.com/cyberkaida/reverse-engineering-assistant | ADOPT/ADAPT | ReVa's tool-driven exploration, headless/assistant modes, context-rot mitigation, and Claude plugin packaging are directly relevant. |
| `LaurieWired/GhidraMCP` | GitHub README: https://github.com/LaurieWired/GhidraMCP | TRACK | Popular baseline Ghidra MCP bridge. Useful to understand common GUI plugin patterns. |
| `13bm/GhidraMCP` | GitHub README: https://github.com/13bm/GhidraMCP | ADAPT | Pagination, async decompilation, multi-instance routing, API-key/local binding. |
| `bethington/ghidra-mcp` | GitHub README: https://github.com/bethington/ghidra-mcp | TRACK | Large tool surface, headless/Docker/lazy tool loading. Good benchmark for breadth, not a direct dependency. |
| `starsong-consulting/GhydraMCP` | GitHub README: https://github.com/starsong-consulting/GhydraMCP | ADAPT | HATEOAS/resource-discovery pattern and structured JSON error envelopes. |
| `mrphrazer/binary-ninja-headless-mcp` | GitHub README: https://github.com/mrphrazer/binary-ninja-headless-mcp | ADOPT/ADAPT | Read-only default, safe mutations, fake backend CI, hard response caps, pagination. |
| `symgraph/BinAssistMCP` | GitHub README: https://github.com/symgraph/BinAssistMCP | ADAPT | Consolidated tools, resources, prompts, multi-binary sessions, async tasks, cache invalidation. |
| `Invoke-RE/binja-lattice-mcp` | GitHub README: https://github.com/Invoke-RE/binja-lattice-mcp | ADAPT | Token auth, local server posture, mutation endpoint separation. |
| `radareorg/radare2-mcp` | GitHub README: https://github.com/radareorg/radare2-mcp | ADOPT/ADAPT | Official radare2 MCP with readonly, sandbox, restricted tools, stdio, HTTP session IDs. |
| `radareorg/r2ai` | GitHub README: https://github.com/radareorg/r2ai | TRACK | Native r2 AI ecosystem; useful for radare-specific future adapters. |
| `Karib0u/kernagent` | GitHub README: https://github.com/Karib0u/kernagent | ADOPT/ADAPT | Deterministic snapshots and "evidence over vibes" match RevEng's corpus model. |
| `mrphrazer/agentic-malware-analysis` | GitHub README: https://github.com/mrphrazer/agentic-malware-analysis | ADOPT/ADAPT | Case directory, Docker co-location, orchestrator skill, multi-tool workflow. |
| `louisgthier/decompai` | GitHub README: https://github.com/louisgthier/decompai | TRACK | LangGraph/Gradio workflow and runner containers are useful, but privileged Docker is too heavy for core RevEng. |
| `aayush0325/reverse-engineering-agent` | GitHub README: https://github.com/aayush0325/reverse-engineering-agent | TRACK | Plan/execute/observe/critic loop is useful conceptually; project is small/WIP. |

## Academic And Research Sources

| Source | Evidence | Decision | Why it matters |
| --- | --- | --- | --- |
| HELIOS | arXiv: https://arxiv.org/abs/2601.14598 | ADOPT/ADAPT | Hierarchical CFG/FCG text abstractions and optional compiler feedback. |
| LLM-resistant software protection | NDSS page: https://www.ndss-symposium.org/ndss-paper/auto-draft-657/ | ADOPT | Observe-Comprehend-Plan failure modes define adversarial evals. |
| CREBench | arXiv: https://arxiv.org/abs/2604.03750 | TRACK/ADAPT | Crypto RE benchmark structure can inspire smaller fixture evals. |
| BinMetric | arXiv: https://arxiv.org/abs/2505.07360 | TRACK/ADAPT | Multi-task benchmark framing for binary analysis quality. |
| ReCopilot | arXiv: https://arxiv.org/abs/2505.16366 | TRACK | Call graph and variable-data-flow context are relevant; model training is out of scope. |
| SoK LLMs for RE | arXiv: https://arxiv.org/abs/2509.21821 | ADOPT as reference | Taxonomy/evaluation gaps justify stricter RevEng evals. |
| Cisco Talos LLM sidekick | Blog: https://blog.talosintelligence.com/using-llm-as-a-reverse-engineering-sidekick/ | ADOPT | Practical MCP security and cost/context cautions. |

## Explicitly Rejected For Core RevEng

| Source class | Decision | Reason |
| --- | --- | --- |
| Reverse-proxy projects for Antigravity/Codex/Copilot accounts | REJECT | Provider policy risk, credential handling risk, and no need for RevEng's plugin goals. |
| Reddit posts and marketplace mirrors | REJECT as primary evidence | Useful for discovery only, not design authority. |
| Star lists and "awesome" lists | REJECT as primary evidence | Aggregators can seed discovery but cannot justify architecture alone. |
| Proprietary-tool-only wrappers as hard dependencies | REJECT | RevEng must remain useful without IDA/Binary Ninja/Ghidra installed. |
| Automatic dynamic malware execution | REJECT | Violates static-first safety unless moved behind explicit PAUSE/sandbox gates. |

