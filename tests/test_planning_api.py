"""AI plan drafting uses checked excerpts and never executes a verifier."""
import importlib
import pytest
from fastapi.testclient import TestClient
from verisys.evaluation import DiscoveryError, StructuredGenerationResult
api=importlib.import_module('verisys.api.app')
client=TestClient(api.app,raise_server_exceptions=False)


def draft(quote='Users save notes.'):
    return {'title':'Save notes','objective':'Check that submitted notes can be retrieved.',
            'prerequisites':['Isolated test database and a confirmed persistence requirement.'],
            'steps':['Submit a note and retrieve it through the documented interface.'],
            'required_evidence':['Executed test output and returned note contents.'],
            'acceptance_questions':['Confirm the expected fields and persistence lifetime.'],
            'citations':[{'excerpt_id':'E1','start_line':2,'end_line':2,'quote':quote}]}


class Fake:
    provider,model='fake','fixture'
    def __init__(self,payload=None,failure=None):self.calls=[];self.payload=payload or {'plans':[draft()]};self.failure=failure
    def generate(self,**kwargs):
        self.calls.append(kwargs)
        if self.failure:raise self.failure
        return StructuredGenerationResult(payload=self.payload)


@pytest.fixture
def repo(tmp_path):
    (tmp_path/'README.md').write_text('# Notes\nUsers save notes.\n')
    (tmp_path/'app.py').write_text('from fastapi import FastAPI\napp=FastAPI()\n@app.post("/notes")\ndef save():\n    return {}\n')
    return tmp_path


@pytest.fixture(autouse=True)
def overrides():
    yield
    api.app.dependency_overrides.clear()


def body(repo,target='functional-requirements'):
    a=client.post('/api/analyze',json={'repository_path':str(repo)}).json()
    return {'repository_path':str(repo),'expected_architecture_id':a['architecture_id'],'target_id':target}


def test_functional_plan_has_checked_grounding_and_no_verification(repo,monkeypatch):
    fake=Fake();api.app.dependency_overrides[api.understanding_client]=lambda:fake
    monkeypatch.setattr(api,'get_verifier',lambda _:pytest.fail('Planning must not execute or select a verifier'))
    r=client.post('/api/evaluations/plan',json=body(repo))
    assert r.status_code==200,r.text
    d=r.json();assert d['kind']=='FUNCTIONAL'
    assert d['plans'][0]['status']=='DRAFT_NOT_EXECUTED'
    assert d['plans'][0]['citations'][0]['path']=='README.md'
    assert not {'verdict','evidence','applicability','execution_support','priority'} & d.keys()
    assert len(fake.calls)==1 and str(repo) not in str(fake.calls[0]['structured_input'])


def test_nonfunctional_scope_is_server_owned(repo):
    fake=Fake();api.app.dependency_overrides[api.understanding_client]=lambda:fake
    r=client.post('/api/evaluations/plan',json=body(repo,'api-latency-v1'))
    assert r.status_code==200,r.text
    assert r.json()['kind']=='NON_FUNCTIONAL'
    assert 'API Latency' in fake.calls[0]['instructions']


@pytest.mark.parametrize('changes,code',[({'expected_architecture_id':'0'*64},'ANALYSIS_STALE'),({'target_id':'invented'},'PLAN_UNSUPPORTED'),({'target_id':'retry-safety-v1'},'PLAN_UNSUPPORTED')])
def test_invalid_scope_never_calls_provider(repo,changes,code):
    fake=Fake();api.app.dependency_overrides[api.understanding_client]=lambda:fake
    r=client.post('/api/evaluations/plan',json={**body(repo),**changes})
    assert r.json()['error']['code']==code
    assert fake.calls==[]


def test_bad_citation_drops_draft_without_repair(repo):
    fake=Fake({'plans':[draft('invented source quotation')]});api.app.dependency_overrides[api.understanding_client]=lambda:fake
    r=client.post('/api/evaluations/plan',json=body(repo))
    assert r.status_code==200 and r.json()['plans']==[]
    assert any('dropped' in x for x in r.json()['limitations'])


def test_model_cannot_add_verdict(repo):
    fake=Fake({'plans':[{**draft(),'verdict':'VERIFIED'}]});api.app.dependency_overrides[api.understanding_client]=lambda:fake
    r=client.post('/api/evaluations/plan',json=body(repo))
    assert r.status_code==502 and r.json()['error']['code']=='PLAN_VALIDATION_FAILED'


def test_provider_failure_is_not_empty_success(repo):
    fake=Fake(failure=DiscoveryError('provider_timeout'));api.app.dependency_overrides[api.understanding_client]=lambda:fake
    r=client.post('/api/evaluations/plan',json=body(repo))
    assert r.status_code==504 and r.json()['error']['code']=='PLAN_PROVIDER_FAILED'
    assert len(fake.calls)==1


def test_no_excerpts_no_model_call(tmp_path):
    fake=Fake();api.app.dependency_overrides[api.understanding_client]=lambda:fake
    r=client.post('/api/evaluations/plan',json=body(tmp_path))
    assert r.status_code==200 and r.json()['plans']==[] and fake.calls==[]


def test_private_dotenv_and_code_are_not_executed(repo):
    (repo/'.env').write_text('PASSWORD=never-send-this-secret')
    (repo/'app.py').write_text('from pathlib import Path\nPath("executed-marker").touch()\n')
    fake=Fake();api.app.dependency_overrides[api.understanding_client]=lambda:fake
    r=client.post('/api/evaluations/plan',json=body(repo))
    assert r.status_code==200
    assert 'never-send-this-secret' not in str(fake.calls)
    assert not (repo/'executed-marker').exists()
