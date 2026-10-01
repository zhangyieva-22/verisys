"""Behavioral contracts for the pure architecture presentation projection."""

import builtins
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from verisys.architecture import project_architecture_graph
from verisys.models import (
    APIRoute, ArchitectureEdge, ArchitectureEdgeType, ArchitectureGraph,
    ArchitectureIR, ArchitectureNode, ArchitectureNodeType, Dependency,
    ExternalService, SourceLocation,
)


def loc(line, file="app.py", column=0):
    return SourceLocation(file=file, line=line, column=column)


def golden_ir():
    return ArchitectureIR(
        repository_root="/does/not/exist", frameworks=["FastAPI"],
        api_routes=[APIRoute(method="POST", path="/documents", handler="documents",
                             source_location=loc(10))],
        external_services=[ExternalService(name="OpenAI", client_library="openai",
                                          source_locations=[loc(2)], call_sites=[loc(12)])],
        limitations=["Cross-file client resolution is unsupported."],
    )


def test_golden_fastapi_openai_projection():
    graph = project_architecture_graph(golden_ir())
    assert [(n.type, n.label) for n in graph.nodes] == [
        (ArchitectureNodeType.EXTERNAL_SERVICE, "OpenAI"),
        (ArchitectureNodeType.FRAMEWORK, "FastAPI"),
        (ArchitectureNodeType.API_ROUTE, "POST /documents"),
    ]
    assert graph.edges == []  # Co-occurrence proves neither CALLS nor CONTAINS.
    service, framework, route = graph.nodes
    assert framework.id == "framework:FastAPI"
    assert framework.source_locations == []
    assert service.source_locations == [loc(2), loc(12)]
    assert service.metadata == {"call_sites": [loc(12).model_dump(mode="json")]}
    assert route.source_locations == [loc(10)]
    assert route.subtitle == "documents"
    assert graph.limitations == golden_ir().limitations


def test_internal_import_modules_and_grounded_edges():
    ir = ArchitectureIR(repository_root="x", dependencies=[
        Dependency(source_component="app.api", target_component="app.llm",
                   dependency_type="import", source_location=loc(3, "app/api.py")),
        Dependency(source_component="app.api", target_component="app.llm",
                   dependency_type="import", source_location=loc(5, "app/api.py")),
    ])
    graph = project_architecture_graph(ir)
    assert [(n.id, n.type) for n in graph.nodes] == [
        ("module:app.api", ArchitectureNodeType.MODULE),
        ("module:app.llm", ArchitectureNodeType.MODULE),
    ]
    assert graph.nodes[0].source_locations == [loc(3, "app/api.py"), loc(5, "app/api.py")]
    assert graph.nodes[1].source_locations == []
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge.id == "imports:app.api:app.llm"
    assert (edge.source, edge.target, edge.type) == (
        "module:app.api", "module:app.llm", ArchitectureEdgeType.IMPORTS,
    )
    assert edge.source_locations == graph.nodes[0].source_locations
    assert json.loads(graph.model_dump_json())["edges"][0]["type"] == "IMPORTS"
    assert ArchitectureGraph.model_validate_json(graph.model_dump_json()) == graph


def test_ungrounded_and_unsupported_dependencies_are_omitted():
    ir = ArchitectureIR(repository_root="x", dependencies=[
        Dependency(source_component="a", target_component="b", dependency_type="import", evidence_ids=["unresolved"]),
        Dependency(source_component="a", target_component="c", dependency_type="calls", source_location=loc(1)),
    ])
    graph = project_architecture_graph(ir)
    assert graph.edges == []
    assert [n.label for n in graph.nodes] == ["a", "b"]
    assert graph.limitations == [
        "Graph omitted import without source location: a -> b.",
        "Graph omitted unsupported dependency type: calls.",
    ]


def test_order_duplicates_and_stable_ids():
    ir = golden_ir()
    ir.frameworks += ["Django", "FastAPI"]
    ir.api_routes += [ir.api_routes[0].model_copy(deep=True)]
    ir.external_services += [ExternalService(name="OpenAI", client_library="openai",
                                             source_locations=[loc(1)], call_sites=[loc(12), loc(20)])]
    ir.dependencies = [Dependency(source_component="b", target_component="a",
                                   dependency_type="import", source_location=loc(8)),
                       Dependency(source_component="a", target_component="b",
                                   dependency_type="import", source_location=loc(4))]
    ir.dependencies += [ir.dependencies[0].model_copy(deep=True)]
    expected = project_architecture_graph(ir)
    reordered = ir.model_copy(deep=True)
    for name in ("frameworks", "api_routes", "external_services", "dependencies", "limitations"):
        getattr(reordered, name).reverse()
    assert expected.model_dump_json() == project_architecture_graph(reordered).model_dump_json()
    assert len(expected.nodes) == 6
    assert len(expected.edges) == 2
    assert [n.id for n in expected.nodes] == sorted(n.id for n in expected.nodes)
    assert [e.id for e in expected.edges] == sorted(e.id for e in expected.edges)
    assert expected.nodes[0].metadata["call_sites"] == [loc(12).model_dump(), loc(20).model_dump()]


def test_semantic_id_collisions_and_duplicate_route_paths():
    ir = ArchitectureIR(repository_root="x", frameworks=["a:b", "a%3Ab"],
                        api_routes=[APIRoute(method="GET", path="/", handler="h", source_location=loc(n))
                                    for n in (1, 2)])
    graph = project_architecture_graph(ir)
    assert len({n.id for n in graph.nodes}) == 4
    assert {n.id for n in graph.nodes if n.type == ArchitectureNodeType.FRAMEWORK} == {
        "framework:a%3Ab", "framework:a%253Ab",
    }


def test_no_filesystem_access_or_input_mutation(monkeypatch):
    ir = golden_ir()
    original = ir.model_dump_json()

    def forbidden(*args, **kwargs):
        raise AssertionError("Projection must not access the filesystem")

    monkeypatch.setattr(builtins, "open", forbidden)
    for name in ("open", "read_text", "read_bytes", "stat", "exists", "resolve", "iterdir"):
        monkeypatch.setattr(Path, name, forbidden)
    graph = project_architecture_graph(ir)
    assert ir.model_dump_json() == original
    graph.nodes[0].metadata["call_sites"].clear()
    graph.nodes[0].source_locations.clear()
    graph.limitations.clear()
    assert ir.model_dump_json() == original


def test_serialization():
    graph = project_architecture_graph(golden_ir())
    dumped = graph.model_dump(mode="json")
    assert dumped["nodes"][0]["type"] == "EXTERNAL_SERVICE"
    assert json.loads(graph.model_dump_json()) == dumped
    assert ArchitectureGraph.model_validate_json(graph.model_dump_json()) == graph
    assert graph.model_dump()["nodes"][0]["source_locations"][0]["file"] == "app.py"


def test_defaults_and_empty_projection():
    one, two = ArchitectureGraph(), ArchitectureGraph()
    one.limitations.append("limited")
    assert two.limitations == [] and two.nodes == [] and two.edges == []
    a = ArchitectureNode(id="a", type="MODULE", label="a")
    b = ArchitectureNode(id="b", type="MODULE", label="b")
    a.metadata["x"] = [1]
    a.source_locations.append(loc(1))
    assert b.metadata == {} and b.source_locations == []
    assert project_architecture_graph(ArchitectureIR(repository_root="x")) == ArchitectureGraph()


@pytest.mark.parametrize("model, kwargs", [
    (ArchitectureNode, dict(id="x", type="DATASTORE", label="x")),
    (ArchitectureNode, dict(id="x", type="MODULE", label="x", color="red")),
    (ArchitectureEdge, dict(id="x", source="a", target="b", type="GUESSED")),
])
def test_invalid_types_and_frontend_fields_rejected(model, kwargs):
    with pytest.raises(ValidationError):
        model(**kwargs)


def test_external_library_identity_does_not_conflate_none_and_empty():
    ir = ArchitectureIR(repository_root="x", external_services=[
        ExternalService(name="OpenAI", client_library=library)
        for library in (None, "", "openai")
    ])
    expected = project_architecture_graph(ir)
    assert len({node.id for node in expected.nodes}) == 3
    ir.external_services.reverse()
    assert project_architecture_graph(ir).model_dump_json() == expected.model_dump_json()
