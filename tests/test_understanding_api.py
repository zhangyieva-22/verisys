"""Understanding HTTP composition with real safe analysis and a fake model client only."""
import importlib

import pytest
from fastapi.testclient import TestClient

from verisys.evaluation import DiscoveryError, StructuredGenerationResult

api = importlib.import_module('verisys.api.app')
client = TestClient(api.app, raise_server_exceptions=False)
URL = '/api/understanding'


class Fake:
    provider, model = 'fake', 'fixture'

    def __init__(self, payload=None, failure=None):
        self.payload, self.failure, self.inputs = payload, failure, []

    def generate(self, **kwargs):
        self.inputs.append(kwargs['structured_input'])
        if self.failure:
            raise self.failure
        return StructuredGenerationResult(payload=self.payload)


@pytest.fixture
def repository(tmp_path):
    (tmp_path / 'README.md').write_text('# Notes\nUsers save notes.\n')
    (tmp_path / 'app.py').write_text('from fastapi import FastAPI\napp = FastAPI()\n@app.post("/notes")\ndef save():\n    return {}\n')
    return tmp_path


@pytest.fixture(autouse=True)
def clean_overrides():
    yield
    api.app.dependency_overrides.clear()


def body(repository):
    analysis = client.post('/api/analyze', json={'repository_path': str(repository)}).json()
    return {'repository_path': str(repository), 'expected_architecture_id': analysis['architecture_id']}


def test_returns_checked_inferred_claims(repository):
    fake = Fake({'functional_requirements': [{'title': 'Save notes', 'description': 'Users can save notes.',
        'citations': [{'excerpt_id': 'E1', 'start_line': 2, 'end_line': 2, 'quote': 'Users save notes.'}]}], 'risks': []})
    api.app.dependency_overrides[api.understanding_client] = lambda: fake
    response = client.post(URL, json=body(repository))
    assert response.status_code == 200, response.text
    data = response.json()
    [requirement] = data['functional_requirements']
    assert requirement['status'] == 'INFERRED_NOT_VERIFIED'
    assert requirement['citations'] == [{'path': 'README.md', 'start_line': 2, 'end_line': 2,
                                         'quote': 'Users save notes.', 'excerpt_kind': 'README'}]
    assert [source['path'] for source in data['sources']] == ['README.md', 'app.py']
    assert str(repository) not in response.text and len(fake.inputs) == 1


def test_stale_analysis_makes_no_model_call(repository):
    fake = Fake({'functional_requirements': [], 'risks': []})
    api.app.dependency_overrides[api.understanding_client] = lambda: fake
    response = client.post(URL, json={**body(repository), 'expected_architecture_id': '0' * 64})
    assert response.status_code == 409 and response.json()['error']['code'] == 'ANALYSIS_STALE'
    assert fake.inputs == []


def test_missing_configuration(repository, monkeypatch):
    for name in ('OPENAI_API_KEY', 'VERISYS_DISCOVERY_MODEL', 'VERISYS_UNDERSTANDING_MODEL'):
        monkeypatch.delenv(name, raising=False)
    response = client.post(URL, json=body(repository))
    assert response.status_code == 503 and response.json()['error']['code'] == 'UNDERSTANDING_CONFIGURATION_MISSING'


def test_understanding_model_falls_back_to_discovery_model(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'placeholder-not-a-key')
    monkeypatch.delenv('VERISYS_UNDERSTANDING_MODEL', raising=False)
    monkeypatch.setenv('VERISYS_DISCOVERY_MODEL', 'model-a')
    assert api.understanding_client().model == 'model-a'
    monkeypatch.setenv('VERISYS_UNDERSTANDING_MODEL', 'model-b')
    assert api.understanding_client().model == 'model-b'


@pytest.mark.parametrize('failure,status,code', [
    (DiscoveryError('provider_timeout'), 504, 'UNDERSTANDING_PROVIDER_FAILED'),
    (DiscoveryError('provider_unavailable'), 502, 'UNDERSTANDING_PROVIDER_FAILED'),
    (RuntimeError('sk-secret detail'), 502, 'UNDERSTANDING_PROVIDER_FAILED'),
    (DiscoveryError('invalid_structured_output'), 502, 'UNDERSTANDING_VALIDATION_FAILED'),
])
def test_provider_failures_are_controlled(repository, failure, status, code):
    api.app.dependency_overrides[api.understanding_client] = lambda: Fake(failure=failure)
    response = client.post(URL, json=body(repository))
    assert response.status_code == status and response.json()['error']['code'] == code
    assert 'sk-secret' not in response.text


def test_unpinned_github_source_is_rejected_before_any_work():
    fake = Fake({'functional_requirements': [], 'risks': []})
    api.app.dependency_overrides[api.understanding_client] = lambda: fake
    response = client.post(URL, json={'source': {'type': 'github', 'url': 'https://github.com/o/r'},
                                      'expected_architecture_id': 'a' * 64})
    assert response.status_code == 400 and response.json()['error']['code'] == 'IMMUTABLE_REVISION_REQUIRED'
    assert fake.inputs == []


def test_analysis_never_triggers_understanding(repository, monkeypatch):
    monkeypatch.setattr(api, 'understand_repository', lambda *a, **k: pytest.fail('analysis must not call the model'))
    assert client.post('/api/analyze', json={'repository_path': str(repository)}).status_code == 200
