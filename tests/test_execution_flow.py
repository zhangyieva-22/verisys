"""Execution architecture is bounded declaration extraction, never execution."""
import json

import pytest
from pydantic import ValidationError
from verisys.architecture import analyze_architecture, project_architecture_graph
from verisys.repository import discover_repository
from verisys.models.execution import ExecutionFlow, ExecutionStep, ExecutionTransition

WORKFLOW = '''from langgraph.graph import StateGraph as Graph, END as Done
from nodes import triage, tools, response

def decide(state):
    return "tools"

def build():
    workflow = Graph(dict)
    workflow.add_node("triage", triage)
    workflow.add_node("tools", tools)
    workflow.add_node("response", response)
    workflow.set_entry_point("triage")
    workflow.add_conditional_edges("triage", decide, {"tools": "tools", "response": "response"})
    workflow.add_conditional_edges("tools", decide, {"retry": "tools", "response": "response"})
    workflow.add_edge("response", Done)
    return workflow.compile()

agent_graph = build()
'''
NODES = '''from candidates import ALL_TOOLS

def triage(state):
    return state

def tools(state):
    for tool in ALL_TOOLS:
        tool.invoke(state)
    return state

def response(state):
    return state
'''
TOOLS = '''from langchain_core.tools import tool
@tool
def first():
    pass
@tool
def second():
    pass
ALL_TOOLS = [first, second]
'''
ROUTE = '''from fastapi import FastAPI
from workflow import agent_graph
app = FastAPI()
@app.post("/chat")
def chat(state):
    result = agent_graph.invoke(state)
    return {"response": result}
'''


def analyze(tmp_path, workflow=WORKFLOW, nodes=NODES, tools=TOOLS, route=ROUTE):
    for path, content in {"workflow.py": workflow, "nodes.py": nodes, "candidates.py": tools, "api.py": route}.items():
        (tmp_path / path).write_text(content)
    return analyze_architecture(discover_repository(tmp_path))


def test_request_flow_exact_transitions_and_provenance(tmp_path):
    ir = analyze(tmp_path)
    flow, = ir.execution_flows
    labels = {step.id: step.label for step in flow.steps}
    assert flow.name == "POST /chat → build"
    assert [(labels[t.source], labels[t.target], t.condition) for t in flow.transitions] == [
        ("POST /chat", "build · START", None), ("build · START", "triage", None),
        ("triage", "tools", "decide: tools"), ("triage", "response", "decide: response"),
        ("tools", "tools", "decide: retry"), ("tools", "response", "decide: response"),
        ("response", "END", None), ("END", "Handler return", None)]
    assert {(loc.file, loc.line) for loc in flow.transitions[0].source_locations} == {
        ("api.py", 2), ("api.py", 4), ("api.py", 6),
        ("workflow.py", 1), ("workflow.py", 7), ("workflow.py", 8),
        ("workflow.py", 16), ("workflow.py", 18)}
    assert {(loc.file, loc.line) for loc in flow.transitions[2].source_locations} == {("workflow.py", 4), ("workflow.py", 13)}
    tool_step = next(step for step in flow.steps if step.type == "TOOL_EXECUTION")
    assert len(tool_step.candidate_tool_ids) == 2
    assert {(loc.file, loc.line) for loc in tool_step.source_locations} >= {("nodes.py", 1), ("nodes.py", 7), ("nodes.py", 8), ("candidates.py", 8)}
    graph = project_architecture_graph(ir)
    assert graph.execution_flows == ir.execution_flows
    assert all(edge.type == "IMPORTS" for edge in graph.edges)
    assert all(tool in {node.id for node in graph.nodes} for tool in tool_step.candidate_tool_ids)
    assert json.loads(graph.model_dump_json())["execution_flows"][0]["transitions"][2]["type"] == "CONDITIONAL"
    assert ir.model_dump_json() == analyze_architecture(discover_repository(tmp_path)).model_dump_json()


@pytest.mark.parametrize("change", [
    lambda s: s.replace('"triage", triage', 'dynamic, triage'),
    lambda s: s.replace('workflow.set_entry_point("triage")', 'if enabled:\n        workflow.set_entry_point("triage")'),
    lambda s: s.replace('{"tools": "tools", "response": "response"}', 'mapping'),
    lambda s: s.replace('return workflow.compile()', 'return something_else()'),
    lambda s: s + '\nGraph = unrelated\n',
])
def test_dynamic_or_rebound_factory_is_not_guessed(tmp_path, change):
    ir = analyze(tmp_path, workflow=change(WORKFLOW))
    assert not ir.execution_flows
    assert any("Execution" in text for text in ir.limitations)


@pytest.mark.parametrize("suffix", ['\nALL_TOOLS.append(first)\n', '\nALL_TOOLS[0] = other\n', '\nALL_TOOLS += [other]\n'])
def test_modified_tool_collection_is_not_confident_candidate_set(tmp_path, suffix):
    ir = analyze(tmp_path, tools=TOOLS + suffix)
    assert not any(step.candidate_tool_ids for flow in ir.execution_flows for step in flow.steps)


def test_nested_handler_loop_is_not_handler_tool_execution(tmp_path):
    ir = analyze(tmp_path, nodes=NODES.replace('    for tool in ALL_TOOLS:\n        tool.invoke(state)', '    def nested():\n        for tool in ALL_TOOLS:\n            tool.invoke(state)'))
    assert not any(step.candidate_tool_ids for flow in ir.execution_flows for step in flow.steps)


@pytest.mark.parametrize("route", [ROUTE.replace('from workflow import agent_graph', 'from unknown import agent_graph'), ROUTE.replace('    result =', '    agent_graph.invoke = unrelated\n    result ='), ROUTE.replace('    result =', '    agent_graph = unrelated\n    result =')])
def test_unproven_route_binding_retains_only_standalone_workflow(tmp_path, route):
    ir = analyze(tmp_path, route=route)
    assert len(ir.execution_flows) == 1
    assert ir.execution_flows[0].name == "build"
    assert not any(t.type == "INVOKE" for t in ir.execution_flows[0].transitions)


def test_local_langgraph_collision_and_non_execution(tmp_path):
    marker = tmp_path / "executed"
    ir = analyze(tmp_path, route=ROUTE + f'\nopen({str(marker)!r}, "w").write("executed")\n')
    assert ir.execution_flows and not marker.exists()
    (tmp_path / "langgraph.py").write_text("")
    ir = analyze_architecture(discover_repository(tmp_path))
    assert not ir.execution_flows and not marker.exists()
    assert any("local langgraph" in text for text in ir.limitations)


def test_source_and_endpoint_validation():
    source = [{"file": "x.py", "line": 1}]
    with pytest.raises(ValidationError):
        ExecutionStep(id="a", label="a", type="WORKFLOW", source_locations=[])
    with pytest.raises(ValidationError):
        ExecutionTransition(source="a", target="a", type="IMPORTS", source_locations=source)
    with pytest.raises(ValidationError):
        ExecutionFlow(id="f", name="f", source_locations=source, transitions=[ExecutionTransition(source="a", target="b", type="NEXT", source_locations=source)])


def test_factory_parameter_shadow_and_async_are_not_compiled_workflows(tmp_path):
    ir = analyze(tmp_path, workflow=WORKFLOW.replace('def build():', 'def build(Graph):'))
    assert not ir.execution_flows
    ir = analyze(tmp_path, workflow=WORKFLOW.replace('def build():', 'async def build():'))
    assert not ir.execution_flows
    assert any('async/decorated' in text for text in ir.limitations)


def test_ambiguous_discovered_module_is_not_resolved_even_if_one_parse_fails(tmp_path):
    (tmp_path / 'workflow').mkdir()
    (tmp_path / 'workflow' / '__init__.py').write_text('bad syntax !')
    ir = analyze(tmp_path)
    assert not ir.execution_flows
    assert any('ambiguous local module workflow' in text for text in ir.limitations)


def test_skipped_local_langgraph_still_invalidates_library_identity(tmp_path):
    from verisys.repository.discovery import DiscoveryLimits
    analyze(tmp_path)
    (tmp_path / 'langgraph.py').write_text('#' * 2000)
    ir = analyze_architecture(discover_repository(tmp_path, limits=DiscoveryLimits(max_file_bytes=1500)))
    assert not ir.execution_flows
    assert any('local langgraph' in text for text in ir.limitations)


def test_explicit_start_and_end_aliases_are_source_grounded(tmp_path):
    workflow = WORKFLOW.replace('StateGraph as Graph, END as Done', 'StateGraph as Graph, END as Done, START as Begin').replace('workflow.set_entry_point("triage")', 'workflow.add_edge(Begin, "triage")')
    flow, = analyze(tmp_path, workflow=workflow).execution_flows
    assert flow.transitions[1].type == 'ENTRY'
    assert {(loc.file, loc.line) for loc in flow.transitions[1].source_locations} == {('workflow.py', 1), ('workflow.py', 12)}


def test_parse_failure_prevents_cross_file_execution_binding(tmp_path):
    ir = analyze(tmp_path, workflow=WORKFLOW + '\ninvalid syntax !\n')
    assert not ir.execution_flows
    assert any('Python parse failed' in text for text in ir.limitations)
