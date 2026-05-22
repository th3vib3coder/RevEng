# Binary Ninja And Radare2 Ecosystem Notes

Scope: Binary Ninja and radare2 projects that show strong MCP patterns for tool safety, session design, and testing.

## Sources

- `mrphrazer/binary-ninja-headless-mcp`: https://github.com/mrphrazer/binary-ninja-headless-mcp
- `symgraph/BinAssistMCP`: https://github.com/symgraph/BinAssistMCP
- `Invoke-RE/binja-lattice-mcp`: https://github.com/Invoke-RE/binja-lattice-mcp
- `radareorg/radare2-mcp`: https://github.com/radareorg/radare2-mcp
- `radareorg/r2ai`: https://github.com/radareorg/r2ai
- `darallium/r2-copilot`: https://github.com/darallium/r2-copilot

## `binary-ninja-headless-mcp`

Observed facts:

- Exposes 181 tools across 36 groups.
- Defaults sessions to read-only.
- Mutation workflows are guarded by undo/redo and transactions.
- Provides `binja.eval` and `binja.call` for uncovered API access, with security warnings.
- Uses stdio and TCP transports.
- Has fake backend mode for CI without a Binary Ninja license.
- Paginates basic-block APIs and caps memory reads.
- Warns not to expose unauthenticated transports to untrusted users or networks.

Atomic ideas for RevEng:

- `ADOPT`: RevEng MCP tools should remain read-only by default.
- `ADOPT`: hard response caps belong in every bulk/byte/text tool.
- `ADOPT`: fake backend fixtures are the right way to test proprietary-tool adapters.
- `ADAPT`: if RevEng ever adds mutation tools, they require transaction logs, previews, and rollback.
- `REJECT`: unrestricted `eval`-style tools are outside core RevEng.

## `BinAssistMCP`

Observed facts:

- Provides 44 consolidated Binary Ninja tools, MCP resources, and guided prompts.
- Supports multi-binary sessions, LRU analysis cache, async tasks, thread-safe synchronization, and auto-start inside Binary Ninja.
- Uses tool annotations such as read-only/idempotent hints.
- Includes prompts for protocol analysis, vulnerability research, and automated binary analysis.

Atomic ideas for RevEng:

- `ADOPT`: add MCP annotations and explicit idempotence/read-only semantics where client support exists.
- `ADAPT`: turn RevEng skills into guided prompts that call specific tools in a deterministic order.
- `ADAPT`: use cache invalidation metadata in case outputs, not hidden global cache.
- `TRACK`: Binary Ninja-specific protocol workflows can inspire future `protocol-reverse-engineering` skill.

## `binja-lattice-mcp`

Observed facts:

- Provides a token-authenticated HTTP protocol between Binary Ninja and an MCP server.
- Supports optional TLS, token expiration/renewal, local default server posture, and API-key environment configuration.
- Separates binary information, function analysis, data access, type management, and annotation tools.

Atomic ideas for RevEng:

- `ADAPT`: if RevEng exposes a network transport later, require local-only default plus a generated token.
- `ADOPT`: tool categories should be separated by safety class: read-only, data access, type/mutation, execution.
- `TRACK`: TLS/auth patterns become relevant only for a non-stdio RevEng service.

## `radare2-mcp`

Observed facts:

- Official radare2 MCP server.
- Written in C using native r2 APIs.
- Works as CLI, r2 plugin, and MCP server.
- Supports readonly mode, sandbox lock, restricted tools, fine-grained tool configuration, stdio, HTTP mode, and `X-Session-ID` multiplexing.
- Optional raw r2 command/script access exists and is explicitly powerful/dangerous.
- Docker mode is documented.

Atomic ideas for RevEng:

- `ADOPT`: expose a `restricted_tools` concept in adapter manifests.
- `ADOPT`: session IDs are mandatory for any multi-target server.
- `ADAPT`: RevEng can consume radare2/r2mcp outputs through external artifacts without owning the r2 lifecycle.
- `REJECT`: raw command/script passthrough in core RevEng.

## `r2ai` And `r2-copilot`

Observed facts:

- `r2ai` is the official radare2 AI ecosystem and points users to `r2mcp`, `r2copilot`, and `r2agent`.
- `r2-copilot` is a third-party MCP server focused on radare2/CTF usage and stdio startup.

Atomic ideas for RevEng:

- `TRACK`: r2-specific autonomous agents are useful references for future CTF/research mode.
- `ADAPT`: keep CTF workflows separate from defensive malware/report workflows to avoid mixing risk profiles.

## Upgrade Implications

Immediate:

- Add MCP tool metadata fields: `readOnlyHint`, `idempotentHint`, `input_caps`, and `max_result_items` where possible.
- Add adapter safety classes: `read_only`, `mutation_preview`, `mutation_commit`, `execution`, `raw_eval`.
- Add fake-adapter fixtures for binary graph export tests.

Later:

- Add optional radare2 adapter docs only after RevEng's graph schema is stable.

