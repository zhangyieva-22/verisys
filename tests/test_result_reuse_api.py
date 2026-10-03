"""Saved results are reused only for identical, immutable inputs; offline doubles only."""
import importlib
import tarfile

import pytest
from fastapi.testclient import TestClient

from verisys.evaluation import StructuredGenerationResult
from verisys.repository.github import RepositoryMaterializer
from verisys.store import ResultStore
from test_remote_repository import FakeFetcher, archive, SHA, URL

api = importlib.import_module('verisys.api.app')
client = TestClient(api.app, raise_server_exceptions=False)
SOURCE = {'type': 'github', 'url': URL, 'ref': SHA}
CODE = (b'from fastapi import FastAPI\nfrom openai import OpenAI\napp = FastAPI()\nclient = OpenAI()\n'
        b'@app.post("/chat")\ndef chat():\n    return client.responses.create(input="x", timeout=2)\n')


class Model:
    provider, model = 'fake', 'fixture-model'

    def __init__(self):
        self.calls = 0

    def generate(self, **kwargs):
        self.calls += 1
        context = getattr(kwargs['structured_input'], 'architecture', kwargs['structured_input'])
        if hasattr(context, 'eligible_options'):
            return StructuredGenerationResult(payload={'selected_option_ids': [o.option_id for o in context.eligible_options]})
        return StructuredGenerationResult(payload={'functional_requirements': [], 'risks': []})


@pytest.fixture
def remote(tmp_path):
    fetcher = FakeFetcher(archive([('repo/README.md', b'# Chat\nAnswers questions.\n', tarfile.REGTYPE),
                                   ('repo/app.py', CODE, tarfile.REGTYPE)]))
    model = Model()
    api.app.dependency_overrides[api.repository_materializer] = lambda: RepositoryMaterializer(fetcher, temp_parent=tmp_path)
    api.app.dependency_overrides[api.discovery_client] = lambda: model
    api.app.dependency_overrides[api.understanding_client] = lambda: model
    architecture_id = client.post('/api/analyze', json={'source': SOURCE}).json()['architecture_id']
    yield fetcher, model, architecture_id
    api.app.dependency_overrides.clear()


def downloads(fetcher):
    return sum('codeload.github.com' in url for url in fetcher.urls)


def test_discovery_is_reused_for_a_pinned_commit_without_download_or_model(remote):
    fetcher, model, architecture_id = remote
    body = {'source': SOURCE, 'expected_architecture_id': architecture_id}
    first = client.post('/api/evaluations/discover', json=body).json()
    assert first['stored']['reused'] is False and first['stored']['saved_at']
    before = downloads(fetcher)
    second = client.post('/api/evaluations/discover', json=body).json()
    assert second['stored'] == {'reused': True, 'saved_at': first['stored']['saved_at']}
    assert second['candidates'] == first['candidates']
    assert model.calls == 1 and downloads(fetcher) == before


def test_refresh_and_different_inputs_regenerate(remote):
    _, model, architecture_id = remote
    body = {'source': SOURCE, 'expected_architecture_id': architecture_id}
    client.post('/api/evaluations/discover', json=body)
    refreshed = client.post('/api/evaluations/discover', json={**body, 'refresh': True}).json()
    assert refreshed['stored']['reused'] is False and model.calls == 2
    concern = client.post('/api/evaluations/discover', json={**body, 'mode': 'ON_DEMAND', 'request_text': 'timeouts'}).json()
    assert concern['stored']['reused'] is False and model.calls == 3
    assert client.post('/api/evaluations/discover', json=body).json()['stored']['reused'] is True and model.calls == 3


def test_verification_is_reused_for_a_pinned_commit(remote):
    fetcher, _, architecture_id = remote
    body = {'source': SOURCE, 'expected_architecture_id': architecture_id, 'evaluation_id': 'external-api-timeout-coverage-v1'}
    first = client.post('/api/evaluations/verify', json=body).json()
    assert first['verdict_status'] == 'VERIFIED' and first['stored']['reused'] is False
    before = downloads(fetcher)
    second = client.post('/api/evaluations/verify', json=body).json()
    assert second['stored']['reused'] is True and downloads(fetcher) == before
    assert {k: v for k, v in second.items() if k != 'stored'} == {k: v for k, v in first.items() if k != 'stored'}
    rerun = client.post('/api/evaluations/verify', json={**body, 'refresh': True}).json()
    assert rerun['stored']['reused'] is False and downloads(fetcher) == before + 1


def test_understanding_is_reused_for_a_pinned_commit(remote):
    _, model, architecture_id = remote
    body = {'source': SOURCE, 'expected_architecture_id': architecture_id}
    assert client.post('/api/understanding', json=body).json()['stored']['reused'] is False
    assert client.post('/api/understanding', json=body).json()['stored']['reused'] is True
    assert model.calls == 1


def test_stale_architecture_id_never_hits_a_saved_result(remote):
    _, model, architecture_id = remote
    client.post('/api/evaluations/discover', json={'source': SOURCE, 'expected_architecture_id': architecture_id})
    stale = client.post('/api/evaluations/discover', json={'source': SOURCE, 'expected_architecture_id': '0' * 64})
    assert stale.status_code == 409 and model.calls == 1


def test_corrupt_saved_file_is_regenerated(remote, monkeypatch, tmp_path):
    _, model, architecture_id = remote
    body = {'source': SOURCE, 'expected_architecture_id': architecture_id}
    client.post('/api/evaluations/discover', json=body)
    root = ResultStore().root
    for path in (root / 'discovery').iterdir():
        path.write_text('{"store_version": "result-store-v1", "kind": "discovery"')
    assert client.post('/api/evaluations/discover', json=body).json()['stored']['reused'] is False
    assert model.calls == 2


def test_local_sources_reuse_discovery_but_never_source_dependent_results(tmp_path):
    (tmp_path / 'README.md').write_text('# Chat\n')
    (tmp_path / 'app.py').write_text(CODE.decode())
    model = Model()
    api.app.dependency_overrides[api.discovery_client] = lambda: model
    api.app.dependency_overrides[api.understanding_client] = lambda: model
    try:
        architecture_id = client.post('/api/analyze', json={'repository_path': str(tmp_path)}).json()['architecture_id']
        body = {'repository_path': str(tmp_path), 'expected_architecture_id': architecture_id}
        client.post('/api/evaluations/discover', json=body)
        assert client.post('/api/evaluations/discover', json=body).json()['stored']['reused'] is True
        verify = {**body, 'evaluation_id': 'external-api-timeout-coverage-v1'}
        assert client.post('/api/evaluations/verify', json=verify).json()['verdict_status'] == 'VERIFIED'
        # Same architecture_id, different timeout literal: a local re-run must see the change.
        (tmp_path / 'app.py').write_text(CODE.decode().replace('timeout=2', 'timeout=None'))
        rerun = client.post('/api/evaluations/verify', json=verify).json()
        assert rerun['verdict_status'] == 'VIOLATED' and rerun['stored']['reused'] is False
        calls = model.calls
        client.post('/api/understanding', json=body)
        client.post('/api/understanding', json=body)
        assert model.calls == calls + 2
    finally:
        api.app.dependency_overrides.clear()


def test_saved_files_live_in_the_configured_store_not_the_repository(remote, tmp_path):
    _, _, architecture_id = remote
    client.post('/api/evaluations/discover', json={'source': SOURCE, 'expected_architecture_id': architecture_id})
    assert list((ResultStore().root / 'discovery').glob('*.json'))
    assert not list(tmp_path.rglob('.verisys'))
