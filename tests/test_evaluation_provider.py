"""The real SDK's structured parsing is exercised through an HTTP mock only."""
import json

import httpx
import pytest

from verisys.evaluation import (DiscoveryError, LLMSelections, OpenAIClient,
    OpenAIConfig, normalize_architecture)
from verisys.models import ArchitectureIR


@pytest.fixture
def context():
    return normalize_architecture(ArchitectureIR(repository_root='not-read'))


def body(*, text='{"candidates":[]}', status='completed', refusal=False):
    content = {'type': 'refusal', 'refusal': 'declined'} if refusal else {
        'type': 'output_text', 'text': text, 'annotations': [], 'logprobs': []}
    return {'id': 'resp_fake', 'object': 'response', 'created_at': 0, 'status': status,
        'model': 'configured-model', 'error': None, 'incomplete_details': None,
        'output': [{'id': 'msg_fake', 'type': 'message', 'role': 'assistant', 'status': 'completed', 'content': [content]}],
        'usage': {'input_tokens': 20, 'output_tokens': 10, 'total_tokens': 30},
        'parallel_tool_calls': False, 'tools': [], 'tool_choice': 'none'}


def sdk_adapter(handler):
    openai = pytest.importorskip('openai')
    sdk = openai.OpenAI(api_key='fake-test-key', max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    return OpenAIClient(OpenAIConfig(model='configured-model'), sdk_client=sdk), sdk


def test_current_sdk_schema_constrained_request(context):
    requests = []
    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=body(), headers={'x-request-id': 'request-fake'})
    adapter, sdk = sdk_adapter(handler)
    try:
        response = adapter.generate(instructions='trusted instruction', structured_input=context, response_schema=LLMSelections)
    finally:
        sdk.close()
    assert response.payload == {'candidates': []}
    assert response.request_id == 'request-fake'
    assert (response.input_tokens, response.output_tokens) == (20, 10)
    request = requests[0]
    assert request['model'] == 'configured-model'
    assert request['tools'] == [] and request['store'] is False
    assert request['truncation'] == 'disabled'
    assert 'temperature' not in request
    assert request['input'][0] == {'role': 'developer', 'content': 'trusted instruction'}
    assert json.loads(request['input'][1]['content']) == context.model_dump(mode='json')
    schema = request['text']['format']
    assert schema['type'] == 'json_schema' and schema['strict'] is True
    assert schema['schema']['additionalProperties'] is False
    assert schema['schema']['$defs']['LLMSelection']['additionalProperties'] is False


@pytest.mark.parametrize('response_body,status', [(body(refusal=True), 'REFUSED'),
    (body(status='incomplete'), 'INCOMPLETE'),
    (body(status='incomplete', text='{\"candidates\":['), 'INCOMPLETE'),
    ({**body(), 'output': []}, 'INVALID')])
def test_sdk_response_statuses(context, response_body, status):
    adapter, sdk = sdk_adapter(lambda request: httpx.Response(200, json=response_body))
    try:
        assert adapter.generate(instructions='trusted', structured_input=context, response_schema=LLMSelections).status == status
    finally:
        sdk.close()


@pytest.mark.parametrize('text', ['not JSON', '{"candidates":[],"verdict":"VERIFIED"}'])
def test_invalid_sdk_structured_result(context, text):
    adapter, sdk = sdk_adapter(lambda request: httpx.Response(200, json=body(text=text)))
    try:
        with pytest.raises(DiscoveryError, match='invalid_structured_output'):
            adapter.generate(instructions='trusted', structured_input=context, response_schema=LLMSelections)
    finally:
        sdk.close()


@pytest.mark.parametrize('timeout,code', [(True, 'provider_timeout'), (False, 'provider_unavailable')])
def test_sdk_transport_failures(context, timeout, code):
    def handler(request):
        if timeout:
            raise httpx.ReadTimeout('sensitive exception', request=request)
        return httpx.Response(503, json={'error': {'message': 'sensitive provider text', 'type': 'server_error'}})
    adapter, sdk = sdk_adapter(handler)
    try:
        with pytest.raises(DiscoveryError, match=code) as caught:
            adapter.generate(instructions='trusted', structured_input=context, response_schema=LLMSelections)
        assert 'sensitive' not in str(caught.value)
    finally:
        sdk.close()


def test_missing_key_is_controlled_without_sdk_or_network(context, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(DiscoveryError, match='configuration_missing_api_key'):
        OpenAIClient(OpenAIConfig(model='configured')).generate(
            instructions='trusted', structured_input=context, response_schema=LLMSelections)


def test_configuration_masks_key_and_requires_model():
    from pydantic import ValidationError
    config = OpenAIConfig(model='configured', api_key='fake-test-key')
    assert 'fake-test-key' not in repr(config) + config.model_dump_json()
    with pytest.raises(ValidationError):
        OpenAIConfig()
