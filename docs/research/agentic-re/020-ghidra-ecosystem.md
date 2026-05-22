# Ghidra Ecosystem Notes

Scope: Ghidra integrations and patterns useful for RevEng's Ghidra/headless and graph-aware roadmap.

## Sources

- NSA Ghidra: https://github.com/NationalSecurityAgency/ghidra
- ReVa / `cyberkaida/reverse-engineering-assistant`: https://github.com/cyberkaida/reverse-engineering-assistant
- `LaurieWired/GhidraMCP`: https://github.com/LaurieWired/GhidraMCP
- `13bm/GhidraMCP`: https://github.com/13bm/GhidraMCP
- `bethington/ghidra-mcp`: https://github.com/bethington/ghidra-mcp
- `starsong-consulting/GhydraMCP`: https://github.com/starsong-consulting/GhydraMCP

## ReVa

Observed facts:

- ReVa is a Ghidra MCP server for AI-assisted reverse engineering.
- It explicitly claims context-rot mitigation for long reverse-engineering tasks.
- It gives decompilation with additional context such as namespace and cross references.
- It supports assistant mode against a running Ghidra UI and headless mode for automation/CI/Docker/PyGhidra.
- Headless projects are session-scoped and automatically cleaned up.
- The repository includes a Claude Code marketplace/plugin package with skills such as Binary Triage, Deep Analysis, Cryptography Analysis, and CTF guides.

Atomic ideas for RevEng:

- `ADOPT`: never dump entire binary analysis into context; expose focused tools and summaries.
- `ADOPT`: every decompiled snippet should carry namespace/xref/caller/callee evidence when available.
- `ADAPT`: add a RevEng "case directory" for session-scoped artifacts and cleanup rules.
- `ADAPT`: make Ghidra analysis modes explicit: `export-only`, `headless-script`, `external-mcp`.
- `TRACK`: full interactive Ghidra UI mode is outside RevEng core but can be documented as an adapter path.

## LaurieWired GhidraMCP

Observed facts:

- Provides a Ghidra plugin plus Python MCP bridge.
- Exposes decompilation, automatic renaming, method/class/import/export listing.
- Uses an absolute path MCP configuration in examples.

Atomic ideas for RevEng:

- `ADAPT`: the plugin+bridge architecture is common, but RevEng should keep path portability and avoid hardcoded absolute examples.
- `TRACK`: useful baseline for user expectations, not a direct implementation model.

## `13bm/GhidraMCP`

Observed facts:

- Exposes 70 MCP tools through a Java Ghidra plugin and Go stdio bridge.
- Supports API-key authentication for the TCP channel.
- Supports multi-instance routing via target ports.
- Supports async decompilation with polling.
- Supports pagination for large functions, strings, imports, and similar result sets.
- Includes CI/CD with Go, Java, Ghidra integration tests, and releases tied to Ghidra versions.

Atomic ideas for RevEng:

- `ADOPT`: long-running analysis should be represented as async jobs with polling rather than blocking tool calls.
- `ADOPT`: list tools must use `offset`/`limit`.
- `ADAPT`: any non-stdio server mode should default to localhost and require an explicit access token.
- `TRACK`: Ghidra-version release automation is useful if RevEng ships a real Ghidra extension later.

## `bethington/ghidra-mcp`

Observed facts:

- Positions itself as a large Ghidra MCP server with 200+ tools.
- Highlights GUI plugin, headless server, lazy tool loading, convention enforcement, batch operations, Ghidra Server integration, and Docker deployment.

Atomic ideas for RevEng:

- `ADAPT`: lazy tool loading is valuable for MCP listTools performance and context size.
- `ADAPT`: convention enforcement should be explicit in skill playbooks and tests.
- `TRACK`: 200+ tool breadth is not a vNext target; RevEng should prefer a smaller reliable surface.

## `GhydraMCP`

Observed facts:

- Provides a modular Ghidra plugin, CLI, and a deprecated MCP bridge.
- Emphasizes a HATEOAS-driven REST API, multi-instance architecture, structured JSON, versioned endpoints, proper HTTP methods/status codes, and discoverable links.
- Supports program analysis, call graphs, data flow, types, memory operations, and modifications.

Atomic ideas for RevEng:

- `ADOPT`: corpus records and MCP responses should include discoverable links to related records when practical.
- `ADOPT`: errors should be structured with `code`, `message`, and remediation hints.
- `ADAPT`: a lightweight HATEOAS pattern can be done inside JSON files without adding a REST server.

## Upgrade Implications

Immediate:

- Expand `ghidra_export_summary.py` schema to support optional CFG/FCG JSON when run inside Ghidra.
- Add `references/graph-analysis-schema.md` with function, block, edge, xref, string, import/export records.
- Add token-safe MCP pages for function lists, strings, xrefs, and graph neighborhoods.

Later:

- Add a true Ghidra smoke test job only when a local Ghidra/PyGhidra install is available.
- Consider a separate RevEng Ghidra extension only after the export schema is stable.

