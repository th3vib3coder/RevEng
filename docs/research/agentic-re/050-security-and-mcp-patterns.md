# Security And MCP Design Patterns

Scope: safety requirements before RevEng grows more powerful.

## Sources

- Cisco Talos, "Using LLMs as a reverse engineering sidekick": https://blog.talosintelligence.com/using-llm-as-a-reverse-engineering-sidekick/
- `binary-ninja-headless-mcp`: https://github.com/mrphrazer/binary-ninja-headless-mcp
- `radare2-mcp`: https://github.com/radareorg/radare2-mcp
- `13bm/GhidraMCP`: https://github.com/13bm/GhidraMCP
- `GhydraMCP`: https://github.com/starsong-consulting/GhydraMCP
- Google Antigravity SDK: https://github.com/google-antigravity/antigravity-sdk-python
- `anti-api`: https://github.com/ink1ing/anti-api

## MCP Threat Model

Observed source themes:

- MCP tools can expose file, network, disassembler, debugger, or code execution capabilities.
- Tool descriptions and returned artifacts become model context.
- Malware strings, function names, comments, and decompiler output can contain prompt-injection payloads.
- Tool output can grow large enough to create token/cost/context failures.
- Unauthenticated local servers become risky if exposed through TCP, tunnels, or remote access.

RevEng decision:

- `ADOPT`: treat every analyzed file and every extracted string as untrusted input.
- `ADOPT`: keep stdio as the default transport.
- `ADOPT`: all network transports, if ever added, must default to localhost and require an explicit token.
- `ADOPT`: never enable raw eval, shell, debugger, or mutation tools in core MCP.

## Read-Only Defaults

Observed patterns:

- Binary Ninja headless MCP defaults sessions to read-only and only allows safe mutation workflows.
- radare2-mcp supports readonly mode, sandbox locks, restricted tools, and fine-grained tool configuration.
- Antigravity SDK defaults the simple agent to read-only unless capabilities are expanded.

RevEng decision:

- `ADOPT`: RevEng MCP remains read-only for vNext.
- `ADOPT`: any future write/mutate/debug/run feature must be a separate skill and require PAUSE.
- `ADOPT`: tool metadata should advertise read-only/idempotent behavior.

## Token-Safe Output

Observed patterns:

- ReVa limits context rot by making the agent explore through tools rather than dumping all output.
- 13bm GhidraMCP paginates large result sets.
- Binary Ninja headless MCP caps memory reads and paginates basic blocks.
- Talos warns that MCP tool instructions and outputs can create very large prompts and high cost.

RevEng decision:

- `ADOPT`: all list/search tools require `limit` and `offset`/cursor support.
- `ADOPT`: all byte/text tools require hard max response caps.
- `ADOPT`: return compact text summaries plus structured JSON where possible.
- `ADOPT`: never put full file contents in MCP responses unless explicitly bounded.

## Structured Errors And Schema Tolerance

Observed patterns:

- GhydraMCP documents structured success/error responses with codes, messages, status, and links.
- ReVa emphasizes robust tool-driven workflows that can recover from tool-level issues.

RevEng decision:

- `ADOPT`: invalid tool inputs return `isError: true` with machine-readable `code`, `message`, and expected schema.
- `ADOPT`: errors should recommend the next safe call when possible.
- `ADAPT`: keep implementation dependency-free; use internal validators rather than Pydantic for now.

## Session And Case Isolation

Observed patterns:

- IDA idalib MCP supports isolated contexts.
- radare2-mcp supports HTTP session multiplexing with `X-Session-ID`.
- BinAssistMCP supports multi-binary context management.
- ReVa headless mode creates session-scoped projects.

RevEng decision:

- `ADOPT`: introduce `case_id` and `case_manifest.json` for deep analysis.
- `ADOPT`: MCP tools should require or expose the active corpus/case path.
- `ADAPT`: source repository analysis can keep file-based isolation before adding a long-running service.

## Rejected Safety Patterns

| Pattern | Decision | Reason |
| --- | --- | --- |
| Unauthenticated TCP exposed beyond localhost | REJECT | Easy accidental exposure. |
| Raw Python/IDA/Binja/r2 eval from MCP | REJECT | Too much privilege for untrusted context. |
| Reverse-proxying provider accounts | REJECT | Credential and provider-policy risk; irrelevant to RevEng core. |
| Privileged Docker runner as default | REJECT | Too broad for static-first vNext. |
| Automatic package manager/build/test execution | REJECT | Supply-chain risk unless operator approves. |

## Upgrade Implications

Immediate:

- Add a `security_model` section to MCP docs.
- Add input taint labels for corpus records derived from untrusted files.
- Add structured error codes to `repo_corpus_mcp.py`.
- Add tests for cursor pagination, cap enforcement, and injection-looking strings staying data-only.

Later:

- Add an optional sandbox profile for dynamic analysis, but keep it out of default workflows.

