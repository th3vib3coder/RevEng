# Graph Analysis Schema

RevEng emits a static evidence graph in `repo_map.json` under `graph`. The graph is designed for compact agent navigation, RAG/MCP indexing, and evidence-backed architecture reports. It is not a runtime trace.

## Top-Level Contract

- `schema`: currently `reveng.repo_graph.v1`.
- `nodes`: stable graph nodes sorted by `id`.
- `edges`: stable graph edges sorted by `id`.
- `metrics`: counts by node and edge kind.
- `limitations`: static-analysis caveats.

## Node Contract

Every node has:

- `id`: stable string identifier.
- `kind`: node family.
- `label`: compact human-readable label.

Optional fields include:

- `path`: repository-relative evidence path.
- `language`: detected language for file nodes.
- `file_kind`: source, manifest, config, test, docs, plugin_manifest, or other.
- `module`: Python module name.
- `symbol`: symbol name.
- `route`: `{method, path}` for API/server route nodes.
- `ecosystem`: dependency ecosystem.
- `target`: entrypoint target string.
- `surface`: plugin or agent surface hint.

Current node kinds:

- `file`
- `module`
- `symbol`
- `route`
- `entrypoint`
- `dependency`
- `plugin`
- `external_import`

## Edge Contract

Every edge has:

- `id`: stable string identifier using `edge:<kind>:<from>-><to>`.
- `from`: source node id.
- `to`: target node id.
- `kind`: edge family.
- `evidence`: optional list of source-backed evidence records, normally including `source` and sometimes `line` or `section`.
- `metadata`: optional machine-readable detail such as the original import token.

Current edge kinds:

- `file_defines_symbol`
- `file_represents_module`
- `module_imports_module`
- `module_imports_external`
- `file_exposes_route`
- `route_bound_to_symbol`
- `manifest_declares_entrypoint`
- `manifest_declares_dependency`
- `file_declares_plugin`

## Corpus Linkage

When `repo_corpus_export.py` is run with `--repo-map`, every corpus record includes:

```json
{
  "graph_refs": {
    "nodes": ["file:pkg/cli.py", "module:pkg.cli"],
    "edges": ["edge:file_represents_module:file:pkg/cli.py->module:pkg.cli"]
  }
}
```

`graph_refs` lets an agent move from a file-level corpus record to graph neighborhoods without re-reading the repository from disk.

## MCP Tools

When `repo_corpus_mcp.py` is started with `--repo-map`, the server exposes:

- `reveng.list_graph_nodes`: filter nodes by `kind`, substring `query`, `cursor`, and hard-capped `limit`.
- `reveng.list_graph_edges`: filter edges by `kind`, `from`, `to`, `cursor`, and hard-capped `limit`.
- `reveng.graph_neighbors`: fetch adjacent nodes and edges for one `node_id`, with `direction` (`in`, `out`, `both`) and optional `edge_kind`.

All tools are read-only, cursor-paginated, and return compact text plus `structuredContent`. The `structuredContent.meta` envelope reports `result_count`, `offset`, `next_offset`, `truncated`, and `warnings` consistently across corpus and graph tools.

## Interpretation Rules

- Treat edges as observed static evidence, not proof of runtime execution.
- Prefer graph neighborhoods over dumping large file lists into the model context.
- Cite `evidence.source` and `evidence.line` when using graph relationships in reports.
- Keep unresolved imports as `external_import` nodes unless a later adapter proves an internal target.
