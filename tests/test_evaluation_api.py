"""M5 HTTP composition with real safe analysis and controlled generation only."""
import importlib

import pytest
from fastapi.testclient import TestClient

from verisys.evaluation import DiscoveryError, StructuredGenerationResult
from verisys.evaluation.contracts import selection_schema

api = importlib.import_module('verisys.api.app')
client = TestClient(api.app, raise_server_exceptions=False)
URL = '/api/evaluations/discover'


class ControlledClient:
    provider = 'fake'
    model = 'fixture'

    def __init__(self, payload=None, failure=None, status='COMPLETED'):
        self.payload = payload
        self.failure = failure
        self.status = status
        self.inputs = []

    def generate(self, **kwargs):
        self.inputs.append(kwargs['structured_input'])
        assert kwargs['response_schema'].model_json_schema() == selection_schema(kwargs['structured_input'].eligible_options).model_json_schema()
        if self.failure:
            raise self.failure
        payload = self.payload if self.payload is not None else {
            'selected_option_ids': [option.option_id for option in kwargs['structured_input'].eligible_options]}
        return StructuredGenerationResult(payload=payload, status=self.status)


@pytest.fixture
def repository(tmp_path):
    (tmp_path / 'app.py').write_text('''from fastapi import FastAPI
from openai import OpenAI
app = FastAPI()
client = OpenAI()
@app.post("/chat")
def chat():
    return client.responses.create(model="example", input="example")
''')
    return tmp_path


@pytest.fixture(autouse=True)
def clean_overrides():
    yield
    api.app.dependency_overrides.clear()


def payload(repository):
    analysis = client.post('/api/analyze', json={'repository_path': str(repository)})
    return {'repository_path': str(repository), 'expected_architecture_id': analysis.json().get('architecture_id', '0' * 64)}


def request(repository, generator=None):
    api.app.dependency_overrides[api.discovery_client] = lambda: generator or ControlledClient()
    return client.post(URL, json=payload(repository))


def test_grounded_success_server_fields_and_narrow_response(repository):
    generator = ControlledClient()
    response = request(repository, generator)
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {'candidates', 'architecture_id', 'catalog_version', 'limitations', 'input_truncated', 'stored'}
    assert data['architecture_id'] == generator.inputs[0].architecture_id
    assert len(generator.inputs) == 1
    assert len(data['candidates']) == 2
    index = {subject.id for subject in generator.inputs[0].subjects}
    for candidate in data['candidates']:
        assert set(candidate) == set(api.SuggestedVerification.model_fields)
        assert set(candidate['architecture_subject_ids']) <= index
        assert candidate['priority'] == 'MEDIUM'
        assert candidate['applicability'] == 'APPLICABLE'
        assert candidate['reason'] and candidate['required_evidence']
    timeout = next(c for c in data['candidates'] if c['verification_mode'] == 'STATIC')
    assert timeout['execution_support'] == 'SUPPORTED'
    latency = next(c for c in data['candidates'] if c['verification_mode'] == 'PERFORMANCE')
    assert latency['execution_support'] == 'NOT_AVAILABLE'
    assert 'provider' not in data and 'diagnostics' not in data
    api.EvaluationDiscoveryResponse.model_validate(data)


def test_valid_empty_selection_is_success(repository):
    response = request(repository, ControlledClient({'selected_option_ids': []}))
    assert response.status_code == 200 and response.json()['candidates'] == []


@pytest.mark.parametrize('variable', ['OPENAI_API_KEY', 'VERISYS_DISCOVERY_MODEL'])
def test_missing_configuration_is_controlled(repository, monkeypatch, variable):
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-test-key')
    monkeypatch.setenv('VERISYS_DISCOVERY_MODEL', 'fixture-model')
    monkeypatch.delenv(variable, raising=False)
    response = client.post(URL, json=payload(repository))
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'DISCOVERY_CONFIGURATION_MISSING'
    assert 'synthetic-test-key' not in response.text


def test_invalid_model_configuration_is_sanitized(repository, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-test-key')
    monkeypatch.setenv('VERISYS_DISCOVERY_MODEL', 'x' * 129)
    response = client.post(URL, json=payload(repository))
    assert response.status_code == 503 and 'x' * 129 not in response.text


@pytest.mark.parametrize('failure,status', [(RuntimeError('private secret'), 502), (TimeoutError('private secret'), 504)])
def test_provider_failure_is_not_empty_success(repository, failure, status):
    response = request(repository, ControlledClient(failure=failure))
    assert response.status_code == status
    assert response.json()['error']['code'] == 'DISCOVERY_PROVIDER_FAILED'
    assert 'candidates' not in response.json() and 'private secret' not in response.text


@pytest.mark.parametrize('status', ['REFUSED', 'INCOMPLETE'])
def test_provider_status_failure(repository, status):
    response = request(repository, ControlledClient(status=status))
    assert response.status_code == 502
    assert response.json()['error']['code'] == 'DISCOVERY_PROVIDER_FAILED'


@pytest.mark.parametrize('payload', [
    {'selected_option_ids': ['invented']},
    {'selected_option_ids': [], 'applicability': 'APPLICABLE'},
    {'candidates': []},
])
def test_invalid_selection_is_distinct_validation_failure(repository, payload):
    response = request(repository, ControlledClient(payload))
    assert response.status_code == 502
    assert response.json()['error']['code'] == 'DISCOVERY_VALIDATION_FAILED'
    assert 'candidates' not in response.json()


def test_repository_errors_and_analysis_failure_do_not_call_provider(repository, monkeypatch):
    generator = ControlledClient()
    response = request(repository / 'absent', generator)
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'REPOSITORY_NOT_FOUND'
    def fail(_):
        raise RuntimeError('private filesystem info')
    monkeypatch.setattr(api, 'analyze_architecture', fail)
    response = request(repository, generator)
    assert response.status_code == 500
    assert response.json()['error']['code'] == 'ANALYSIS_FAILED'
    assert 'private filesystem info' not in response.text
    assert not generator.inputs


@pytest.mark.parametrize('field', ['architecture', 'candidates', 'architecture_id', 'priority'])
def test_browser_cannot_supply_authoritative_data(repository, field):
    generator = ControlledClient()
    api.app.dependency_overrides[api.discovery_client] = lambda: generator
    response = client.post(URL, json={**payload(repository), field: {}})
    assert response.status_code == 400 and not generator.inputs


def test_no_verification_evidence_verdict_or_repository_execution(repository, monkeypatch):
    marker = repository / 'executed'
    (repository / 'evil.py').write_text(f'from pathlib import Path\nPath({str(marker)!r}).write_text("executed")\n')
    def forbidden(*args, **kwargs):
        raise AssertionError('Verification/evidence/verdict must never run')
    discovery = importlib.import_module('verisys.evaluation.discovery')
    monkeypatch.setattr(discovery, 'get_verifier', lambda identifier: forbidden if identifier == 'external-api-timeout-coverage-v1' else None)
    run = importlib.import_module('verisys.verification.run')
    monkeypatch.setattr(run, 'verify_timeout_coverage', forbidden)
    from verisys.models import Evidence, Verdict
    monkeypatch.setattr(Evidence, '__init__', forbidden)
    monkeypatch.setattr(Verdict, '__init__', forbidden)
    response = request(repository)
    assert response.status_code == 200
    assert not marker.exists()
    assert not {'evidence', 'verdict', 'trace'} & response.json().keys()
    assert all('related_architecture_evidence_ids' not in c for c in response.json()['candidates'])


def test_discovery_does_not_load_dotenv(repository, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('VERISYS_DISCOVERY_MODEL', raising=False)
    assert client.post(URL, json=payload(repository)).status_code == 503


def test_untrusted_browser_origin_does_not_call_provider(repository):
    generator = ControlledClient()
    api.app.dependency_overrides[api.discovery_client] = lambda: generator
    response = client.post(URL, json=payload(repository), headers={'Origin': 'https://untrusted.example'})
    assert response.status_code == 403 and not generator.inputs


def test_stale_analysis_rejected_before_generation_or_verification(repository, monkeypatch):
    expected = payload(repository)
    (repository / 'app.py').write_text((repository / 'app.py').read_text().replace('/chat', '/changed'))
    generator = ControlledClient()
    api.app.dependency_overrides[api.discovery_client] = lambda: generator
    def forbidden(*args, **kwargs):
        raise AssertionError('No generation or verification on stale input')
    monkeypatch.setattr(api, 'discover_evaluations', forbidden)
    from verisys.models import Evidence, Verdict
    monkeypatch.setattr(Evidence, '__init__', forbidden)
    monkeypatch.setattr(Verdict, '__init__', forbidden)
    run = importlib.import_module('verisys.verification.run')
    monkeypatch.setattr(run, 'verify_timeout_coverage', forbidden)
    response = client.post(URL, json=expected)
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'ANALYSIS_STALE'
    assert set(response.json()) == {'error'}
    assert not generator.inputs


def test_expected_id_is_precondition_not_authority(repository, monkeypatch):
    expected = payload(repository)
    generator = ControlledClient()
    api.app.dependency_overrides[api.discovery_client] = lambda: generator
    real_analysis = api.analyze_architecture
    calls = []
    def observed(discovery):
        calls.append(discovery)
        return real_analysis(discovery)
    monkeypatch.setattr(api, 'analyze_architecture', observed)
    response = client.post(URL, json=expected)
    assert response.status_code == 200
    assert response.json()['architecture_id'] == expected['expected_architecture_id']
    assert len(calls) == 1 and len(generator.inputs) == 1
    response = client.post(URL, json={**expected, 'expected_architecture_id': '0' * 64})
    assert response.status_code == 409 and len(calls) == 2 and len(generator.inputs) == 1


@pytest.mark.parametrize('identifier', [None, 'invalid', 42])
def test_missing_or_invalid_precondition_is_rejected(repository, identifier):
    generator = ControlledClient()
    api.app.dependency_overrides[api.discovery_client] = lambda: generator
    data = {'repository_path': str(repository)}
    if identifier is not None:
        data['expected_architecture_id'] = identifier
    assert client.post(URL, json=data).status_code == 400
    assert not generator.inputs


def test_capability_is_registry_owned_even_for_partial_candidate(repository, monkeypatch):
    (repository/'app.py').write_text('from langchain_openai import ChatOpenAI\nclient=ChatOpenAI()\n')
    response=request(repository)
    assert response.status_code == 200
    timeout=response.json()['candidates'][0]
    assert timeout['execution_support'] == 'PARTIAL' and timeout['can_execute'] is True
    monkeypatch.setattr(api,'get_verifier',lambda _:None)
    assert request(repository).json()['candidates'][0]['can_execute'] is False
