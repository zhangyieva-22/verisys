"""Static requests/httpx timeout observations; fixtures are never imported or executed."""
import pytest

from verisys.repository.discovery import DiscoveryLimits
from verisys.verification import verify_http_timeout_coverage, verify_timeout_coverage
from verisys.verification.registry import get_verifier


def run(tmp_path, source):
    (tmp_path / "app.py").write_text(source)
    return verify_http_timeout_coverage(tmp_path)


def calls(result):
    return [item.observed_value for item in result.evidence if item.observed_value["kind"] == "call"]


def single(tmp_path, source):
    result = run(tmp_path, source)
    [observed] = calls(result)
    return observed, result


@pytest.mark.parametrize("call,status,reason,source", [
    ("requests.get('u', timeout=5)", "CONFIGURED", "positive_numeric_literal", "call"),
    ("requests.get('u', timeout=(3.05, 27))", "CONFIGURED", "positive_timeout_literals", "call"),
    ("requests.get('u')", "MISSING", "requests_has_no_default_timeout", None),
    ("requests.get('u', timeout=None)", "MISSING", "timeout_disabled", None),
    ("requests.get('u', timeout=(3, None))", "MISSING", "timeout_disabled", None),
    ("requests.get('u', timeout=(3, None, 1))", "MISSING", "invalid_timeout_literal", None),
    ("requests.get('u', timeout=0)", "MISSING", "invalid_timeout_literal", None),
    ("requests.get('u', timeout=-1)", "MISSING", "invalid_timeout_literal", None),
    ("requests.get('u', timeout=True)", "MISSING", "invalid_timeout_literal", None),
    ("requests.get('u', timeout='5')", "MISSING", "invalid_timeout_literal", None),
    ("requests.get('u', timeout=(None, limit))", "MISSING", "timeout_disabled", None),
    ("requests.get('u', timeout=limit)", "UNKNOWN", "nonliteral_timeout", None),
    ("requests.get('u', timeout=(3, limit))", "UNKNOWN", "nonliteral_timeout", None),
    ("requests.get('u', **options)", "UNKNOWN", "expanded_keywords", None),
])
def test_requests_module_calls(tmp_path, call, status, reason, source):
    observed, _ = single(tmp_path, f"import requests\nlimit = 3\noptions = {{}}\n{call}\n")
    assert (observed["timeout_status"], observed["reason"], observed.get("timeout_source")) == (status, reason, source)
    assert observed["service"] == "Outbound HTTP" and observed["client_library"] == "requests"


@pytest.mark.parametrize("call,status,reason,source", [
    ("httpx.get('u')", "CONFIGURED", "httpx_default_timeout", "library_default"),
    ("httpx.get('u', timeout=2.5)", "CONFIGURED", "positive_numeric_literal", "call"),
    ("httpx.get('u', timeout=httpx.Timeout(5.0, connect=2.0))", "CONFIGURED", "positive_timeout_object", "call"),
    ("httpx.get('u', timeout=httpx.Timeout(5.0, connect=None))", "MISSING", "timeout_disabled", None),
    ("httpx.get('u', timeout=httpx.Timeout(None))", "MISSING", "timeout_disabled", None),
    ("httpx.get('u', timeout=httpx.Timeout(**cfg))", "UNKNOWN", "unsupported_timeout_object", None),
    ("httpx.get('u', timeout=(1, 2, 3, 4))", "CONFIGURED", "positive_timeout_literals", "call"),
    ("httpx.get('u', timeout=None)", "MISSING", "timeout_disabled", None),
    ("httpx.get('u', timeout=limit)", "UNKNOWN", "nonliteral_timeout", None),
])
def test_httpx_module_calls(tmp_path, call, status, reason, source):
    observed, _ = single(tmp_path, f"import httpx\nlimit = 3\ncfg = {{}}\n{call}\n")
    assert (observed["timeout_status"], observed["reason"], observed.get("timeout_source")) == (status, reason, source)


@pytest.mark.parametrize("constructor,call,status,reason,source", [
    ("httpx.Client()", "c.get('u')", "CONFIGURED", "httpx_default_timeout", "library_default"),
    ("httpx.Client(timeout=10)", "c.get('u')", "CONFIGURED", "client_timeout_configured", "client"),
    ("httpx.Client(timeout=None)", "c.get('u')", "MISSING", "client_timeout_disabled", None),
    ("httpx.Client(timeout=None)", "c.get('u', timeout=3)", "CONFIGURED", "positive_numeric_literal", "call"),
    ("httpx.Client(timeout=10)", "c.get('u', timeout=None)", "MISSING", "timeout_disabled", None),
    ("httpx.Client(timeout=limit)", "c.get('u')", "UNKNOWN", "client_nonliteral_timeout", None),
    ("httpx.Client(**cfg)", "c.get('u')", "UNKNOWN", "client_timeout_unresolved", None),
])
def test_httpx_client_inheritance(tmp_path, constructor, call, status, reason, source):
    observed, _ = single(tmp_path, f"import httpx\nlimit = 3\ncfg = {{}}\nwith {constructor} as c:\n    {call}\n")
    assert (observed["timeout_status"], observed["reason"], observed.get("timeout_source")) == (status, reason, source)


def test_async_httpx_client(tmp_path):
    observed, _ = single(tmp_path, '''import httpx
async def fetch():
    async with httpx.AsyncClient(timeout=None) as client:
        return await client.post("u")
''')
    assert (observed["timeout_status"], observed["operation"]) == ("MISSING", "post")


def test_requests_session_has_no_timeout_setting(tmp_path):
    observed, _ = single(tmp_path, "import requests\ns = requests.Session()\ns.get('u')\n")
    assert (observed["timeout_status"], observed["reason"]) == ("MISSING", "requests_has_no_default_timeout")


def test_mounted_session_is_unknown_even_when_mounted_later(tmp_path):
    observed, _ = single(tmp_path, '''import requests
s = requests.Session()
def fetch():
    return s.get("u")
s.mount("https://", TimeoutAdapter())
''')
    assert (observed["timeout_status"], observed["reason"]) == ("UNKNOWN", "custom_adapter_may_set_timeout")


def test_mount_on_another_session_does_not_hide_missing_timeout(tmp_path):
    observed, _ = single(tmp_path, '''import requests
a = requests.Session()
b = requests.Session()
b.mount("https://", TimeoutAdapter())
a.get("u")
''')
    assert observed["timeout_status"] == "MISSING"


def test_conditionally_constructed_clients_are_not_merged(tmp_path):
    result = run(tmp_path, '''import httpx
if flag:
    c = httpx.Client(timeout=None)
else:
    c = httpx.Client(timeout=None)
c.get("u")
''')
    # The analyzer keeps the common binding; the verifier cannot pick one constructor.
    assert [(item["timeout_status"], item["reason"]) for item in calls(result)] == [("UNKNOWN", "call_identity_unresolved")]


def test_verdicts_end_to_end(tmp_path):
    (tmp_path / "ok").mkdir()
    verified = run(tmp_path / "ok", "import requests\nimport httpx\nrequests.get('u', timeout=5)\nhttpx.get('u')\n")
    assert verified.verdict.status == "VERIFIED"
    assert verified.verdict.observed["coverage_percent"] == 100.0
    (tmp_path / "bad").mkdir()
    violated = run(tmp_path / "bad", "import requests\nrequests.get('u', timeout=5)\nrequests.post('u')\n")
    assert violated.verdict.status == "VIOLATED"
    assert violated.verdict.observed["missing"] == 1
    (tmp_path / "unknown").mkdir()
    unknown = run(tmp_path / "unknown", "import requests\nlimit = 3\nrequests.get('u', timeout=limit)\n")
    assert unknown.verdict.status == "NOT_VERIFIABLE"


def test_no_http_calls_is_not_applicable_without_verdict(tmp_path):
    result = run(tmp_path, "import httpx\n")
    assert result.verdict is None and result.evaluation.applicability == "NOT_APPLICABLE"
    assert result.execution_status == "NOT_RUN"


def test_policies_do_not_cross(tmp_path):
    (tmp_path / "app.py").write_text('''import requests
from openai import OpenAI
client = OpenAI()
client.responses.create(model="m", input="x", timeout=30)
requests.get("u")
''')
    http = verify_http_timeout_coverage(tmp_path)
    openai = verify_timeout_coverage(tmp_path)
    assert [item["client_library"] for item in calls(http)] == ["requests"]
    assert [item["client_library"] for item in calls(openai)] == ["openai"]
    assert http.verdict.status == "VIOLATED" and openai.verdict.status == "VERIFIED"
    assert "openai: timeout semantics outside this requests/httpx grammar." in http.limitations
    assert "requests: timeout semantics outside this OpenAI per-call grammar." in openai.limitations
    assert {item.tool for item in http.evidence} == {"python-static-http-timeout-v1"}


def test_source_changes_after_analysis_are_unknown(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text("import requests\nrequests.get('u')\n")
    import verisys.verification.static_timeouts as shared
    real = shared.read_python_source
    monkeypatch.setattr(shared, "read_python_source", lambda *a, **k: real(*a, **k) + b"\n# changed\n")
    result = verify_http_timeout_coverage(tmp_path)
    [observed] = calls(result)
    assert (observed["timeout_status"], observed["reason"]) == ("UNKNOWN", "source_changed")
    assert result.verdict.status == "NOT_VERIFIABLE"


def test_truncated_scope_cannot_verify(tmp_path):
    (tmp_path / "app.py").write_text("import requests\nrequests.get('u', timeout=5)\n")
    (tmp_path / "b.py").write_text("pass\n")
    result = verify_http_timeout_coverage(tmp_path, limits=DiscoveryLimits(max_files=1))
    assert result.verdict.status == "NOT_VERIFIABLE"


def test_registered_verifier():
    assert get_verifier("http-client-timeout-coverage-v1") is verify_http_timeout_coverage

@pytest.mark.parametrize('argument,status', [('timeout=90','VERIFIED'), ('','VIOLATED'), ('timeout=value','NOT_VERIFIABLE')])
def test_requests_in_try_has_real_observations(tmp_path, argument, status):
    result=run(tmp_path, f'import requests\ntry:\n    requests.post("https://example.invalid", {argument})\nexcept Exception:\n    pass\n')
    assert result.verdict.status == status
    assert len(calls(result)) == 1
    assert result.evidence[0].source_location.line == 3


def test_exception_alias_cannot_be_mistaken_for_http_library(tmp_path):
    result=run(tmp_path, 'import requests\ntry:\n    pass\nexcept Exception as requests:\n    requests.get("x",timeout=5)\n')
    assert calls(result) == []
    assert result.verdict.status == 'NOT_VERIFIABLE'
