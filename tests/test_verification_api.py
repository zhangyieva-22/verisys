"""M6 composes the real static verifier; fixtures are data, never imported."""
import importlib
import pytest
from fastapi.testclient import TestClient

api = importlib.import_module('verisys.api.app')
client = TestClient(api.app, raise_server_exceptions=False)
URL = '/api/evaluations/verify'
ID = 'external-api-timeout-coverage-v1'


def repository(tmp_path, args):
    source = 'from openai import OpenAI\nclient = OpenAI()\n'
    source += ''.join(f'client.responses.create(input="example"{arg})\n' for arg in args)
    (tmp_path / 'app.py').write_text(source)
    return tmp_path


def payload(root):
    data = client.post('/api/analyze', json={'repository_path': str(root)}).json()
    return dict(repository_path=str(root), evaluation_id=ID, expected_architecture_id=data['architecture_id'])


@pytest.mark.parametrize('args,status,counts,coverage', [
    ([', timeout=2', ', timeout=3', ''], 'VIOLATED', [2,1,0,3], 66.7),
    ([', timeout=setting'], 'NOT_VERIFIABLE', [0,0,1,1], None),
    ([', timeout=2'], 'VERIFIED', [1,0,0,1], 100.0),
    ([], None, [0,0,0,0], None),
    (['', ', timeout=setting'], 'VIOLATED', [0,1,1,2], None),
])
def test_existing_judgment_and_provenance(tmp_path, monkeypatch, args, status, counts, coverage):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr(api, 'discover_evaluations', lambda *a: pytest.fail('No provider or discovery during verification'))
    root = repository(tmp_path, args)
    marker = root / 'marker'
    (root / 'never_import.py').write_text(f'from pathlib import Path\nPath({str(marker)!r}).touch()\n')
    request = payload(root)
    response = client.post(URL, json=request)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['architecture_id'] == request['expected_architecture_id']
    assert result['verdict_status'] == status
    assert list(result['counts'].values()) == counts
    assert result['coverage_percent'] == coverage
    assert result['applicability'] == ('APPLICABLE' if args else 'NOT_APPLICABLE')
    assert result['execution_status'] == ('COMPLETED' if args else 'NOT_RUN')
    calls = [e for e in result['evidence'] if e['observation']['kind'] == 'call']
    assert len(calls) == len(args)
    assert [e['source_location']['line'] for e in calls] == list(range(3,3+len(args)))
    assert all(e['source_location']['file'] == 'app.py' and e['tool'] == 'python-static-timeout-v1' for e in calls)
    assert set(result['verdict_evidence_ids']) <= {e['id'] for e in result['evidence']}
    assert result['trace'] and not marker.exists()
    assert 'architecture' not in result and 'plan' not in result


def test_stale_prevents_registry_execution(tmp_path, monkeypatch):
    root = repository(tmp_path, [''])
    request = payload(root)
    (root/'route.py').write_text('from fastapi import FastAPI\napp=FastAPI()\n@app.get("/new")\ndef x(): pass\n')
    monkeypatch.setattr(api, 'get_verifier', lambda _: pytest.fail('Stale must stop before resolution'))
    response = client.post(URL, json=request)
    assert response.status_code == 409 and response.json()['error']['code'] == 'ANALYSIS_STALE'


@pytest.mark.parametrize('identifier', ['api-latency-v1','retry-safety-v1','tool-side-effect-safety-v1','invented'])
def test_unsupported(tmp_path, identifier):
    request = payload(repository(tmp_path, ['']))
    request['evaluation_id'] = identifier
    response = client.post(URL, json=request)
    assert response.status_code == 400 and response.json()['error']['code'] == 'VERIFICATION_UNSUPPORTED'


@pytest.mark.parametrize('field', ['evidence','verdict','plan','candidate','architecture'])
def test_browser_authority_rejected(tmp_path, field):
    response = client.post(URL, json={**payload(repository(tmp_path, [''])), field: {}})
    assert response.status_code == 400 and response.json()['error']['code'] == 'VERIFICATION_BAD_REQUEST'


def test_execution_failure_is_not_verdict(tmp_path, monkeypatch):
    request = payload(repository(tmp_path, ['']))
    def fail(_): raise RuntimeError('private details')
    monkeypatch.setattr(api, 'get_verifier', lambda _: fail)
    response = client.post(URL, json=request)
    assert response.status_code == 500 and response.json()['error']['code'] == 'VERIFICATION_FAILED'
    assert 'private details' not in response.text and 'verdict_status' not in response.json()


def test_analysis_failure_is_distinct(tmp_path, monkeypatch):
    request = payload(repository(tmp_path, ['']))
    monkeypatch.setattr(api, 'analyze_architecture', lambda _: (_ for _ in ()).throw(RuntimeError()))
    response = client.post(URL, json=request)
    assert response.status_code == 500 and response.json()['error']['code'] == 'ANALYSIS_FAILED'


def test_snapshot_changed_during_verifier_not_published(tmp_path, monkeypatch):
    request = payload(repository(tmp_path, ['']))
    real = api.get_verifier(ID)
    def changed(root):
        (tmp_path/'new.py').write_text('from fastapi import FastAPI\napp=FastAPI()\n')
        return real(root)
    monkeypatch.setattr(api,'get_verifier',lambda _:changed)
    response=client.post(URL,json=request)
    assert response.status_code == 409 and response.json()['error']['code'] == 'ANALYSIS_STALE'
