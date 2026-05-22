from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from repo_common import classify_kind, detect_language, iter_repo_files, load_json, python_definitions, read_text, repo_relative, write_json

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


ROUTE_PATTERNS = [
    ("python", re.compile(r"@\w+\.(get|post|put|delete|patch|route)\(\s*['\"]([^'\"]+)['\"]", re.I)),
    ("javascript", re.compile(r"\b(?:app|router)\.(get|post|put|delete|patch|use)\(\s*['\"`]([^'\"`]+)['\"`]", re.I)),
]

IMPORT_PATTERNS = [
    re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.M),
    re.compile(r"^\s*import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]", re.M),
    re.compile(r"\brequire\(\s*['\"]([^'\"]+)['\"]\s*\)", re.M),
]

SYMBOL_PATTERNS = [
    re.compile(r"^\s*(?:def|async def)\s+([A-Za-z_][\w]*)\s*\(", re.M),
    re.compile(r"^\s*class\s+([A-Za-z_][\w]*)\b", re.M),
    re.compile(r"^\s*(?:export\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", re.M),
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=", re.M),
]

PYTHON_SUFFIXES = {".py", ".pyi"}


def parse_toml_array_items(text: str) -> list[str]:
    items: list[str] = []
    for chunk in text.split(","):
        item = chunk.strip().strip("'\"")
        if item:
            items.append(item)
    return items


def parse_pyproject_fallback(text: str) -> dict[str, Any]:
    project: dict[str, Any] = {"scripts": {}, "dependencies": []}
    section = ""
    collecting_dependencies = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if collecting_dependencies:
            if "]" in line:
                project["dependencies"].extend(parse_toml_array_items(line.split("]", 1)[0]))
                collecting_dependencies = False
            else:
                project["dependencies"].extend(parse_toml_array_items(line))
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.strip("[]")
            continue
        if section == "project" and line.startswith("dependencies") and "=" in line:
            value = line.split("=", 1)[1].strip()
            if value.startswith("["):
                values = value.split("[", 1)[1]
                if "]" in values:
                    project["dependencies"] = parse_toml_array_items(values.rsplit("]", 1)[0])
                else:
                    project["dependencies"].extend(parse_toml_array_items(values))
                    collecting_dependencies = True
        elif section == "project.scripts" and "=" in line:
            name, target = line.split("=", 1)
            project["scripts"][name.strip().strip("'\"")] = target.strip().strip("'\"")
    return {"project": project}


def parse_pyproject(path: Path, rel: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    text = read_text(path)
    try:
        data = tomllib.loads(text) if tomllib is not None else parse_pyproject_fallback(text)
    except Exception:
        data = parse_pyproject_fallback(text)
    project = data.get("project", {})
    entrypoints = [
        {"kind": "python_script", "name": name, "target": target, "source": rel}
        for name, target in sorted(project.get("scripts", {}).items())
    ]
    deps = [
        {"ecosystem": "python", "name": dep, "source": rel, "section": "project.dependencies"}
        for dep in project.get("dependencies", [])
    ]
    for group, values in sorted(project.get("optional-dependencies", {}).items()):
        deps.extend({"ecosystem": "python", "name": dep, "source": rel, "section": f"project.optional-dependencies.{group}"} for dep in values)
    return entrypoints, deps


def parse_package_json(path: Path, rel: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = load_json(path)
    entrypoints: list[dict[str, Any]] = []
    for name, command in sorted(data.get("scripts", {}).items()):
        entrypoints.append({"kind": "npm_script", "name": name, "target": command, "source": rel})
    if "main" in data:
        entrypoints.append({"kind": "node_main", "name": "main", "target": data["main"], "source": rel})
    bin_value = data.get("bin")
    if isinstance(bin_value, dict):
        for name, target in sorted(bin_value.items()):
            entrypoints.append({"kind": "node_bin", "name": name, "target": target, "source": rel})
    elif isinstance(bin_value, str):
        entrypoints.append({"kind": "node_bin", "name": data.get("name", "bin"), "target": bin_value, "source": rel})

    deps: list[dict[str, Any]] = []
    for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        for name, version in sorted(data.get(section, {}).items()):
            deps.append({"ecosystem": "node", "name": name, "version": version, "source": rel, "section": section})
    return entrypoints, deps


def extract_imports(text: str) -> list[str]:
    imports: set[str] = set()
    for pattern in IMPORT_PATTERNS:
        for match in pattern.finditer(text):
            for group in match.groups():
                if group:
                    imports.add(group)
    return sorted(imports)


def extract_symbols(text: str) -> list[str]:
    symbols: set[str] = set()
    for pattern in SYMBOL_PATTERNS:
        symbols.update(match.group(1) for match in pattern.finditer(text))
    return sorted(symbols)


def extract_routes(text: str, rel: str) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    for framework, pattern in ROUTE_PATTERNS:
        for match in pattern.finditer(text):
            method = match.group(1).upper()
            path = match.group(2)
            line = text[: match.start()].count("\n") + 1
            routes.append({"framework_hint": framework, "method": method, "path": path, "source": rel, "line": line})
    return routes


def python_module_name(root: Path, path: Path) -> str:
    rel = path.relative_to(root)
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def resolve_python_import(import_name: str, from_module: str, modules: set[str]) -> str | None:
    if import_name.startswith("."):
        level = len(import_name) - len(import_name.lstrip("."))
        remainder = import_name[level:]
        from_parts = from_module.split(".")
        if level > len(from_parts):
            return None
        base_parts = from_parts[:-level]
        target = ".".join(part for part in [*base_parts, remainder] if part)
        return target if target in modules else None

    parts = import_name.split(".")
    for end in range(len(parts), 0, -1):
        candidate = ".".join(parts[:end])
        if candidate in modules:
            return candidate
    return None


def build_python_module_graph(
    python_modules: dict[str, str],
    python_imports: dict[str, list[str]],
) -> dict[str, Any]:
    module_names = set(python_modules)
    edges: list[dict[str, str]] = []
    external_imports: list[dict[str, str]] = []
    for from_module, imports in sorted(python_imports.items()):
        for import_name in imports:
            target = resolve_python_import(import_name, from_module, module_names)
            if target and target != from_module:
                edges.append(
                    {
                        "from": from_module,
                        "from_path": python_modules[from_module],
                        "to": target,
                        "to_path": python_modules[target],
                        "import": import_name,
                    }
                )
            elif not target:
                external_imports.append(
                    {
                        "from": from_module,
                        "from_path": python_modules[from_module],
                        "import": import_name,
                    }
                )
    return {
        "modules": [
            {"module": module, "path": python_modules[module]}
            for module in sorted(python_modules)
            if module
        ],
        "edges": sorted(edges, key=lambda item: (item["from"], item["to"], item["import"])),
        "external_imports": sorted(external_imports, key=lambda item: (item["from"], item["import"])),
        "metrics": module_graph_metrics([module for module in sorted(python_modules) if module], edges),
        "limitations": [
            "Python module graph is static and import-derived; dynamic imports and runtime path mutation are not resolved.",
            "JavaScript/TypeScript and other language graphs are not built in this zero-dependency implementation.",
        ],
    }


def strongly_connected_cycles(adjacency: dict[str, set[str]]) -> list[list[str]]:
    """Return strongly connected components with more than one node (import cycles).

    Iterative Tarjan so a deep dependency graph cannot exhaust the recursion stack.
    """
    index_counter = 0
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    stack: list[str] = []
    components: list[list[str]] = []
    for start in sorted(adjacency):
        if start in indices:
            continue
        indices[start] = lowlink[start] = index_counter
        index_counter += 1
        stack.append(start)
        on_stack[start] = True
        work: list[tuple[str, Any]] = [(start, iter(sorted(adjacency.get(start, set()))))]
        while work:
            node, successors = work[-1]
            advanced = False
            for successor in successors:
                if successor not in indices:
                    indices[successor] = lowlink[successor] = index_counter
                    index_counter += 1
                    stack.append(successor)
                    on_stack[successor] = True
                    work.append((successor, iter(sorted(adjacency.get(successor, set())))))
                    advanced = True
                    break
                if on_stack.get(successor):
                    lowlink[node] = min(lowlink[node], indices[successor])
            if advanced:
                continue
            if lowlink[node] == indices[node]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack[member] = False
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    components.append(sorted(component))
            work.pop()
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])
    return components


def module_graph_metrics(modules: list[str], edges: list[dict[str, Any]]) -> dict[str, Any]:
    adjacency: dict[str, set[str]] = {module: set() for module in modules}
    fan_in: dict[str, int] = {module: 0 for module in modules}
    fan_out: dict[str, int] = {module: 0 for module in modules}
    self_loops: list[str] = []
    counted: set[tuple[str, str]] = set()
    for edge in edges:
        src = edge.get("from")
        dst = edge.get("to")
        if not isinstance(src, str) or not isinstance(dst, str):
            continue
        if src == dst:
            if src not in self_loops:
                self_loops.append(src)
            continue
        if (src, dst) in counted:
            continue
        counted.add((src, dst))
        adjacency.setdefault(src, set()).add(dst)
        adjacency.setdefault(dst, set())
        fan_out[src] = fan_out.get(src, 0) + 1
        fan_in[dst] = fan_in.get(dst, 0) + 1
    cycles = strongly_connected_cycles(adjacency)
    cycles.extend([node] for node in sorted(self_loops))
    return {
        "fan_in": dict(sorted(fan_in.items())),
        "fan_out": dict(sorted(fan_out.items())),
        "cycles": sorted(cycles),
    }


def edge_id(kind: str, src: str, dst: str) -> str:
    return f"edge:{kind}:{src}->{dst}"


def add_node(nodes: dict[str, dict[str, Any]], node_id: str, kind: str, label: str, **fields: Any) -> None:
    node = {"id": node_id, "kind": kind, "label": label}
    for key, value in fields.items():
        if value not in (None, "", [], {}):
            node[key] = value
    nodes[node_id] = node


def add_edge(
    edges: dict[str, dict[str, Any]],
    kind: str,
    src: str,
    dst: str,
    *,
    evidence: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    eid = edge_id(kind, src, dst)
    edge: dict[str, Any] = {"id": eid, "from": src, "to": dst, "kind": kind}
    if evidence:
        edge["evidence"] = evidence
    if metadata:
        edge["metadata"] = metadata
    edges[eid] = edge


def graph_metrics(nodes: dict[str, dict[str, Any]], edges: dict[str, dict[str, Any]]) -> dict[str, Any]:
    node_kinds: dict[str, int] = {}
    edge_kinds: dict[str, int] = {}
    for node in nodes.values():
        kind = str(node.get("kind", "unknown"))
        node_kinds[kind] = node_kinds.get(kind, 0) + 1
    for edge in edges.values():
        kind = str(edge.get("kind", "unknown"))
        edge_kinds[kind] = edge_kinds.get(kind, 0) + 1
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_kinds": dict(sorted(node_kinds.items())),
        "edge_kinds": dict(sorted(edge_kinds.items())),
    }


def build_repo_graph(
    files: dict[str, dict[str, Any]],
    symbols_by_path: dict[str, list[str]],
    entrypoints: list[dict[str, Any]],
    dependencies: list[dict[str, Any]],
    routes: list[dict[str, Any]],
    plugins: list[dict[str, Any]],
    module_graph: dict[str, Any],
) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    for rel, metadata in sorted(files.items()):
        add_node(
            nodes,
            f"file:{rel}",
            "file",
            rel,
            path=rel,
            language=metadata.get("language"),
            file_kind=metadata.get("kind"),
        )

    for rel, symbols in sorted(symbols_by_path.items()):
        file_node = f"file:{rel}"
        for symbol in symbols:
            symbol_node = f"symbol:{rel}#{symbol}"
            add_node(nodes, symbol_node, "symbol", symbol, path=rel, symbol=symbol)
            add_edge(edges, "file_defines_symbol", file_node, symbol_node, evidence=[{"source": rel}])

    for module in module_graph.get("modules", []) or []:
        if not isinstance(module, dict):
            continue
        name = module.get("module")
        path = module.get("path")
        if not isinstance(name, str) or not isinstance(path, str):
            continue
        module_node = f"module:{name}"
        file_node = f"file:{path}"
        add_node(nodes, module_node, "module", name, path=path, module=name)
        add_edge(edges, "file_represents_module", file_node, module_node, evidence=[{"source": path}])

    for edge in module_graph.get("edges", []) or []:
        if not isinstance(edge, dict):
            continue
        src = edge.get("from")
        dst = edge.get("to")
        source = edge.get("from_path")
        if not isinstance(src, str) or not isinstance(dst, str):
            continue
        add_edge(
            edges,
            "module_imports_module",
            f"module:{src}",
            f"module:{dst}",
            evidence=[{"source": source}] if isinstance(source, str) else None,
            metadata={"import": edge.get("import")} if isinstance(edge.get("import"), str) else None,
        )

    for item in module_graph.get("external_imports", []) or []:
        if not isinstance(item, dict):
            continue
        src = item.get("from")
        import_name = item.get("import")
        source = item.get("from_path")
        if not isinstance(src, str) or not isinstance(import_name, str):
            continue
        import_node = f"external_import:{import_name}"
        add_node(nodes, import_node, "external_import", import_name, import_name=import_name)
        add_edge(
            edges,
            "module_imports_external",
            f"module:{src}",
            import_node,
            evidence=[{"source": source}] if isinstance(source, str) else None,
        )

    for route in routes:
        method = str(route.get("method", "")).upper()
        path = str(route.get("path", ""))
        source = route.get("source")
        if not method or not path or not isinstance(source, str):
            continue
        route_node = f"route:{method}:{path}"
        add_node(nodes, route_node, "route", f"{method} {path}", path=source, route={"method": method, "path": path})
        evidence = [{"source": source, "line": route.get("line")}] if route.get("line") else [{"source": source}]
        add_edge(edges, "file_exposes_route", f"file:{source}", route_node, evidence=evidence)
        handler = route.get("handler")
        if isinstance(handler, str) and handler:
            handler_node = f"symbol:{source}#{handler}"
            if handler_node in nodes:
                add_edge(edges, "route_bound_to_symbol", route_node, handler_node, evidence=evidence)

    for dependency in dependencies:
        ecosystem = str(dependency.get("ecosystem", "unknown"))
        name = str(dependency.get("name", ""))
        source = dependency.get("source")
        if not name or not isinstance(source, str):
            continue
        dep_node = f"dependency:{ecosystem}:{name}"
        add_node(nodes, dep_node, "dependency", name, ecosystem=ecosystem, version=dependency.get("version"))
        add_edge(
            edges,
            "manifest_declares_dependency",
            f"file:{source}",
            dep_node,
            evidence=[{"source": source, "section": dependency.get("section")}],
        )

    for entrypoint in entrypoints:
        kind = str(entrypoint.get("kind", "entrypoint"))
        name = str(entrypoint.get("name", ""))
        source = entrypoint.get("source")
        if not name or not isinstance(source, str):
            continue
        entry_node = f"entrypoint:{kind}:{name}"
        add_node(nodes, entry_node, "entrypoint", name, entrypoint_kind=kind, target=entrypoint.get("target"))
        add_edge(
            edges,
            "manifest_declares_entrypoint",
            f"file:{source}",
            entry_node,
            evidence=[{"source": source}],
        )

    for plugin in plugins:
        path = plugin.get("path")
        if not isinstance(path, str):
            continue
        plugin_node = f"plugin:{path}"
        add_node(nodes, plugin_node, "plugin", path, path=path, surface=plugin.get("surface"))
        add_edge(edges, "file_declares_plugin", f"file:{path}", plugin_node, evidence=[{"source": path}])

    return {
        "schema": "reveng.repo_graph.v1",
        "nodes": [nodes[node_id] for node_id in sorted(nodes)],
        "edges": [edges[eid] for eid in sorted(edges)],
        "metrics": graph_metrics(nodes, edges),
        "limitations": [
            "Repo graph is a static evidence graph; it does not imply runtime reachability or execution order.",
            "Only Python import edges are resolved to internal modules in the zero-dependency implementation.",
            "Non-Python symbols, routes, and imports remain regex-derived hints and require human confirmation.",
        ],
    }


def static_risks(root: Path, rel: str, text: str, kind: str) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    lowered = text.lower()
    if kind == "manifest" and any(token in lowered for token in ("postinstall", "preinstall", "curl ", "wget ")):
        risks.append({"kind": "install_script_or_fetch", "source": rel, "evidence": "install/fetch-like token observed"})
    if rel.endswith((".env", ".env.example")) or "secret" in lowered or "api_key" in lowered:
        risks.append({"kind": "secret_pattern", "source": rel, "evidence": "secret-like token observed"})
    return risks


def build_map(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")

    entrypoints: list[dict[str, Any]] = []
    dependencies: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []
    plugins: list[dict[str, Any]] = []
    configs: list[dict[str, Any]] = []
    imports: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []
    python_modules: dict[str, str] = {}
    python_imports: dict[str, list[str]] = {}
    files: dict[str, dict[str, Any]] = {}
    symbols_by_path: dict[str, list[str]] = {}

    for path in iter_repo_files(root):
        rel = repo_relative(root, path)
        kind = classify_kind(root, path)
        files[rel] = {"kind": kind, "language": detect_language(path)}
        if path.suffix.lower() in PYTHON_SUFFIXES:
            module = python_module_name(root, path)
            if module:
                python_modules[module] = rel
        if path.name == "pyproject.toml":
            eps, deps = parse_pyproject(path, rel)
            entrypoints.extend(eps)
            dependencies.extend(deps)
        elif path.name == "package.json":
            eps, deps = parse_package_json(path, rel)
            entrypoints.extend(eps)
            dependencies.extend(deps)

        if kind == "plugin_manifest":
            plugins.append({"path": rel, "surface": path.parent.name if path.parent.name.startswith(".") else path.name})
        if kind == "config":
            configs.append({"path": rel, "kind": "config"})

        if path.suffix.lower() in {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            text = read_text(path)
            definitions = python_definitions(text) if path.suffix.lower() in PYTHON_SUFFIXES else None
            if definitions is not None:
                module = python_module_name(root, path)
                if module:
                    python_imports[module] = definitions["imports"]
                if definitions["symbols"]:
                    symbols_by_path[rel] = definitions["symbols"]
                if definitions["imports"]:
                    imports.append({"path": rel, "imports": definitions["imports"]})
                for route in definitions["routes"]:
                    route_record = {"framework_hint": "python", "method": route["method"], "path": route["path"], "source": rel, "line": route["line"]}
                    if route.get("handler"):
                        route_record["handler"] = route["handler"]
                    routes.append(route_record)
            else:
                file_symbols = extract_symbols(text)
                if file_symbols:
                    symbols_by_path[rel] = file_symbols
                file_imports = extract_imports(text)
                if file_imports:
                    imports.append({"path": rel, "imports": file_imports})
                routes.extend(extract_routes(text, rel))
            risks.extend(static_risks(root, rel, text, kind))
        elif kind in {"manifest", "plugin_manifest", "config"}:
            risks.extend(static_risks(root, rel, read_text(path), kind))

    module_graph = build_python_module_graph(python_modules, python_imports)
    return {
        "root": str(root),
        "entrypoints": sorted(entrypoints, key=lambda item: (item["source"], item["kind"], item["name"])),
        "dependencies": sorted(dependencies, key=lambda item: (item["source"], item["ecosystem"], item["name"])),
        "routes": sorted(routes, key=lambda item: (item["source"], item["line"], item["path"])),
        "plugins": sorted(plugins, key=lambda item: item["path"]),
        "configs": sorted(configs, key=lambda item: item["path"]),
        "imports": sorted(imports, key=lambda item: item["path"]),
        "module_graph": module_graph,
        "graph": build_repo_graph(
            files,
            symbols_by_path,
            entrypoints,
            dependencies,
            routes,
            plugins,
            module_graph,
        ),
        "risks": sorted(risks, key=lambda item: (item["source"], item["kind"])),
        "limitations": [
            "Static analysis only; repository code, tests, package managers, containers, and build scripts were not executed.",
            "Python routes/imports use AST when parseable; non-Python routes/imports and invalid Python fallback to regex candidates and require human confirmation for complex frameworks.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Static repository map")
    parser.add_argument("repo", help="Repository directory to inspect")
    parser.add_argument("--json-out", help="Write map JSON to this path")
    args = parser.parse_args()

    payload = build_map(Path(args.repo))
    if args.json_out:
        write_json(Path(args.json_out), payload)
    else:
        import json

        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
