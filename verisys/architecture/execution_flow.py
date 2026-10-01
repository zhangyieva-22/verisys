"""Finite LangGraph declaration grammar and one-hop FastAPI invocation binding.

Consumes only already safely parsed ASTs. No evaluator/imports/source walking.
Not a Python call graph: unknown syntax fails closed with explicit limitations.
"""
import ast
from pathlib import Path

from verisys.models.execution import ExecutionFlow, ExecutionStep, ExecutionTransition
from .graph import _id, _locations
from .python_ast import location, module_name, _module_rebindings, _local_names


def _literal(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _qualified(node, bindings):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    parent = bindings.get(node.id) if isinstance(node, ast.Name) else None
    return ".".join([parent, *reversed(parts)]) if parent else None


def _locals(function):
    args = function.args
    parameters = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    parameters += [item for item in (args.vararg, args.kwarg) if item is not None]
    return _local_names(function) | {arg.arg for arg in parameters}


class Module:
    def __init__(self, path, tree):
        self.path, self.tree = path, tree
        self.name = module_name(path)
        self.bindings, self.imports, self.functions, self.binding_sources = {}, {}, {}, {}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and not node.level and node.module:
                for alias in node.names:
                    if alias.name != "*":
                        name = alias.asname or alias.name
                        self.bindings[name] = f"{node.module}.{alias.name}"
                        self.binding_sources[name] = location(path, node)
                        self.imports[name] = (node.module, alias.name, node)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    self.bindings[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
                    self.binding_sources[alias.asname or alias.name.split('.')[0]] = location(path, node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions[node.name] = node
        self.uncertain = _module_rebindings(tree)
        for name in self.uncertain:
            self.bindings.pop(name, None)
            self.imports.pop(name, None)
            self.functions.pop(name, None)

    def function(self, name, modules):
        if name in self.functions:
            return self, self.functions[name], []
        imported = self.imports.get(name)
        if imported and imported[0] in modules:
            other = modules[imported[0]]
            function = other.functions.get(imported[1])
            if function:
                return other, function, [location(self.path, imported[2])]
        return None


def _factory(module, function, result, modules):
    if isinstance(function, ast.AsyncFunctionDef) or function.decorator_list:
        result.limitations.append(f"{module.path}:{function.lineno}: Execution flow omitted: async/decorated factory is unsupported.")
        return None
    bindings = module.bindings.copy()
    for name in _locals(function):
        bindings.pop(name, None)
    graph_name, construction, compiled = None, None, None
    registered, declarations, limitations = {}, [], []
    def fail(node, reason):
        result.limitations.append(f"{module.path}:{node.lineno}: Execution flow omitted: {reason}.")
        return None
    for statement in function.body:
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
            continue  # docstring
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            value = statement.value
            if isinstance(value, ast.Call) and _qualified(value.func, bindings) == "langgraph.graph.StateGraph" and graph_name is None:
                graph_name, construction = statement.targets[0].id, value
                continue
            return fail(statement, "only one simple StateGraph assignment is supported")
        if isinstance(statement, ast.Return):
            value = statement.value
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and isinstance(value.func.value, ast.Name) and value.func.value.id == graph_name and value.func.attr == "compile":
                if compiled is not None or any(not isinstance(arg, ast.Constant) for arg in [*value.args, *(kw.value for kw in value.keywords)]):
                    return fail(statement, "compile configuration is dynamic")
                compiled = value
                continue
            return fail(statement, "factory must directly return graph.compile")
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            return fail(statement, "dynamic or unsupported graph declarations")
        call = statement.value
        if not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name) or call.func.value.id != graph_name:
            return fail(statement, "unsupported factory call")
        if compiled is not None:
            return fail(statement, "declarations after compile are unsupported")
        method = call.func.attr
        if call.keywords:
            return fail(call, "keyword graph declarations are unsupported")
        if method == "add_node" and len(call.args) == 2:
            label, handler = _literal(call.args[0]), call.args[1]
            if label is None or label in {"START", "END"} or label in registered or not isinstance(handler, ast.Name):
                return fail(call, "node declaration is not a unique literal and named handler")
            resolved = module.function(handler.id, modules)
            if not resolved:
                return fail(call, "node handler identity is unresolved")
            registered[label] = (call, handler.id, resolved)
        elif method in {"add_edge", "set_entry_point", "add_conditional_edges"}:
            declarations.append((method, call))
        else:
            return fail(call, "unsupported StateGraph method")
    if graph_name is None or compiled is None:
        return fail(function, "no directly compiled StateGraph")
    # Reject absent/multiple entry declarations and unresolved endpoints.
    def endpoint(node):
        symbol = _qualified(node, bindings)
        if symbol in {"langgraph.graph.START", "langgraph.graph.END"}:
            return symbol.rsplit('.', 1)[-1]
        text = _literal(node)
        return text if text in registered else None
    edges, entries = [], 0
    for method, call in declarations:
        args = call.args
        sources = [location(module.path, call)]
        for arg in args:
            root = arg
            while isinstance(root, ast.Attribute): root = root.value
            if isinstance(root, ast.Name) and root.id in bindings and root.id in module.binding_sources:
                sources.append(module.binding_sources[root.id])
        if method == "set_entry_point" and len(args) == 1:
            target = endpoint(args[0])
            source, kind, condition = "START", "ENTRY", None
            entries += 1
            edges.append((source, target, kind, condition, sources))
        elif method == "add_edge" and len(args) == 2:
            source, target = map(endpoint, args)
            if source == "START": entries += 1
            edges.append((source, target, "ENTRY" if source == "START" else "NEXT", None, sources))
        elif method == "add_conditional_edges" and len(args) == 3 and isinstance(args[1], ast.Name) and isinstance(args[2], ast.Dict):
            source = endpoint(args[0])
            condition = module.function(args[1].id, modules)
            if not condition:
                return fail(call, "condition function identity is unresolved")
            condition_module, condition_function, import_sources = condition
            sources += import_sources + [location(condition_module.path, condition_function), location(module.path, args[2])]
            for key, value in zip(args[2].keys, args[2].values):
                if _literal(key) is None or endpoint(value) is None:
                    return fail(call, "conditional destinations are not literal/static")
                edges.append((source, endpoint(value), "CONDITIONAL", f"{args[1].id}: {_literal(key)}", sources))
        else:
            return fail(call, "unsupported edge declaration signature")
    if entries != 1 or not edges or any(source is None or target is None for source, target, *_ in edges):
        return fail(function, "missing/ambiguous entry or unresolved transition endpoints")
    if not any(target == "END" for _, target, *_ in edges):
        limitations.append("No explicit END transition is declared; completion/return is not established.")
    constructor_root = construction.func
    while isinstance(constructor_root, ast.Attribute): constructor_root = constructor_root.value
    identity_sources = [module.binding_sources[constructor_root.id]] if isinstance(constructor_root, ast.Name) and constructor_root.id in module.binding_sources else []
    identifier = _id("execution", module.name, function.name, str(function.lineno))
    step_id = lambda label: _id(identifier, label)
    steps = [ExecutionStep(id=step_id("START"), type="WORKFLOW", label=f"{function.name} · START", source_locations=_locations([location(module.path, construction), location(module.path, compiled)]))]
    if any(target == "END" or source == "END" for source, target, *_ in edges):
        steps.append(ExecutionStep(id=step_id("END"), type="EXIT", label="END", source_locations=_locations([loc for source, target, _, _, locs in edges if source == "END" or target == "END" for loc in locs])))
    for label, (call, handler, resolved) in registered.items():
        owner, body, imports = resolved
        candidates, tool_sources = _candidate_tools(owner, body, modules, result)
        steps.append(ExecutionStep(id=step_id(label), type="TOOL_EXECUTION" if candidates else "WORKFLOW_STEP", label=label, component_id=_id("module", owner.name), candidate_tool_ids=candidates, source_locations=_locations([location(module.path, call), location(owner.path, body), *imports, *tool_sources])))
    flow = ExecutionFlow(id=identifier, name=function.name, trigger=step_id("START"), steps=steps,
        transitions=[ExecutionTransition(source=step_id(source), target=step_id(target), type=kind, condition=condition, source_locations=_locations(locs)) for source, target, kind, condition, locs in edges],
        source_locations=_locations([*identity_sources, location(module.path, function), location(module.path, construction), location(module.path, compiled)]), limitations=limitations + ["Possible source-declared paths only; conditions, runtime outcomes and exception paths are not evaluated.", "OpenAI factory bindings and business-service/SQLite call chains are outside this bounded extraction."])
    return flow, compiled


def _scope_nodes(function):
    """Visit this handler only; nested scopes do not establish its execution."""
    pending = list(reversed(function.body))
    while pending:
        node = pending.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            pending.extend(reversed(list(ast.iter_child_nodes(node))))


def _collection_written(tree, name, declaration):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.Delete)) and node is not declaration:
            targets = node.targets if isinstance(node, (ast.Assign, ast.Delete)) else [node.target]
            for target in targets:
                while isinstance(target, (ast.Attribute, ast.Subscript)):
                    target = target.value
                if isinstance(target, ast.Name) and target.id == name:
                    return True
    return False


def _candidate_tools(module, function, modules, result):
    """Only literal registered tools iterated by a local variable with explicit invoke.

    Candidate set, not ordered calls or selected tools. No collection mutation,
    re-exports, nested function capture, iterator reassignment or dynamic names.
    """
    candidates, sources = set(), []
    local = _locals(function)
    for loop in _scope_nodes(function):
        if not isinstance(loop, ast.For) or not isinstance(loop.iter, ast.Name) or not isinstance(loop.target, ast.Name) or loop.iter.id in local:
            continue
        imported = module.imports.get(loop.iter.id)
        if not imported or imported[0] not in modules:
            continue
        owner = modules[imported[0]]
        declarations = [node for node in owner.tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == imported[1] for target in node.targets)]
        if len(declarations) != 1 or imported[1] in owner.uncertain:
            continue
        declaration = declarations[0]
        if not isinstance(declaration.value, (ast.List, ast.Tuple)) or not all(isinstance(item, ast.Name) for item in declaration.value.elts):
            continue
        # Fail closed on any explicit writes/mutating calls to the collection or loop variable.
        body = list(ast.walk(loop))
        if any(isinstance(node, ast.Name) and node.id == loop.target.id and isinstance(node.ctx, (ast.Store, ast.Del)) and node is not loop.target for node in body):
            continue
        if any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) for node in body):
            continue
        uses = [node for node in body if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == loop.target.id and node.func.attr == "invoke"]
        if not uses:
            continue
        collection_names = {imported[1]}
        modified = any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id in collection_names for node in ast.walk(owner.tree))
        modified |= _collection_written(owner.tree, imported[1], declaration) or _collection_written(function, loop.iter.id, None)
        modified |= any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == loop.iter.id for node in ast.walk(function))
        if modified:
            continue
        tools = []
        for item in declaration.value.elts:
            match = [tool for tool in result.tools if tool.module == owner.name and tool.handler == item.id and item.id not in owner.uncertain]
            if len(match) != 1:
                break
            tools.append(match[0])
        else:
            for tool in tools:
                loc = tool.source_location
                candidates.add(_id("tool", tool.module, tool.handler, loc.file, str(loc.line)))
            sources += [location(module.path, imported[2]), location(owner.path, declaration), location(module.path, loop), *(location(module.path, use) for use in uses)]
    return sorted(candidates), _locations(sources)


def extract_execution_flows(parsed, result, collisions, ambiguous_modules=()):
    names = [module_name(path) for path in parsed]
    ambiguous = set(ambiguous_modules) | {name for name in names if names.count(name) > 1}
    modules = {module_name(path): Module(path, tree) for path, tree in sorted(parsed.items(), key=lambda item: item[0].as_posix()) if module_name(path) not in ambiguous}
    for name in sorted(ambiguous):
        result.limitations.append(f"Execution flow omitted: ambiguous local module {name}.")
    if "langgraph" in collisions or any("langgraph" in path.parts or path.stem == "langgraph" for path in parsed):
        result.limitations.append("Execution flow omitted: local langgraph identity is ambiguous.")
        return
    factories = {}
    for module in modules.values():
        for function in module.functions.values():
            local = module.bindings.copy()
            for name in _locals(function): local.pop(name, None)
            # Only top-level statements inside one named factory, never nested dynamic construction.
            matches = [node for node in ast.walk(function) if isinstance(node, ast.Call) and _qualified(node.func, local) == "langgraph.graph.StateGraph"]
            if not matches:
                continue
            extracted = _factory(module, function, result, modules)
            if extracted:
                factories[(module.name, function.name)] = extracted
    exported = {}
    for module in modules.values():
        for statement in module.tree.body:
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
                continue
            call = statement.value
            if statement.targets[0].id in module.uncertain or not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.args or call.keywords:
                continue
            factory = factories.get((module.name, call.func.id))
            if factory:
                exported[(module.name, statement.targets[0].id)] = (*factory, statement)
    associated = set()
    for route in result.api_routes:
        module = modules.get(module_name(Path(route.source_location.file)))
        function = module.functions.get(route.handler) if module else None
        if not function or not any(location(module.path, decorator) == route.source_location for decorator in function.decorator_list):
            continue
        local = _locals(function)
        invokes = [node for node in _scope_nodes(function) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "invoke" and isinstance(node.func.value, ast.Name) and node.func.value.id in module.imports]
        if len(invokes) > 1:
            result.limitations.append(f"{module.path}:{function.lineno}: Execution association omitted: multiple imported invoke calls.")
            continue
        linked = False
        # Only direct, straight-line assignment invoke and a later straight-line return.
        for index, statement in enumerate(function.body):
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
                continue
            call = statement.value
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name) or call.func.attr != "invoke" or call.func.value.id in local:
                continue
            if _collection_written(function, call.func.value.id, None):
                result.limitations.append(f"{module.path}:{call.lineno}: Execution association omitted: imported binding is modified.")
                continue
            imported = module.imports.get(call.func.value.id)
            target = exported.get(imported[:2]) if imported else None
            if not target:
                result.limitations.append(f"{module.path}:{call.lineno}: Execution invocation has no proven local compiled StateGraph binding.")
                continue
            base, compile_call, export = target
            flow = base.model_copy(deep=True)
            flow.id = _id("request-flow", route.source_location.file, route.handler, str(route.source_location.line), base.id)
            entry_id = _id(flow.id, "request")
            ref = _id("route", route.method, route.path, route.handler, route.source_location.file, str(route.source_location.line), "none" if route.source_location.column is None else str(route.source_location.column))
            proof = _locations([route.source_location, location(module.path, imported[2]), location(module.path, call), *base.source_locations, location(modules[imported[0]].path, export)])
            flow.steps.insert(0, ExecutionStep(id=entry_id, type="ENTRY", label=f"{route.method} {route.path}", component_id=ref, source_locations=[route.source_location, location(module.path, function)]))
            flow.transitions.insert(0, ExecutionTransition(source=entry_id, target=base.trigger, type="INVOKE", source_locations=proof))
            flow.trigger, flow.name = entry_id, f"{route.method} {route.path} → {base.name}"
            # Normal handler return, not a claim that the workflow succeeds at runtime.
            returns = [node for node in function.body[index + 1:] if isinstance(node, ast.Return)]
            if len(returns) == 1 and any(step.label == "END" for step in flow.steps):
                return_node = returns[0]
                writes = [node for node in function.body[index + 1:] for node in ast.walk(node) if isinstance(node, ast.Name) and node.id == statement.targets[0].id and isinstance(node.ctx, (ast.Store, ast.Del))]
                if not writes and any(isinstance(node, ast.Name) and node.id == statement.targets[0].id for node in ast.walk(return_node)):
                    return_id = _id(flow.id, "return")
                    flow.steps.append(ExecutionStep(id=return_id, type="EXIT", label="Handler return", source_locations=[location(module.path, return_node)]))
                    end = next(step for step in flow.steps if step.label == "END")
                    flow.transitions.append(ExecutionTransition(source=end.id, target=return_id, type="RETURN", source_locations=_locations([location(module.path, call), location(module.path, return_node), *end.source_locations])))
            flow.source_locations = _locations([*flow.source_locations, *proof])
            result.execution_flows.append(flow)
            associated.add(base.id)
            linked = True
        if invokes and not linked:
            result.limitations.append(f"{module.path}:{function.lineno}: Execution association omitted: no supported direct invocation of an unchanged imported compiled graph.")
    result.execution_flows += [flow for flow, _ in factories.values() if flow.id not in associated]
    result.execution_flows.sort(key=lambda flow: flow.id)
