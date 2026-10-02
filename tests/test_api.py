"""HTTP wiring over real temporary repositories; no external repo dependency."""
import importlib

import pytest
from fastapi.testclient import TestClient

from verisys.api.app import app, AnalyzeResponse
from verisys.architecture import analyze_architecture, project_architecture_graph
from verisys.repository import discover_repository
from verisys.evaluation import normalize_architecture

client = TestClient(app, raise_server_exceptions=False)


def test_success_preserves_current_pipeline_and_no_flow_is_valid(tmp_path):
    (tmp_path / 'app.py').write_text('from fastapi import FastAPI\napp = FastAPI()\n@app.post("/hello")\ndef hello():\n    return "hello"\n')
    response = client.post('/api/analyze', json={'repository_path': str(tmp_path)})
    assert response.status_code == 200
    data = response.json()
    ir = analyze_architecture(discover_repository(tmp_path))
    assert data['architecture'] == ir.model_dump(mode='json')
    assert data['architecture_id'] == normalize_architecture(ir).architecture_id
    assert data['graph'] == project_architecture_graph(ir).model_dump(mode='json')
    assert data['graph']['execution_flows'] == []
    assert data['repository']['name'] == tmp_path.name
    assert data['repository']['path'] == str(tmp_path)
    assert data['repository']['source'] == {'type': 'local', 'path': str(tmp_path)}
    assert any(node['type'] == 'API_ROUTE' for node in data['graph']['nodes'])
    assert AnalyzeResponse.model_validate(data).graph.execution_flows == []
    assert response.json() == client.post('/api/analyze', json={'repository_path': str(tmp_path)}).json()


def test_supported_flow_comes_from_analysis(tmp_path):
    (tmp_path / 'workflow.py').write_text('''from langgraph.graph import StateGraph, END

def step(state):
    return state

def build():
    graph = StateGraph(dict)
    graph.add_node("step", step)
    graph.set_entry_point("step")
    graph.add_edge("step", END)
    return graph.compile()

agent_graph = build()
''')
    (tmp_path / 'api.py').write_text('''from fastapi import FastAPI
from workflow import agent_graph
app = FastAPI()
@app.post("/chat")
def chat(state):
    result = agent_graph.invoke(state)
    return result
''')
    data = client.post('/api/analyze', json={'repository_path': str(tmp_path)}).json()
    flow, = data['graph']['execution_flows']
    assert flow == data['architecture']['execution_flows'][0]
    assert flow['name'] == 'POST /chat → build'
    assert any(t['type'] == 'INVOKE' for t in flow['transitions'])
    assert all(t['source_locations'] for t in flow['transitions'])


@pytest.mark.parametrize('path', ['relative/path', '', '~', '\x00', 'https://github.com/example/repo'])
def test_invalid_path(path):
    response = client.post('/api/analyze', json={'repository_path': path})
    assert response.status_code == 400
    assert response.json()['error']['code'] in {'INVALID_REPOSITORY_PATH', 'INVALID_REPOSITORY_SOURCE'}


@pytest.mark.parametrize('payload', [{}, {'repository_path': 42}, {'repository_path': '/x', 'extra': True}])
def test_invalid_request_is_sanitized(payload):
    response = client.post('/api/analyze', json=payload)
    assert response.status_code == 400
    assert set(response.json()) == {'error'}
    assert 'detail' not in response.json()


def test_missing_path_and_file_path(tmp_path):
    response = client.post('/api/analyze', json={'repository_path': str(tmp_path / 'absent')})
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'REPOSITORY_NOT_FOUND'
    assert str(tmp_path) not in response.text
    file = tmp_path / 'file.py'
    file.write_text('')
    response = client.post('/api/analyze', json={'repository_path': str(file)})
    assert response.status_code == 400
    assert response.json()['error']['code'] == 'REPOSITORY_NOT_DIRECTORY'


def test_limitations_and_repo_code_are_not_executed(tmp_path):
    marker = tmp_path / 'executed'
    (tmp_path / 'app.py').write_text(f'open({str(marker)!r}, "w").write("ran")\n')
    (tmp_path / 'broken.py').write_text('bad syntax !')
    (tmp_path / '.env').write_text('SECRET=never-read')
    data = client.post('/api/analyze', json={'repository_path': str(tmp_path)}).json()
    assert not marker.exists()
    assert any('Python parse failed' in item for item in data['graph']['limitations'])
    assert data['graph']['limitations'] == data['architecture']['limitations']
    assert 'never-read' not in str(data)


def test_failure_does_not_expose_exception_text_or_stack(tmp_path, monkeypatch):
    api = importlib.import_module('verisys.api.app')
    def fail(_discovery):
        raise RuntimeError('sensitive private filesystem details')
    monkeypatch.setattr(api, 'analyze_architecture', fail)
    response = client.post('/api/analyze', json={'repository_path': str(tmp_path)})
    assert response.status_code == 500
    assert response.json() == {'error': {'code': 'ANALYSIS_FAILED', 'message': 'Repository analysis could not be completed.'}}


def test_browser_origin_boundary(tmp_path):
    response = client.post('/api/analyze', json={'repository_path': str(tmp_path)}, headers={'Origin': 'https://untrusted.example'})
    assert response.status_code == 403
    response = client.post('/api/analyze', json={'repository_path': str(tmp_path)}, headers={'Origin': 'http://127.0.0.1:3000'})
    assert response.status_code == 200
