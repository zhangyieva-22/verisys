"""Bounded semantic presence detection; no execution or inferred relationships."""
from pathlib import Path

from verisys.architecture import analyze_architecture, project_architecture_graph
from verisys.repository import discover_repository
from verisys.models import ArchitectureIR, ArchitectureTool, Datastore, SourceLocation


def analyze(tmp_path, source):
    (tmp_path / "app.py").write_text(source)
    return analyze_architecture(discover_repository(tmp_path))


def test_chatopenai_import_and_constructor_are_presence_not_api_calls(tmp_path):
    ir = analyze(tmp_path, 'from langchain_openai import ChatOpenAI as Chat\nllm = Chat(model="literal")\nllm.invoke("hello")\n')
    service, = ir.external_services
    assert (service.name, service.client_library) == ("OpenAI", "langchain_openai")
    assert [loc.line for loc in service.source_locations] == [1, 2]
    assert service.call_sites == []
    assert any("Unsupported OpenAI call pattern: invoke" in text for text in ir.limitations)
    graph = project_architecture_graph(ir)
    assert graph.nodes[0].type == "EXTERNAL_SERVICE"
    assert graph.nodes[0].metadata["call_sites"] == []
    assert graph.edges == []


def test_sdk_and_wrapper_library_identity_are_preserved(tmp_path):
    ir = analyze(tmp_path, 'from openai import OpenAI\nfrom langchain_openai import ChatOpenAI\nclient = OpenAI()\nllm = ChatOpenAI()\n')
    assert [item.client_library for item in ir.external_services] == ["langchain_openai", "openai"]
    assert len(project_architecture_graph(ir).nodes) == 2


def test_bare_tools_and_aliases_preserve_actual_functions(tmp_path):
    ir = analyze(tmp_path, 'from langchain_core.tools import tool as t\n@t\ndef lookup_order():\n    pass\n@t\nasync def track_shipment():\n    pass\n')
    assert [(tool.name, tool.handler, tool.module, tool.source_location.line) for tool in ir.tools] == [
        ("lookup_order", "lookup_order", "app", 3), ("track_shipment", "track_shipment", "app", 6)]
    graph = project_architecture_graph(ir)
    assert all(node.type == "TOOL" for node in graph.nodes)
    assert graph.edges == []


def test_sqlite_alias_connect_requires_explicit_binding(tmp_path):
    ir = analyze(tmp_path, 'import sqlite3 as sql\ndef connect():\n    return sql.connect("local.db")\n')
    store, = ir.datastores
    assert (store.name, store.engine) == ("SQLite", "sqlite3")
    assert [loc.line for loc in store.source_locations] == [3]
    graph = project_architecture_graph(ir)
    assert graph.nodes[0].type == "DATASTORE"
    assert graph.edges == []


def test_import_alone_does_not_claim_datastore_or_arbitrary_wrapper(tmp_path):
    ir = analyze(tmp_path, 'import sqlite3\nimport langchain_openai\nfrom langchain_openai import OpenAIEmbeddings\nx = OpenAIEmbeddings()\n')
    assert ir.datastores == []
    assert ir.external_services == []


def test_unrelated_names_and_rebinding_do_not_create_semantic_facts(tmp_path):
    ir = analyze(tmp_path, 'from langchain_openai import ChatOpenAI\nfrom langchain_core.tools import tool\nimport sqlite3\nChatOpenAI = other\ntool = other\nsqlite3.connect = other\nx = ChatOpenAI()\n@tool\ndef f():\n    pass\nsqlite3.connect("x")\n')
    assert [loc.line for loc in ir.external_services[0].source_locations] == [1]
    assert ir.tools == []
    assert ir.datastores == []
    ir = analyze(tmp_path, 'ChatOpenAI()\nsqlite3.connect("x")\n@tool\ndef f():\n    pass\n')
    assert not ir.external_services and not ir.datastores and not ir.tools


def test_local_library_collision_is_not_external_semantics(tmp_path):
    for name in ("langchain_openai", "langchain_core", "sqlite3"):
        (tmp_path / f"{name}.py").write_text("")
    ir = analyze(tmp_path, 'from langchain_openai import ChatOpenAI\nfrom langchain_core.tools import tool\nimport sqlite3\nx = ChatOpenAI()\n@tool\ndef f():\n    pass\nsqlite3.connect("x")\n')
    assert not ir.external_services and not ir.tools and not ir.datastores
    assert sum("identity is ambiguous" in text for text in ir.limitations) == 3


def test_tool_factory_and_unsupported_scopes_remain_limitations(tmp_path):
    ir = analyze(tmp_path, 'from langchain_core.tools import tool\nimport sqlite3\n@tool("renamed")\ndef f():\n    pass\ntry:\n    sqlite3.connect("x")\nexcept Exception:\n    pass\n')
    assert ir.tools == [] and ir.datastores == []
    assert any("decorator factory" in text for text in ir.limitations)
    assert any("Try" in text for text in ir.limitations)


def test_semantic_models_serialize_and_default_lists_are_isolated():
    first = ArchitectureIR(repository_root=".")
    second = ArchitectureIR(repository_root=".")
    first.tools.append(ArchitectureTool(name="f", handler="f", module="app", source_location=SourceLocation(file="app.py", line=2)))
    first.datastores.append(Datastore(name="SQLite", engine="sqlite3"))
    assert not second.tools and not second.datastores
    assert ArchitectureIR.model_validate(first.model_dump()).model_dump() == first.model_dump()
    graph = project_architecture_graph(first)
    reordered = first.model_copy(update={"tools": list(reversed(first.tools)), "datastores": list(reversed(first.datastores))})
    assert graph.model_dump_json() == project_architecture_graph(reordered).model_dump_json()
