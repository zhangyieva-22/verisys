"""Small explicit AST patterns, not a whole-program or runtime call graph.

Supported bindings: direct/aliased imports and simple named client/app/router
assignments, including within functions. FastAPI decorators require such a
binding and a literal path. Client calls are limited to the families below.
Constructors and imports are detection signals, never external call sites.
M2.5 adds exact ChatOpenAI presence, bare langchain_core.tools.tool decorators,
and sqlite3.connect presence; wrapper invoke/stream calls remain unsupported.
No timeout arguments are inspected. Dynamic factories, attribute-held clients,
re-exports, src-layout resolution, router mounting/prefix composition, and
cross-file client bindings are outside this milestone.
With/async-with bodies are inspected as straight-line code; `with <constructor>()
as <name>` binds like an assignment, relying on supported clients returning
themselves from __enter__. Loops, try/match statements, lambdas and
comprehensions are explicitly unsupported for service/route binding analysis; dependency imports are still
collected independently. Conditional branches retain only common bindings.
"""

import ast
from pathlib import Path

from verisys.models.architecture import (
    APIRoute, ArchitectureIR, ArchitectureTool, Datastore, Dependency, ExternalService, SourceLocation,
)

SERVICES = {
    "openai": "OpenAI", "stripe": "Stripe", "twilio": "Twilio", "langchain_openai": "OpenAI",
    "requests": "Outbound HTTP", "httpx": "Outbound HTTP",
}
CONSTRUCTORS = {
    "langchain_openai.ChatOpenAI": "langchain_openai",
    "openai.OpenAI": "openai", "openai.AsyncOpenAI": "openai",
    "stripe.StripeClient": "stripe", "twilio.rest.Client": "twilio",
    "requests.Session": "requests", "requests.session": "requests",
    "httpx.Client": "httpx", "httpx.AsyncClient": "httpx",
}
# Request-making operations, as module functions and as methods of a bound client.
HTTP_CALLS = {
    "requests": {"get", "options", "head", "post", "put", "patch", "delete", "request"},
    "httpx": {"get", "options", "head", "post", "put", "patch", "delete", "request", "stream"},
}
# First operation segments that never send a request: configuration objects,
# exceptions and client state. Anything else unrecognized stays a limitation.
HTTP_MODULE_HELPERS = {
    "requests": {"Request", "PreparedRequest", "Response", "exceptions", "adapters", "auth",
                 "utils", "structures", "cookies", "codes", "status_codes"},
    "httpx": {"Timeout", "Limits", "URL", "Headers", "QueryParams", "Cookies", "Request", "Response",
              "HTTPTransport", "AsyncHTTPTransport", "MockTransport", "BasicAuth", "DigestAuth",
              "Auth", "Proxy", "codes"},
}
HTTP_CLIENT_HELPERS = {"close", "aclose", "mount", "build_request", "prepare_request", "headers",
                       "cookies", "params", "auth", "get_adapter"}
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
OPENAI_CALLS = {
    "chat.completions.create", "completions.create", "responses.create",
    "embeddings.create", "ChatCompletion.create", "Completion.create", "Embedding.create",
}
STRIPE_RESOURCES = {"Charge", "PaymentIntent", "Customer", "Refund"}
STRIPE_CLIENT_RESOURCES = {"charges", "payment_intents", "customers", "refunds"}
STRIPE_METHODS = {"create", "retrieve", "list", "update", "delete"}


def module_name(path: Path) -> str:
    parts = list(path.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def location(path: Path, node: ast.AST) -> SourceLocation:
    return SourceLocation(file=path.as_posix(), line=node.lineno, column=node.col_offset)


def collect_dependencies(tree, path, modules, ambiguous, result):
    source = module_name(path)
    package = source if path.name == "__init__.py" else source.rpartition(".")[0]
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".") if package else []
                if node.level > len(parts):
                    result.limitations.append(f"{path.as_posix()}:{node.lineno}: relative import exceeds known package.")
                    continue
                prefix = ".".join(parts[:len(parts) - node.level + 1])
                base = ".".join(filter(None, (prefix, base)))
            for alias in node.names:
                child = ".".join(filter(None, (base, alias.name)))
                targets.append(child if child in modules or child in ambiguous else base)
        for target in sorted(set(targets)):
            if target in modules:
                result.dependencies.append(Dependency(
                    source_component=source, target_component=target,
                    dependency_type="import", source_location=location(path, node),
                ))


def _local_names(function):
    """Names local to this function cannot fall back to outer import aliases."""
    names = set()
    globals_ = set()

    class Bindings(ast.NodeVisitor):
        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Store):
                names.add(node.id)

        def visit_Import(self, node):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)

        def visit_ImportFrom(self, node):
            names.update(alias.asname or alias.name for alias in node.names)

        def visit_FunctionDef(self, node):
            names.add(node.name)

        visit_AsyncFunctionDef = visit_FunctionDef
        visit_ClassDef = visit_FunctionDef

        def visit_Global(self, node):
            globals_.update(node.names)

        visit_Nonlocal = visit_Global

    visitor = Bindings()
    for statement in function.body:
        visitor.visit(statement)
    return names - globals_


def _module_rebindings(tree):
    """Small prepass: function globals with module-level writes are uncertain.

    No execution order or full data flow is inferred. A repeated assignment,
    assignment to an imported name, or attribute write disables that global
    association in function bodies. Straight-line module analysis is unchanged.
    """
    assigned, imported, attributes = {}, set(), set()

    class Writes(ast.NodeVisitor):
        def visit_Name(self, node):
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                assigned[node.id] = assigned.get(node.id, 0) + 1

        def visit_Attribute(self, node):
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                root = node.value
                while isinstance(root, ast.Attribute):
                    root = root.value
                if isinstance(root, ast.Name):
                    attributes.add(root.id)
            self.generic_visit(node)

        def visit_Import(self, node):
            imported.update(alias.asname or alias.name.split(".")[0] for alias in node.names)

        def visit_ImportFrom(self, node):
            imported.update(alias.asname or alias.name for alias in node.names)

        def visit_FunctionDef(self, node):
            assigned[node.name] = assigned.get(node.name, 0) + 1

        visit_AsyncFunctionDef = visit_FunctionDef
        visit_ClassDef = visit_FunctionDef

    Writes().visit(tree)
    return attributes | {name for name, count in assigned.items() if count > 1 or name in imported}


class SourceAnalyzer(ast.NodeVisitor):
    def __init__(self, path, modules, ambiguous, result, *, collisions=None, on_non_call_limitation=None):
        self.path, self.modules, self.ambiguous, self.result = path, modules, ambiguous, result
        self.bindings: dict[str, str] = {}
        self.function_parent = None
        self.collisions = collisions or set()
        self.on_non_call_limitation = on_non_call_limitation
        self.invalidated_attributes: set[str] = set()
        self.rebound_globals: set[str] = set()

    def visit_Module(self, node):
        self.rebound_globals = _module_rebindings(node)
        self.generic_visit(node)

    def limit(self, node, summary, *, affects_calls=True):
        message = f"{self.path.as_posix()}:{node.lineno}: {summary}"
        self.result.limitations.append(message)
        if not affects_calls and self.on_non_call_limitation is not None:
            self.on_non_call_limitation(message)

    def service(self, library, node, *, call=False):
        name = SERVICES[library]
        service = next((item for item in self.result.external_services if item.name == name and item.client_library == library), None)
        if service is None:
            service = ExternalService(name=name, client_library=library)
            self.result.external_services.append(service)
        source = location(self.path, node)
        if source not in service.source_locations:
            service.source_locations.append(source)
        if call and source not in service.call_sites:
            service.call_sites.append(source)

    def qualified(self, node):
        if isinstance(node, ast.Name):
            symbol = self.bindings.get(node.id)
        elif isinstance(node, ast.Attribute):
            parent = self.qualified(node.value)
            symbol = f"{parent}.{node.attr}" if parent else None
        else:
            return None
        if symbol and any(symbol == prefix or symbol.startswith(prefix + ".")
                          for prefix in self.invalidated_attributes):
            return None
        return symbol

    @staticmethod
    def known_binding(symbol):
        return bool(symbol and (symbol.split(".")[0] in {*SERVICES, "fastapi", "sqlite3", "langchain_core"}
                                or symbol.startswith(("client:", "route:"))))

    def invalidate_attribute(self, target):
        symbol = self.qualified(target)
        if self.known_binding(symbol):
            self.invalidated_attributes.add(symbol)
            self.limit(target, "Supported library/client/app attribute replaced; binding identity is ambiguous.")

    def bind_import(self, name, symbol, node):
        root = symbol.split(".")[0]
        if root in {*SERVICES, "sqlite3", "langchain_core"} and root in self.collisions:
            self.bindings[name] = "unresolved:" + name
            self.limit(node, f"Local module/package named {root} is present in discovery; external-library identity is ambiguous.")
            return
        if root in self.modules or root in self.ambiguous or any(
            module.startswith(root + ".") for module in self.modules
        ):
            self.bindings[name] = "unresolved:" + name
            return
        self.bindings[name] = symbol
        if root == "fastapi":
            self.result.frameworks.append("FastAPI")
        elif root in SERVICES and (root != "langchain_openai" or symbol == "langchain_openai.ChatOpenAI"):
            self.service(root, node)

    def visit_Import(self, node):
        for alias in node.names:
            self.bind_import(alias.asname or alias.name.split(".")[0],
                             alias.name if alias.asname else alias.name.split(".")[0], node)

    def visit_ImportFrom(self, node):
        if node.level or not node.module:
            for alias in node.names:
                name = alias.asname or alias.name
                self.bindings[name] = "unresolved:" + name
            return
        for alias in node.names:
            if alias.name == "*":
                self.limit(node, "Wildcard import bindings are unsupported.")
                continue
            self.bind_import(alias.asname or alias.name, f"{node.module}.{alias.name}", node)

    def visit_Call(self, node):
        symbol = self.qualified(node.func)
        if symbol and symbol.startswith("unresolved:"):
            operation = symbol.partition(".")[2]
            if operation in OPENAI_CALLS or operation in {"messages.create", "calls.create"} or (
                len(operation.split(".")) == 2 and operation.split(".")[0] in STRIPE_RESOURCES
                and operation.split(".")[1] in STRIPE_METHODS
            ):
                self.limit(node, "Imported binding used in unsupported client-like call; cross-file identity is unresolved.")
        if symbol == "fastapi.APIRouter" and any(keyword.arg == "prefix" for keyword in node.keywords):
            self.limit(node, "Router prefix is not composed; detected route paths are decorator literals.")
        if symbol == "route:.include_router":
            self.limit(node, "Router mounting is not resolved; detected route paths are decorator literals.", affects_calls=False)
        if symbol == "sqlite3.connect":
            store = next((item for item in self.result.datastores if item.engine == "sqlite3"), None)
            if store is None:
                store = Datastore(name="SQLite", engine="sqlite3")
                self.result.datastores.append(store)
            source = location(self.path, node)
            if source not in store.source_locations:
                store.source_locations.append(source)
        base = node.func
        while isinstance(base, ast.Attribute):
            base = base.value
        if base is not node.func and isinstance(base, ast.Call) and self.qualified(base.func) in CONSTRUCTORS:
            self.limit(node, "Call on an unbound client expression is unsupported; not classified.")
        if symbol in CONSTRUCTORS:
            self.service(CONSTRUCTORS[symbol], node)
        elif symbol:
            library, _, operation = symbol.removeprefix("client:").partition(".")
            if library in SERVICES:
                supported = (
                    (library == "openai" and operation in OPENAI_CALLS)
                    or (library == "twilio" and symbol.startswith("client:")
                        and operation in {"messages.create", "calls.create"})
                )
                parts = operation.split(".")
                if library == "stripe":
                    supported = (
                        len(parts) == 2 and parts[0] in STRIPE_RESOURCES and parts[1] in STRIPE_METHODS
                    ) or (
                        symbol.startswith("client:") and len(parts) == 3 and parts[0] == "v1"
                        and parts[1] in STRIPE_CLIENT_RESOURCES and parts[2] in STRIPE_METHODS
                    )
                helper = False
                if library in HTTP_CALLS:
                    supported = operation in HTTP_CALLS[library]
                    head = parts[0]
                    helper = (head in HTTP_CLIENT_HELPERS if symbol.startswith("client:")
                              else head in HTTP_MODULE_HELPERS[library] or head.endswith(("Error", "Exception", "Timeout")))
                if supported:
                    self.service(library, node, call=True)
                elif not helper:
                    self.limit(node, f"Unsupported {SERVICES[library]} call pattern: {operation}; not classified.")
        self.generic_visit(node)

    def assign(self, targets, value):
        self.visit(value)
        symbol = self.qualified(value)
        if isinstance(value, ast.Call):
            constructor = self.qualified(value.func)
            if constructor in CONSTRUCTORS:
                symbol = "client:" + CONSTRUCTORS[constructor]
            elif constructor in {"fastapi.FastAPI", "fastapi.APIRouter"}:
                symbol = "route:"
        for target in targets:
            if isinstance(target, ast.Name):
                old = self.bindings.get(target.id)
                if self.known_binding(old) and old != symbol:
                    self.limit(target, "Name reassigned; previous service/app binding invalidated.")
                if symbol:
                    self.bindings[target.id] = symbol
                else:
                    self.bindings.pop(target.id, None)
            else:
                if isinstance(target, ast.Attribute):
                    self.invalidate_attribute(target)
                for child in ast.walk(target):
                    if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                        self.bindings.pop(child.id, None)
                if symbol and symbol.startswith(("client:", "route:")):
                    self.limit(target, "Client/app binding requires a simple name; attribute/unpacking binding unsupported.")

    def visit_Assign(self, node):
        self.assign(node.targets, node.value)

    def visit_NamedExpr(self, node):
        self.assign([node.target], node.value)

    def visit_AnnAssign(self, node):
        if node.value:
            self.assign([node.target], node.value)

    def visit_FunctionDef(self, node):
        for decorator in node.decorator_list:
            if self.qualified(decorator) == "langchain_core.tools.tool":
                self.result.tools.append(ArchitectureTool(
                    name=node.name, handler=node.name, module=module_name(self.path),
                    source_location=location(self.path, node),
                ))
            elif isinstance(decorator, ast.Call) and self.qualified(decorator.func) == "langchain_core.tools.tool":
                self.limit(decorator, "Only bare @tool decorators are supported; decorator factory not classified.")
            if isinstance(decorator, ast.Call):
                symbol = self.qualified(decorator.func)
                if symbol and symbol.startswith("route:.") and symbol.rsplit(".", 1)[-1] in HTTP_METHODS:
                    path = decorator.args[0] if decorator.args else next(
                        (keyword.value for keyword in decorator.keywords if keyword.arg == "path"), None,
                    )
                    if isinstance(path, ast.Constant) and isinstance(path.value, str):
                        self.result.api_routes.append(APIRoute(
                            method=symbol.rsplit(".", 1)[-1].upper(), path=path.value,
                            handler=node.name, source_location=location(self.path, decorator),
                        ))
                    else:
                        self.limit(decorator, "FastAPI route path is not a literal string.")
            self.visit(decorator)
        for value in [*node.args.defaults, *node.args.kw_defaults]:
            if value is not None:
                self.visit(value)
        outer = self.bindings
        function_parent = self.function_parent
        self.bindings = (function_parent if function_parent is not None else outer).copy()
        self.function_parent = None
        for name in sorted(self.rebound_globals):
            if self.known_binding(self.bindings.get(name)):
                self.bindings.pop(name)
                self.limit(node, f"Global binding {name} has module-level reassignments; function-body identity is ambiguous.")
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        arguments += [argument for argument in (node.args.vararg, node.args.kwarg) if argument]
        for name in _local_names(node) | {argument.arg for argument in arguments}:
            self.bindings.pop(name, None)
        for statement in node.body:
            self.visit(statement)
        self.bindings = outer
        self.function_parent = function_parent
        self.bindings.pop(node.name, None)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        outer = self.bindings
        function_parent = self.function_parent
        self.function_parent = outer
        self.bindings = outer.copy()
        for statement in node.body:
            self.visit(statement)
        self.bindings = outer
        self.function_parent = function_parent
        self.bindings.pop(node.name, None)

    def visit_If(self, node):
        self.visit(node.test)
        outer = self.bindings.copy()
        for statement in node.body:
            self.visit(statement)
        body = self.bindings.copy()
        self.bindings = outer
        for statement in node.orelse:
            self.visit(statement)
        self.bindings = {name: value for name, value in body.items() if self.bindings.get(name) == value}
        if body != self.bindings:
            self.limit(node, "Conditional bindings differ; ambiguous bindings are not propagated.")

    def visit_Try(self, node):
        # Inspect possible paths only. A known alias assigned on any path is
        # ambiguous at entry and exit; never propagate a branch's client identity.
        outer = self.bindings.copy()
        written = {child.id for child in ast.walk(node)
                   if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del))}
        written.update(handler.name for handler in node.handlers if handler.name)
        for child in ast.walk(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                written.update(alias.asname or alias.name.split(".")[0] for alias in child.names)
            elif isinstance(child, ast.Attribute) and isinstance(child.ctx, (ast.Store, ast.Del)):
                self.invalidate_attribute(child)
        if any(self.known_binding(outer.get(name)) for name in written):
            self.limit(node, "Try reassigns a supported binding; cross-path identity is unresolved.")
        base = {name: value for name, value in outer.items() if name not in written}
        for statements in [node.body, *(handler.body for handler in node.handlers), node.orelse, node.finalbody]:
            self.bindings = base.copy()
            for statement in statements:
                self.visit(statement)
        self.bindings = base

    def unsupported_scope(self, node):
        self.limit(node, f"{type(node).__name__} service/route bindings are unsupported; body not inspected.")
        # Such a body can rebind an outer name. Drop affected aliases rather
        # than propagating whichever branch happens to be visited last.
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                self.bindings.pop(child.id, None)
            elif isinstance(child, (ast.Import, ast.ImportFrom)):
                for alias in child.names:
                    self.bindings.pop(alias.asname or alias.name.split(".")[0], None)
            elif isinstance(child, ast.Attribute) and isinstance(child.ctx, (ast.Store, ast.Del)):
                self.invalidate_attribute(child)

    def visit_With(self, node):
        for item in node.items:
            if item.optional_vars is None:
                self.visit(item.context_expr)
            else:
                self.assign([item.optional_vars], item.context_expr)
        for statement in node.body:
            self.visit(statement)

    visit_AsyncWith = visit_With
    visit_For = unsupported_scope
    visit_AsyncFor = unsupported_scope
    visit_While = unsupported_scope
    visit_TryStar = unsupported_scope
    visit_Match = unsupported_scope
    visit_Lambda = unsupported_scope
    visit_ListComp = unsupported_scope
    visit_SetComp = unsupported_scope
    visit_DictComp = unsupported_scope
    visit_GeneratorExp = unsupported_scope

    def visit_Delete(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.bindings.pop(target.id, None)
            elif isinstance(target, ast.Attribute):
                self.invalidate_attribute(target)

    def visit_AugAssign(self, node):
        self.visit(node.value)
        if isinstance(node.target, ast.Name):
            self.bindings.pop(node.target.id, None)
        elif isinstance(node.target, ast.Attribute):
            self.invalidate_attribute(node.target)
