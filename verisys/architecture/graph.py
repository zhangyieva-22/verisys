"""Pure ArchitectureIR projection: no source reads or relationship inference."""

from urllib.parse import quote

from verisys.models.architecture import ArchitectureIR, SourceLocation
from verisys.models.graph import (
    ArchitectureEdge, ArchitectureEdgeType, ArchitectureGraph,
    ArchitectureNode, ArchitectureNodeType,
)


def _id(prefix: str, *parts: str) -> str:
    # Encode each component independently: colons/percent signs cannot collide
    # with separators. Preserve case rather than conflating distinct IR facts.
    return prefix + ":" + ":".join(quote(part, safe="") for part in parts)


def _locations(locations: list[SourceLocation]) -> list[SourceLocation]:
    return sorted(set(locations), key=lambda loc: (
        loc.file, loc.line, -1 if loc.column is None else loc.column,
    ))


def project_architecture_graph(architecture: ArchitectureIR) -> ArchitectureGraph:
    """Project only explicit facts; ordering and IDs do not depend on input order.

    Module inventory is limited to import dependency endpoints. IMPORTS edges
    require an import source location; evidence IDs alone cannot resolve a source.
    Framework strings have no source references in current IR. Service metadata
    preserves concrete call_sites separately from presence source_locations.
    CONTAINS/CALLS relationships cannot currently be grounded and are omitted.
    Route identity includes handler and full source location to distinguish routes
    sharing a method/path. Exact duplicate facts merge, with sorted source unions.
    """
    nodes: dict[str, ArchitectureNode] = {}
    edges: dict[str, ArchitectureEdge] = {}
    limitations = set(architecture.limitations)

    def add_node(node: ArchitectureNode) -> None:
        previous = nodes.get(node.id)
        if previous is not None:
            node.source_locations = _locations(previous.source_locations + node.source_locations)
            if node.type == ArchitectureNodeType.EXTERNAL_SERVICE:
                # Call references remain distinct from service-presence references.
                calls = previous.metadata["call_sites"] + node.metadata["call_sites"]
                node.metadata["call_sites"] = [loc.model_dump(mode="json") for loc in _locations([
                    SourceLocation.model_validate(call) for call in calls
                ])]
        nodes[node.id] = node

    for framework in architecture.frameworks:
        add_node(ArchitectureNode(id=_id("framework", framework),
                                 type=ArchitectureNodeType.FRAMEWORK, label=framework))

    for route in architecture.api_routes:
        loc = route.source_location
        add_node(ArchitectureNode(
            id=_id("route", route.method, route.path, route.handler, loc.file,
                   str(loc.line), "none" if loc.column is None else str(loc.column)),
            type=ArchitectureNodeType.API_ROUTE, label=f"{route.method} {route.path}",
            subtitle=route.handler, source_locations=[loc],
        ))

    for service in architecture.external_services:
        add_node(ArchitectureNode(
            id=_id("external", service.name, *([] if service.client_library is None else [service.client_library])),
            type=ArchitectureNodeType.EXTERNAL_SERVICE, label=service.name,
            subtitle=service.client_library,
            source_locations=_locations(service.source_locations + service.call_sites),
            metadata={"call_sites": [loc.model_dump(mode="json")
                                     for loc in _locations(service.call_sites)]},
        ))

    for tool in architecture.tools:
        loc = tool.source_location
        add_node(ArchitectureNode(
            id=_id("tool", tool.module, tool.handler, loc.file, str(loc.line)),
            type=ArchitectureNodeType.TOOL, label=tool.name, subtitle=tool.module,
            source_locations=[loc], metadata={"handler": tool.handler, "module": tool.module},
        ))

    for store in architecture.datastores:
        add_node(ArchitectureNode(
            id=_id("datastore", store.name, store.engine),
            type=ArchitectureNodeType.DATASTORE, label=store.name, subtitle=store.engine,
            source_locations=_locations(store.source_locations),
        ))

    for dependency in architecture.dependencies:
        if dependency.dependency_type != "import":
            limitations.add(f"Graph omitted unsupported dependency type: {dependency.dependency_type}.")
            continue
        source = _id("module", dependency.source_component)
        target = _id("module", dependency.target_component)
        for identifier, label in ((source, dependency.source_component), (target, dependency.target_component)):
            # An import reference does not locate the target module definition.
            locations = [dependency.source_location] if identifier == source and dependency.source_location else []
            add_node(ArchitectureNode(id=identifier, type=ArchitectureNodeType.MODULE,
                                     label=label, source_locations=locations))
        if dependency.source_location is None:
            limitations.add(f"Graph omitted import without source location: {dependency.source_component} -> {dependency.target_component}.")
            continue
        identifier = _id("imports", dependency.source_component, dependency.target_component)
        previous = edges.get(identifier)
        edges[identifier] = ArchitectureEdge(
            id=identifier, source=source, target=target, type=ArchitectureEdgeType.IMPORTS,
            source_locations=_locations([dependency.source_location] + (previous.source_locations if previous else [])),
        )

    return ArchitectureGraph(execution_flows=sorted(
        [flow.model_copy(deep=True) for flow in architecture.execution_flows], key=lambda flow: flow.id), nodes=[nodes[key] for key in sorted(nodes)],
                             edges=[edges[key] for key in sorted(edges)],
                             limitations=sorted(limitations))
