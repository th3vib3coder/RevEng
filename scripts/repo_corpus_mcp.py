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


def tool_result(text: str, structured: dict[str, Any], is_error: bool = False) -> dict[str, Any]:
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
    return {
        "path": record.get("path", ""),
        "kind": record.get("kind", "unknown"),
        "language": record.get("language", "Unknown"),
        "sha256": record.get("sha256", ""),
        "summary": str(record.get("summary", ""))[:MAX_TEXT_CHARS],
        "symbols": list(record.get("symbols", []) or [])[:50],
        "imports": list(record.get("imports", []) or [])[:50],
        "evidence": evidence[:MAX_EVIDENCE_LINES],
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
        {"records": records, "query": query, "nextCursor": next_cursor, "done": done, "limit": limit},
    )


def tool_get_record(corpus: Path, args: dict[str, Any]) -> dict[str, Any]:
    requested = validate_relative_path(require_text_arg(args, "path"))
    for _, record in iter_records(corpus):
        if record.get("path") == requested:
            compact = compact_record(record)
            return tool_result(f"Record found: {requested}", {"record": compact})
    return tool_result(f"Record not found: {requested}", {"record": None, "path": requested})


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
    return tool_result(text, {"matches": matches, "query": query, "nextCursor": next_cursor, "done": done, "limit": limit})


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
        },
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


def handle_tools_call(corpus: Path, params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    args = params.get("arguments", {})
    if not isinstance(name, str) or name not in TOOL_HANDLERS:
        raise KeyError(f"unknown tool: {name!r}")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return tool_error("invalid_arguments", "arguments must be an object", {"arguments": "object"})
    try:
        return TOOL_HANDLERS[name](corpus, args)
    except ToolInputError as exc:
        return tool_error("invalid_arguments", str(exc))


def handle_request(corpus: Path, message: dict[str, Any]) -> dict[str, Any] | None:
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
            return jsonrpc_result(request_id, handle_tools_call(corpus, params))
        return jsonrpc_error(request_id, -32601, f"method not found: {method}")
    except KeyError as exc:
        return jsonrpc_error(request_id, -32602, str(exc))
    except Exception as exc:
        return jsonrpc_error(request_id, -32603, f"internal error: {exc}")


def serve_stdio(corpus: Path) -> int:
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
            response = handle_request(corpus, item)
            if response is not None:
                responses.append(response)
        if isinstance(message, list):
            if responses:
                sys.stdout.write(json.dumps(responses, separators=(",", ":"), sort_keys=True) + "\n")
                sys.stdout.flush()
        elif responses:
            write_message(responses[0])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only MCP stdio server for RevEng repo_corpus.jsonl")
    parser.add_argument("--corpus", required=True, help="Path to repo_corpus.jsonl generated by repo_corpus_export.py")
    args = parser.parse_args()
    return serve_stdio(Path(args.corpus).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
