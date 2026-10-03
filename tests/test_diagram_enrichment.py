"""Diagram enrichment uses fake clients only; fixtures are never imported or executed."""
import importlib

import pytest
from fastapi.testclient import TestClient

from verisys.architecture import analyze_architecture
from verisys.evaluation import DiscoveryError, StructuredGenerationResult
from verisys.repository import discover_repository
from verisys.understanding import enrich_diagram, select_excerpts, validate_diagram

api = importlib.import_module('verisys.api.app')
client = TestClient(api.app, raise_server_exceptions=False)


def write(root, name, text):
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(text)


@pytest.fixture
def repo(tmp_path):
    write(tmp_path, 'README.md', '# Shop\nA Next.js web app calls the FastAPI backend.\nOrders are stored in Postgres.\n')
    write(tmp_path, 'web/package.json', '{\n  "name": "shop-web",\n  "dependencies": {"next": "16"}\n}\n')
    write(tmp_path, 'api/main.py', 'from fastapi import FastAPI\napp = FastAPI()\n@app.post("/orders")\ndef create():\n    return {}\n')
    return tmp_path


@pytest.fixture(autouse=True)
def clean_overrides():
    yield
    api.app.dependency_overrides.clear()


class Fake:
    provider, model = 'fake', 'fixture'

    def __init__(self, payload=None, failure=None):
        self.payload, self.failure, self.calls = payload, failure, []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.failure:
            raise self.failure
        return StructuredGenerationResult(payload=self.payload)


def cite(eid, line, quote):
    return [{'excerpt_id': eid, 'start_line': line, 'end_line': line, 'quote': quote}]


def excerpts(root):
    discovery = discover_repository(root)
    return select_excerpts(discovery, analyze_architecture(discovery))[0]


GOOD = {
    'components': [
        {'layer': 'FRONTEND', 'label': 'Next.js web app', 'detail': 'Browser UI', 'citations': cite('E1', 2, 'A Next.js web app')},
        {'layer': 'DATA', 'label': 'Postgres', 'detail': 'Order storage', 'citations': cite('E1', 3, 'stored in Postgres')},
    ],
    'request_path': [{'label': 'Web app', 'citations': cite('E2', 2, '"name": "shop-web"')},
                     {'label': 'FastAPI backend', 'citations': cite('E1', 2, 'calls the FastAPI backend')}],
}


def test_valid_components_and_path_keep_checked_citations(repo):
    fake = Fake(GOOD)
    discovery = discover_repository(repo)
    result = enrich_diagram(discovery, analyze_architecture(discovery), architecture_id='a' * 64, repository='shop', client=fake)
    assert [(c.layer, c.label, c.status) for c in result.components] == [
        ('FRONTEND', 'Next.js web app', 'INFERRED_NOT_VERIFIED'), ('DATA', 'Postgres', 'INFERRED_NOT_VERIFIED')]
    assert [s.label for s in result.request_path] == ['Web app', 'FastAPI backend']
    assert result.components[0].citations[0].path == 'README.md'
    assert result.request_path[0].citations[0].excerpt_kind == 'MANIFEST'
    assert 'Do not repeat them' in fake.calls[0]['instructions']
    schema = fake.calls[0]['response_schema'].model_json_schema()
    assert schema['$defs']['Component']['properties']['layer']['enum'][0] == 'CLIENT'


def test_unsupported_items_are_dropped_and_counted(repo):
    payload = {'components': [
        {'layer': 'DATA', 'label': 'Redis', 'detail': 'Cache', 'citations': cite('E1', 3, 'Redis cache')},  # quote not in text
        {'layer': 'DATA', 'label': 'Postgres', 'detail': '', 'citations': cite('E1', 3, 'stored in Postgres')},
        {'layer': 'DATA', 'label': 'postgres', 'detail': 'dup', 'citations': cite('E1', 3, 'stored in Postgres')},
        {'layer': 'MOON', 'label': 'Bad layer', 'detail': '', 'citations': cite('E1', 3, 'stored in Postgres')}],
        'request_path': [{'label': 'Only step', 'citations': cite('E1', 2, 'A Next.js web app')}]}
    components, steps, rejected_items, rejected_citations = validate_diagram(payload, excerpts(repo), 'a' * 64)
    assert [c.label for c in components] == ['Postgres']
    assert steps == []  # a single surviving step is not a path
    assert (rejected_items, rejected_citations) == (4, 1)


@pytest.mark.parametrize('payload', [None, {'components': []}, {'components': 'x', 'request_path': []}])
def test_malformed_payload_is_rejected(repo, payload):
    with pytest.raises(DiscoveryError, match='invalid_structured_output'):
        validate_diagram(payload, excerpts(repo), 'a' * 64)


def body(root):
    analysis = client.post('/api/analyze', json={'repository_path': str(root)}).json()
    return {'repository_path': str(root), 'expected_architecture_id': analysis['architecture_id']}


def test_endpoint_returns_inferred_components(repo):
    api.app.dependency_overrides[api.understanding_client] = lambda: Fake(GOOD)
    response = client.post('/api/diagram/enrich', json=body(repo))
    assert response.status_code == 200, response.text
    data = response.json()
    assert [c['label'] for c in data['components']] == ['Next.js web app', 'Postgres']
    assert all(c['status'] == 'INFERRED_NOT_VERIFIED' for c in data['components'] + data['request_path'])
    assert str(repo) not in response.text


def test_endpoint_stale_and_errors_use_diagram_codes(repo, monkeypatch):
    fake = Fake(GOOD)
    api.app.dependency_overrides[api.understanding_client] = lambda: fake
    stale = client.post('/api/diagram/enrich', json={**body(repo), 'expected_architecture_id': '0' * 64})
    assert stale.status_code == 409 and fake.calls == []
    api.app.dependency_overrides[api.understanding_client] = lambda: Fake(failure=DiscoveryError('provider_timeout'))
    failed = client.post('/api/diagram/enrich', json=body(repo))
    assert failed.status_code == 504 and failed.json()['error']['code'] == 'DIAGRAM_PROVIDER_FAILED'
    api.app.dependency_overrides.clear()
    for name in ('OPENAI_API_KEY', 'VERISYS_DISCOVERY_MODEL', 'VERISYS_UNDERSTANDING_MODEL'):
        monkeypatch.delenv(name, raising=False)
    missing = client.post('/api/diagram/enrich', json=body(repo))
    assert missing.status_code == 503 and missing.json()['error']['code'] == 'DIAGRAM_CONFIGURATION_MISSING'
