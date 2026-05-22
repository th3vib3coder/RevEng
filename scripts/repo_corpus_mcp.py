from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


PROTOCOL_VERSION = "2025-11-25"
MAX_LIMIT = 50
DEFAULT_LIMIT = 10
MAX_TEXT_CHARS = 400
MAX_EVIDENCE_LINES = 3


class ToolInputError(ValueError):
    pass


def write_message(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
    sys.stdout.flush()


def jsonrpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def jsonrpc_error(request_id: Any, code: int, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def response_meta(
    *,
    result_count: int = 0,
    offset: int = 0,
    next_offset: int | None = None,
    truncated: bool = False,
    warnings: list[str] | None = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "result_count": result_count,
        "offset": offset,
        "next_offset": next_offset,
        "truncated": truncated,
        "warnings": warnings or [],
    }


def with_meta(
    structured: dict[str, Any],
    *,
    result_count: int = 0,
    offset: int = 0,
    next_offset: int | None = None,
    truncated: bool = False,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    structured["meta"] = response_meta(
        result_count=result_count,
        offset=offset,
        next_offset=next_offset,
        truncated=truncated,
        warnings=warnings,
    )
    return structured


def tool_result(text: str, structured: dict[str, Any], is_error: bool = False) -> dict[str, Any]:
    if "meta" not in structured:
        structured = with_meta(structured)
    return {
        "resultType": "complete",
        "content": [{"type": "text", "text": text[:MAX_TEXT_CHARS]}],
        "structuredContent": structured,
        "isError": is_error,
    }


def tool_error(code: str, message: str, expected: dict[str, Any] | None = None) -> dict[str, Any]:
    structured: dict[str, Any] = {"error": {"code": code, "message": message}}
    if expected is not None:
        structured["error"]["expected"] = expected
    structured = with_meta(structured, warnings=[message])
    return tool_result(f"Error: {message}", structured, is_error=True)


def bounded_limit(value: Any, default: int = DEFAULT_LIMIT) -> int:
    if value is None:
        return default
    if not isinstance(value, int):
        raise ToolInputError("limit must be an integer")
    if value < 1 or value > MAX_LIMIT:
        raise ToolInputError(f"limit must be between 1 and {MAX_LIMIT}")
    return value


def cursor_to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.isdigit():
        parsed = int(value)
    else:
        raise ToolInputError("cursor must be a non-negative integer string")
    if parsed < 0:
        raise ToolInputError("cursor must be non-negative")
    return parsed


def require_text_arg(args: dict[str, Any], name: str, *, allow_empty: bool = False) -> str:
    value = args.get(name)
    if not isinstance(value, str):
        raise ToolInputError(f"{name} must be a string")
    if not allow_empty and not value.strip():
        raise ToolInputError(f"{name} must not be empty")
    return value


def validate_relative_path(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise ToolInputError("path must be repository-relative and must not contain '..'")
    return path.as_posix()


def iter_records(corpus: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with corpus.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                yield line_no, record


def compact_record(record: dict[str, Any]) -> dict[str, Any]:
    evidence = record.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []
    graph_refs = record.get("graph_refs", {})
    if not isinstance(graph_refs, dict):
        graph_refs = {}
    return {
        "path": record.get("path", ""),
        "kind": record.get("kind", "unknown"),
        "language": record.get("language", "Unknown"),
        "sha256": record.get("sha256", ""),
        "summary": str(record.get("summary", ""))[:MAX_TEXT_CHARS],
        "symbols": list(record.get("symbols", []) or [])[:50],
        "imports": list(record.get("imports", []) or [])[:50],
        "evidence": evidence[:MAX_EVIDENCE_LINES],
        "graph_refs": {
            "nodes": list(graph_refs.get("nodes", []) or [])[:50],
            "edges": list(graph_refs.get("edges", []) or [])[:50],
        },
    }


def record_text(record: dict[str, Any]) -> str:
    evidence_text = " ".join(str(item.get("text", "")) for item in record.get("evidence", []) if isinstance(item, dict))
    parts = [
        str(record.get("path", "")),
        str(record.get("kind", "")),
        str(record.get("language", "")),
        str(record.get("summary", "")),
        " ".join(str(item) for item in record.get("symbols", []) or []),
        " ".join(str(item) for item in record.get("imports", []) or []),
        evidence_text,
    ]
    return "\n".join(parts).lower()


def tool_search_corpus(corpus: Path, args: dict[str, Any]) -> dict[str, Any]:
    query = require_text_arg(args, "query").lower()
    limit = bounded_limit(args.get("limit"))
    start_line = cursor_to_int(args.get("cursor"))
    kind = args.get("kind")
    language = args.get("language")
    if kind is not None and not isinstance(kind, str):
        raise ToolInputError("kind must be a string when provided")
    if language is not None and not isinstance(language, str):
        raise ToolInputError("language must be a string when provided")

    records: list[dict[str, Any]] = []
    next_cursor: str | None = None
    for line_no, record in iter_records(corpus):
        if line_no < start_line:
            continue
        if kind and record.get("kind") != kind:
            continue
        if language and record.get("language") != language:
            continue
        if query not in record_text(record):
            continue
        records.append(compact_record(record))
        if len(records) >= limit:
            next_cursor = str(line_no + 1)
            break

    done = next_cursor is None
    text = f"{len(records)} corpus match(es) for '{query}'" + ("" if done else f"; continue with cursor {next_cursor}")
    return tool_result(
        text,
        with_meta(
            {"records": records, "query": query[:MAX_TEXT_CHARS], "nextCursor": next_cursor, "done": done, "limit": limit},
            result_count=len(records),
            offset=start_line,
            next_offset=int(next_cursor) if next_cursor is not None else None,
            truncated=not done,
        ),
    )


def tool_get_record(corpus: Path, args: dict[str, Any]) -> dict[str, Any]:
    requested = validate_relative_path(require_text_arg(args, "path"))
    for _, record in iter_records(corpus):
        if record.get("path") == requested:
            compact = compact_record(record)
            return tool_result(f"Record found: {requested}", with_meta({"record": compact}, result_count=1))
    return tool_result(
        f"Record not found: {requested}",
        with_meta({"record": None, "path": requested}, warnings=[f"record not found: {requested}"]),
    )


def tool_list_symbols(corpus: Path, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", "")).lower()
    limit = bounded_limit(args.get("limit"))
    start_match = cursor_to_int(args.get("cursor"))
    matches: list[dict[str, Any]] = []
    seen_matches = 0
    next_cursor: str | None = None
    for _, record in iter_records(corpus):
        symbols = record.get("symbols", []) or []
        for symbol in symbols:
            symbol_text = str(symbol)
            if query and query not in symbol_text.lower():
                continue
            if seen_matches < start_match:
                seen_matches += 1
                continue
            matches.append(
                {
                    "path": record.get("path", ""),
                    "language": record.get("language", "Unknown"),
                    "symbol": symbol_text,
                    "summary": str(record.get("summary", ""))[:MAX_TEXT_CHARS],
                }
            )
            seen_matches += 1
            if len(matches) >= limit:
                next_cursor = str(seen_matches)
                break
        if next_cursor is not None:
            break
    done = next_cursor is None
    text = f"{len(matches)} symbol match(es)" + ("" if done else f"; continue with cursor {next_cursor}")
    return tool_result(
        text,
        with_meta(
            {"matches": matches, "query": query[:MAX_TEXT_CHARS], "nextCursor": next_cursor, "done": done, "limit": limit},
            result_count=len(matches),
            offset=start_match,
            next_offset=int(next_cursor) if next_cursor is not None else None,
            truncated=not done,
        ),
    )


def tool_corpus_summary(corpus: Path, args: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    languages: dict[str, int] = {}
    total = 0
    for _, record in iter_records(corpus):
        total += 1
        kind = str(record.get("kind", "unknown"))
        language = str(record.get("language", "Unknown"))
        counts[kind] = counts.get(kind, 0) + 1
        languages[language] = languages.get(language, 0) + 1
    return tool_result(
        f"Corpus contains {total} record(s)",
        {
            "path": str(corpus),
            "records": total,
            "kinds": dict(sorted(counts.items())),
            "languages": dict(sorted(languages.items())),
            "meta": response_meta(result_count=total),
        },
    )


def limited_dict(items: dict[Any, Any], limit: int) -> tuple[dict[str, Any], bool]:
    sorted_items = sorted((str(key), value) for key, value in items.items())
    return dict(sorted_items[:limit]), len(sorted_items) > limit


def module_graph_metrics_view(metrics: Any, module: str | None, limit: int) -> dict[str, Any]:
    if not isinstance(metrics, dict):
        return {"fan_in": {}, "fan_out": {}, "cycles": [], "truncated": False}
    fan_in = metrics.get("fan_in", {})
    fan_out = metrics.get("fan_out", {})
    cycles = metrics.get("cycles", [])
    if not isinstance(fan_in, dict):
        fan_in = {}
    if not isinstance(fan_out, dict):
        fan_out = {}
    if not isinstance(cycles, list):
        cycles = []
    clean_cycles = [
        [str(item) for item in cycle]
        for cycle in cycles
        if isinstance(cycle, list)
    ]
    if module is None:
        fan_in_view, fan_in_truncated = limited_dict(fan_in, limit)
        fan_out_view, fan_out_truncated = limited_dict(fan_out, limit)
        return {
            "fan_in": fan_in_view,
            "fan_out": fan_out_view,
            "cycles": clean_cycles[:limit],
            "truncated": fan_in_truncated or fan_out_truncated or len(clean_cycles) > limit,
        }
    filtered_cycles = [cycle for cycle in clean_cycles if module in cycle]
    return {
        "fan_in": {module: fan_in.get(module, 0)},
        "fan_out": {module: fan_out.get(module, 0)},
        "cycles": filtered_cycles[:limit],
        "truncated": len(filtered_cycles) > limit,
    }


def graph_unavailable_error() -> dict[str, Any]:
    return tool_error(
        "graph_unavailable",
        "repo graph not loaded; start the server with --repo-map <repo_map.json>",
    )


def clean_graph_nodes(repo_graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for node in repo_graph.get("nodes", []) or []:
        if isinstance(node, dict) and isinstance(node.get("id"), str):
            nodes.append(node)
    return sorted(nodes, key=lambda item: item["id"])


def clean_graph_edges(repo_graph: dict[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for edge in repo_graph.get("edges", []) or []:
        if (
            isinstance(edge, dict)
            and isinstance(edge.get("id"), str)
            and isinstance(edge.get("from"), str)
            and isinstance(edge.get("to"), str)
        ):
            edges.append(edge)
    return sorted(edges, key=lambda item: item["id"])


def compact_graph_node(node: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "id": node.get("id", ""),
        "kind": node.get("kind", "unknown"),
        "label": str(node.get("label", ""))[:MAX_TEXT_CHARS],
    }
    for key in ("path", "language", "file_kind", "module", "symbol", "ecosystem", "surface", "entrypoint_kind"):
        if key in node:
            compact[key] = node[key]
    if "route" in node and isinstance(node["route"], dict):
        compact["route"] = node["route"]
    if "target" in node:
        compact["target"] = str(node["target"])[:MAX_TEXT_CHARS]
    return compact


def compact_graph_edge(edge: dict[str, Any]) -> dict[str, Any]:
    evidence = edge.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []
    compact = {
        "id": edge.get("id", ""),
        "from": edge.get("from", ""),
        "to": edge.get("to", ""),
        "kind": edge.get("kind", "unknown"),
        "evidence": evidence[:MAX_EVIDENCE_LINES],
    }
    if isinstance(edge.get("metadata"), dict):
        compact["metadata"] = edge["metadata"]
    return compact


def tool_list_graph_nodes(repo_graph: dict[str, Any] | None, args: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(repo_graph, dict):
        return graph_unavailable_error()
    kind = args.get("kind")
    query = str(args.get("query", "")).lower()
    if kind is not None and not isinstance(kind, str):
        raise ToolInputError("kind must be a string when provided")
    limit = bounded_limit(args.get("limit"))
    start = cursor_to_int(args.get("cursor"))
    nodes = clean_graph_nodes(repo_graph)
    filtered: list[dict[str, Any]] = []
    for node in nodes:
        if kind and node.get("kind") != kind:
            continue
        haystack = "\n".join(str(node.get(key, "")) for key in ("id", "kind", "label", "path", "module", "symbol")).lower()
        if query and query not in haystack:
            continue
        filtered.append(node)
    page = filtered[start : start + limit]
    next_cursor = str(start + limit) if start + limit < len(filtered) else None
    done = next_cursor is None
    text = f"{len(page)} graph node(s)" + ("" if done else f"; cursor {next_cursor}")
    return tool_result(
        text,
        with_meta(
            {
            "nodes": [compact_graph_node(node) for node in page],
            "kind": kind,
            "query": query[:MAX_TEXT_CHARS],
            "nextCursor": next_cursor,
            "done": done,
            "limit": limit,
            },
            result_count=len(page),
            offset=start,
            next_offset=int(next_cursor) if next_cursor is not None else None,
            truncated=not done,
        ),
    )


def tool_list_graph_edges(repo_graph: dict[str, Any] | None, args: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(repo_graph, dict):
        return graph_unavailable_error()
    kind = args.get("kind")
    src = args.get("from")
    dst = args.get("to")
    for name, value in (("kind", kind), ("from", src), ("to", dst)):
        if value is not None and not isinstance(value, str):
            raise ToolInputError(f"{name} must be a string when provided")
    limit = bounded_limit(args.get("limit"))
    start = cursor_to_int(args.get("cursor"))
    filtered: list[dict[str, Any]] = []
    for edge in clean_graph_edges(repo_graph):
        if kind and edge.get("kind") != kind:
            continue
        if src and edge.get("from") != src:
            continue
        if dst and edge.get("to") != dst:
            continue
        filtered.append(edge)
    page = filtered[start : start + limit]
    next_cursor = str(start + limit) if start + limit < len(filtered) else None
    done = next_cursor is None
    text = f"{len(page)} graph edge(s)" + ("" if done else f"; cursor {next_cursor}")
    return tool_result(
        text,
        with_meta(
            {
            "edges": [compact_graph_edge(edge) for edge in page],
            "kind": kind,
            "from": src,
            "to": dst,
            "nextCursor": next_cursor,
            "done": done,
            "limit": limit,
            },
            result_count=len(page),
            offset=start,
            next_offset=int(next_cursor) if next_cursor is not None else None,
            truncated=not done,
        ),
    )


def tool_graph_neighbors(repo_graph: dict[str, Any] | None, args: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(repo_graph, dict):
        return graph_unavailable_error()
    node_id = require_text_arg(args, "node_id")
    direction = args.get("direction", "both")
    if direction not in ("in", "out", "both"):
        raise ToolInputError("direction must be one of: in, out, both")
    edge_kind = args.get("edge_kind")
    if edge_kind is not None and not isinstance(edge_kind, str):
        raise ToolInputError("edge_kind must be a string when provided")
    limit = bounded_limit(args.get("limit"))
    start = cursor_to_int(args.get("cursor"))
    nodes_by_id = {node["id"]: node for node in clean_graph_nodes(repo_graph)}
    if node_id not in nodes_by_id:
        return tool_result(
            f"Graph node not found: {node_id}",
            with_meta(
                {"node_id": node_id, "nodes": [], "edges": [], "nextCursor": None, "done": True, "limit": limit},
                warnings=[f"graph node not found: {node_id}"],
            ),
        )

    filtered: list[dict[str, Any]] = []
    for edge in clean_graph_edges(repo_graph):
        outgoing = edge.get("from") == node_id
        incoming = edge.get("to") == node_id
        if direction == "out" and not outgoing:
            continue
        if direction == "in" and not incoming:
            continue
        if direction == "both" and not (outgoing or incoming):
            continue
        if edge_kind and edge.get("kind") != edge_kind:
            continue
        filtered.append(edge)
    page = filtered[start : start + limit]
    next_cursor = str(start + limit) if start + limit < len(filtered) else None
    adjacent_ids: set[str] = set()
    for edge in page:
        if edge.get("from") == node_id:
            adjacent_ids.add(str(edge.get("to")))
        if edge.get("to") == node_id:
            adjacent_ids.add(str(edge.get("from")))
    adjacent_nodes = [nodes_by_id[adjacent_id] for adjacent_id in sorted(adjacent_ids) if adjacent_id in nodes_by_id]
    done = next_cursor is None
    text = f"{len(page)} neighbor edge(s) for {node_id}" + ("" if done else f"; cursor {next_cursor}")
    return tool_result(
        text,
        with_meta(
            {
            "node_id": node_id,
            "direction": direction,
            "edge_kind": edge_kind,
            "nodes": [compact_graph_node(node) for node in adjacent_nodes],
            "edges": [compact_graph_edge(edge) for edge in page],
            "nextCursor": next_cursor,
            "done": done,
            "limit": limit,
            },
            result_count=len(page),
            offset=start,
            next_offset=int(next_cursor) if next_cursor is not None else None,
            truncated=not done,
        ),
    )


def tool_module_graph(module_graph: dict[str, Any] | None, args: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(module_graph, dict):
        return tool_error(
            "graph_unavailable",
            "module graph not loaded; start the server with --repo-map <repo_map.json>",
        )
    module = args.get("module")
    if module is not None and not isinstance(module, str):
        raise ToolInputError("module must be a string when provided")
    direction = args.get("direction", "both")
    if direction not in ("dependencies", "dependents", "both"):
        raise ToolInputError("direction must be one of: dependencies, dependents, both")
    limit = bounded_limit(args.get("limit"))
    start = cursor_to_int(args.get("cursor"))
    edges = [edge for edge in (module_graph.get("edges") or []) if isinstance(edge, dict)]

    def keep(edge: dict[str, Any]) -> bool:
        if module is None:
            return True
        if direction == "dependencies":
            return edge.get("from") == module
        if direction == "dependents":
            return edge.get("to") == module
        return edge.get("from") == module or edge.get("to") == module

    filtered = [edge for edge in edges if keep(edge)]
    page = filtered[start : start + limit]
    next_cursor = str(start + limit) if start + limit < len(filtered) else None
    external = [
        item
        for item in (module_graph.get("external_imports") or [])
        if isinstance(item, dict) and (module is None or item.get("from") == module)
    ][:MAX_LIMIT]
    done = next_cursor is None
    text = f"{len(page)} edge(s)" + (f" for '{module}'" if module else "") + ("" if done else f"; cursor {next_cursor}")
    return tool_result(
        text,
        with_meta(
            {
            "edges": page,
            "external_imports": external,
            "metrics": module_graph_metrics_view(module_graph.get("metrics"), module, limit),
            "module": module,
            "direction": direction,
            "nextCursor": next_cursor,
            "done": done,
            "limit": limit,
            },
            result_count=len(page),
            offset=start,
            next_offset=int(next_cursor) if next_cursor is not None else None,
            truncated=not done,
        ),
    )


TOOLS: list[dict[str, Any]] = [
    {
        "name": "reveng.corpus_summary",
        "title": "RevEng Corpus Summary",
        "description": "Summarize the loaded RevEng repo_corpus.jsonl without reading source files or executing code.",
        "inputSchema": {"type": "object", "additionalProperties": False},
    },
    {
        "name": "reveng.get_record",
        "title": "RevEng Get Corpus Record",
        "description": "Return one corpus record by repository-relative path with compact evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Repository-relative path in the corpus"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "reveng.graph_neighbors",
        "title": "RevEng Graph Neighbors",
        "description": "Return adjacent repo graph nodes and edges for one node id. Read-only; requires --repo-map.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "direction": {"type": "string", "enum": ["in", "out", "both"]},
                "edge_kind": {"type": "string"},
                "cursor": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT},
            },
            "required": ["node_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "reveng.list_graph_edges",
        "title": "RevEng List Graph Edges",
        "description": "List repo graph edges with kind/source/target filters and cursor pagination. Read-only; requires --repo-map.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
                "from": {"type": "string"},
                "to": {"type": "string"},
                "cursor": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "reveng.list_graph_nodes",
        "title": "RevEng List Graph Nodes",
        "description": "List repo graph nodes with kind/query filters and cursor pagination. Read-only; requires --repo-map.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
                "query": {"type": "string"},
                "cursor": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "reveng.list_symbols",
        "title": "RevEng List Symbols",
        "description": "List symbol hints from the corpus with cursor pagination. Does not execute repository code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional case-insensitive substring filter"},
                "cursor": {"type": "string", "description": "Opaque cursor from the previous response"},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "reveng.module_graph",
        "title": "RevEng Module Graph",
        "description": "Query the Python module dependency graph (internal edges + external imports) from repo_map.json. Read-only; requires the server started with --repo-map.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "module": {"type": "string", "description": "Optional module to filter, e.g. pkg.cli"},
                "direction": {"type": "string", "enum": ["dependencies", "dependents", "both"]},
                "cursor": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "reveng.search_corpus",
        "title": "RevEng Search Corpus",
        "description": "Search path, summary, symbols, imports, and evidence in repo_corpus.jsonl with hard-capped pagination.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "kind": {"type": "string"},
                "language": {"type": "string"},
                "cursor": {"type": "string", "description": "Cursor from previous response"},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
]

TOOL_HANDLERS = {
    "reveng.corpus_summary": tool_corpus_summary,
    "reveng.get_record": tool_get_record,
    "reveng.list_symbols": tool_list_symbols,
    "reveng.search_corpus": tool_search_corpus,
}

GRAPH_TOOL_HANDLERS = {
    "reveng.graph_neighbors": tool_graph_neighbors,
    "reveng.list_graph_edges": tool_list_graph_edges,
    "reveng.list_graph_nodes": tool_list_graph_nodes,
}


def handle_initialize(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {
            "name": "reveng-corpus-mcp",
            "title": "RevEng Corpus MCP",
            "version": "0.1.0",
            "description": "Read-only MCP server for RevEng repo_corpus.jsonl analysis.",
        },
        "instructions": (
            "Use these tools for static, evidence-backed repository corpus queries. "
            "All responses are paginated and include structuredContent plus compact text."
        ),
    }


def handle_tools_call(
    corpus: Path,
    module_graph: dict[str, Any] | None,
    repo_graph: dict[str, Any] | None,
    params: dict[str, Any],
) -> dict[str, Any]:
    name = params.get("name")
    args = params.get("arguments", {})
    if not isinstance(name, str) or (name not in TOOL_HANDLERS and name not in GRAPH_TOOL_HANDLERS and name != "reveng.module_graph"):
        raise KeyError(f"unknown tool: {name!r}")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return tool_error("invalid_arguments", "arguments must be an object", {"arguments": "object"})
    try:
        if name == "reveng.module_graph":
            return tool_module_graph(module_graph, args)
        if name in GRAPH_TOOL_HANDLERS:
            return GRAPH_TOOL_HANDLERS[name](repo_graph, args)
        return TOOL_HANDLERS[name](corpus, args)
    except ToolInputError as exc:
        return tool_error("invalid_arguments", str(exc))


def handle_request(
    corpus: Path,
    module_graph: dict[str, Any] | None,
    repo_graph: dict[str, Any] | None,
    message: dict[str, Any],
) -> dict[str, Any] | None:
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params", {})
    if "id" not in message:
        return None
    if not isinstance(params, dict):
        return jsonrpc_error(request_id, -32602, "params must be an object")
    try:
        if method == "initialize":
            return jsonrpc_result(request_id, handle_initialize(params))
        if method == "ping":
            return jsonrpc_result(request_id, {})
        if method == "tools/list":
            return jsonrpc_result(request_id, {"resultType": "complete", "tools": TOOLS})
        if method == "tools/call":
            return jsonrpc_result(request_id, handle_tools_call(corpus, module_graph, repo_graph, params))
        return jsonrpc_error(request_id, -32601, f"method not found: {method}")
    except KeyError as exc:
        return jsonrpc_error(request_id, -32602, str(exc))
    except Exception as exc:
        return jsonrpc_error(request_id, -32603, f"internal error: {exc}")


def serve_stdio(corpus: Path, module_graph: dict[str, Any] | None, repo_graph: dict[str, Any] | None) -> int:
    if not corpus.is_file():
        raise SystemExit(f"corpus not found: {corpus}")
    for line in sys.stdin:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            message = json.loads(stripped)
        except json.JSONDecodeError as exc:
            write_message(jsonrpc_error(None, -32700, f"parse error: {exc}"))
            continue
        messages = message if isinstance(message, list) else [message]
        responses: list[dict[str, Any]] = []
        for item in messages:
            if not isinstance(item, dict):
                responses.append(jsonrpc_error(None, -32600, "invalid request"))
                continue
            response = handle_request(corpus, module_graph, repo_graph, item)
            if response is not None:
                responses.append(response)
        if isinstance(message, list):
            if responses:
                sys.stdout.write(json.dumps(responses, separators=(",", ":"), sort_keys=True) + "\n")
                sys.stdout.flush()
        elif responses:
            write_message(responses[0])
    return 0


def load_repo_map(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def load_module_graph(repo_map: dict[str, Any] | None) -> dict[str, Any] | None:
    graph = repo_map.get("module_graph") if isinstance(repo_map, dict) else None
    return graph if isinstance(graph, dict) else None


def load_repo_graph(repo_map: dict[str, Any] | None) -> dict[str, Any] | None:
    graph = repo_map.get("graph") if isinstance(repo_map, dict) else None
    return graph if isinstance(graph, dict) else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only MCP stdio server for RevEng repo_corpus.jsonl")
    parser.add_argument("--corpus", required=True, help="Path to repo_corpus.jsonl generated by repo_corpus_export.py")
    parser.add_argument("--repo-map", help="Optional repo_map.json to enable module graph and general repo graph tools")
    args = parser.parse_args()
    repo_map = load_repo_map(Path(args.repo_map)) if args.repo_map else None
    module_graph = load_module_graph(repo_map)
    repo_graph = load_repo_graph(repo_map)
    return serve_stdio(Path(args.corpus).resolve(), module_graph, repo_graph)


if __name__ == "__main__":
    raise SystemExit(main())
