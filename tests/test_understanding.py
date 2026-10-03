"""Understanding uses fake clients only; fixtures are never imported or executed."""
import json

import pytest

from verisys.architecture import analyze_architecture
from verisys.evaluation import DiscoveryError, StructuredGenerationResult
from verisys.repository import discover_repository
from verisys.understanding import SelectionLimits, select_excerpts, understand_repository, validate_claims
from verisys.understanding.contracts import ExcerptKind, ExcerptLine, SourceExcerpt, UnderstandingInput

APP = '''from fastapi import FastAPI
import requests
app = FastAPI()

@app.post("/orders")
def create_order(order: dict):
    """Create an order and charge the customer."""
    response = requests.post("https://payments.example.com/charge", json=order)
    return {"status": "created", "charge": response.json()}
'''


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def repo(tmp_path):
    write(tmp_path, "README.md", "# Shop\nCustomers place orders and pay by card.\n")
    write(tmp_path, "docs/design.md", "Orders are charged through the payments service.\n")
    write(tmp_path, "CHANGELOG.md", "v1\n")
    write(tmp_path, "app/main.py", APP)
    write(tmp_path, "app/util.py", "def helper():\n    return 1\n")
    write(tmp_path, "tests/test_orders.py", "import pytest\n\ndef test_create_order_charges_card():\n    pass\n\nasync def test_rejects_empty_order():\n    pass\n")
    write(tmp_path, ".env", "OPENAI_API_KEY=sk-should-never-be-read-0000000000\n")
    return tmp_path


def analyzed(root):
    discovery = discover_repository(root)
    return discovery, analyze_architecture(discovery)


class FakeClient:
    provider, model = "fake", "fixture-model"

    def __init__(self, payload=None, status="COMPLETED", error=None):
        self.payload, self.status, self.error, self.calls = payload, status, error, []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return StructuredGenerationResult(payload=self.payload, status=self.status)


def excerpt_ids(client):
    return {item.id: item for item in client.calls[0]["structured_input"].excerpts}


def test_selection_priority_and_kinds(repo):
    excerpts, truncated, limitations = select_excerpts(*analyzed(repo))
    assert [(e.id, e.path, e.kind) for e in excerpts] == [
        ("E1", "README.md", ExcerptKind.README),
        ("E2", "docs/design.md", ExcerptKind.DOCUMENT),
        ("E3", "app/main.py", ExcerptKind.ROUTE_SOURCE),
        ("E4", "tests/test_orders.py", ExcerptKind.TEST_INDEX),
    ]
    assert not truncated and limitations == []
    assert [line.number for line in excerpts[3].lines] == [3, 6]
    assert excerpts[2].lines[0].number == 2 and excerpts[2].lines[-1].text.strip().startswith("return")
    assert select_excerpts(*analyzed(repo))[0] == excerpts


def test_env_files_and_undiscovered_paths_are_never_sent(repo):
    excerpts, _, _ = select_excerpts(*analyzed(repo))
    text = json.dumps([e.model_dump(mode="json") for e in excerpts])
    assert ".env" not in text and "sk-should-never" not in text and "CHANGELOG" not in text


def test_entry_points_and_integrations_without_routes(tmp_path):
    write(tmp_path, "cli.py", "import sys\nprint(sys.argv)\n")
    write(tmp_path, "client.py", "import httpx\n\ndef fetch():\n    return httpx.get('https://x')\n")
    kinds = {e.path: e.kind for e in select_excerpts(*analyzed(tmp_path))[0]}
    assert kinds == {"client.py": ExcerptKind.INTEGRATION_SOURCE, "cli.py": ExcerptKind.ENTRY_POINT}


@pytest.mark.parametrize("line,leak", [
    ('OPENAI_API_KEY = "sk-proj-abcdefghijklmnop1234"', "sk-proj-abcdefghijklmnop1234"),
    ('password = "hunter2hunter2"', "hunter2hunter2"),
    ('headers = {"Authorization": "Bearer abcdefghijklmnopqrstuvwxyz123"}', "abcdefghijklmnopqrstuvwxyz123"),
    ('AWS = "AKIAABCDEFGHIJKLMNOP"', "AKIAABCDEFGHIJKLMNOP"),
])
def test_likely_secrets_are_redacted(tmp_path, line, leak):
    write(tmp_path, "main.py", f"{line}\n")
    excerpts, _, limitations = select_excerpts(*analyzed(tmp_path))
    text = excerpts[0].numbered_text()
    assert leak not in text and "[REDACTED]" in text
    assert any("redacted" in item for item in limitations)


def test_private_key_blocks_are_redacted(tmp_path):
    write(tmp_path, "README.md", "key:\n-----BEGIN RSA PRIVATE KEY-----\nMIIEabc\n-----END RSA PRIVATE KEY-----\nafter\n")
    text = select_excerpts(*analyzed(tmp_path))[0][0].numbered_text()
    assert "MIIEabc" not in text and "5| after" in text


def test_budget_truncation_is_visible(repo):
    excerpts, truncated, limitations = select_excerpts(*analyzed(repo), SelectionLimits(max_total_lines=4))
    assert truncated and sum(len(e.lines) for e in excerpts) == 4
    assert any("budget" in item for item in limitations)


def claim(eid, start, end, quote, **extra):
    return {"title": extra.pop("title", "Place orders"), "description": "Customers can create orders.",
            "citations": [{"excerpt_id": eid, "start_line": start, "end_line": end, "quote": quote}], **extra}


def test_valid_claims_keep_checked_citations(repo):
    payload = {"functional_requirements": [claim("E3", 5, 6, "@app.post(\"/orders\") def create_order(order: dict):")],
               "risks": [claim("E3", 8, 8, "requests.post(\"https://payments.example.com/charge\", json=order)",
                               title="Payment call without timeout", category="reliability", severity="high")]}
    client = FakeClient(payload)
    discovery, architecture = analyzed(repo)
    result = understand_repository(discovery, architecture, architecture_id="a" * 64, repository="shop", client=client)
    [requirement], [risk] = result.functional_requirements, result.risks
    assert requirement.status == risk.status == "INFERRED_NOT_VERIFIED"
    assert (requirement.citations[0].path, requirement.citations[0].start_line) == ("app/main.py", 5)
    assert (risk.category, risk.severity) == ("reliability", "high")
    assert result.rejected_claims == result.rejected_citations == 0
    assert any("not verified" in item for item in result.limitations)
    sent = client.calls[0]
    assert isinstance(sent["structured_input"], UnderstandingInput)
    assert "UNTRUSTED DATA" in sent["instructions"]
    assert sent["response_schema"].model_json_schema()["$defs"]["Citation"]["properties"]["excerpt_id"]["enum"] == ["E1", "E2", "E3", "E4"]


@pytest.mark.parametrize("citation", [
    {"excerpt_id": "E3", "start_line": 5, "end_line": 5, "quote": "def delete_everything()"},  # quote not in lines
    {"excerpt_id": "E3", "start_line": 1, "end_line": 1, "quote": "fastapi"},  # line 1 was not sent
    {"excerpt_id": "E9", "start_line": 5, "end_line": 5, "quote": "orders"},  # unknown excerpt
    {"excerpt_id": "E3", "start_line": 6, "end_line": 5, "quote": "orders"},  # reversed range
    {"excerpt_id": "E4", "start_line": 3, "end_line": 6, "quote": "test_create_order"},  # gap in test index
    {"excerpt_id": "E3", "start_line": 5, "end_line": 5, "quote": "or"},  # too short
])
def test_invalid_citations_drop_the_claim(repo, citation):
    excerpts = select_excerpts(*analyzed(repo))[0]
    payload = {"functional_requirements": [{"title": "x", "description": "y", "citations": [citation]}], "risks": []}
    requirements, risks, rejected_claims, rejected_citations = validate_claims(payload, excerpts, "a" * 64)
    assert requirements == risks == [] and (rejected_claims, rejected_citations) == (1, 1)


def test_line_number_prefixes_and_whitespace_in_quotes_are_tolerated():
    excerpt = SourceExcerpt(id="E1", path="a.py", kind=ExcerptKind.ROUTE_SOURCE,
                            lines=(ExcerptLine(number=4, text="def   pay(amount):"), ExcerptLine(number=5, text="    return charge(amount)")))
    payload = {"functional_requirements": [claim("E1", 4, 5, "4| def pay(amount):\n5|     return charge(amount)")], "risks": []}
    [requirement], _, rejected, _ = validate_claims(payload, [excerpt], "a" * 64)
    assert requirement.citations[0].quote == "def pay(amount): return charge(amount)" and rejected == 0


def test_partial_citations_keep_claim_and_duplicates_are_dropped(repo):
    excerpts = select_excerpts(*analyzed(repo))[0]
    good = {"excerpt_id": "E1", "start_line": 2, "end_line": 2, "quote": "Customers place orders"}
    bad = {"excerpt_id": "E1", "start_line": 2, "end_line": 2, "quote": "invented"}
    payload = {"functional_requirements": [
        {"title": "Orders", "description": "d", "citations": [bad, good]},
        {"title": "orders", "description": "duplicate title", "citations": [good]},
        {"title": "", "description": "no title", "citations": [good]}], "risks": []}
    requirements, _, rejected_claims, rejected_citations = validate_claims(payload, excerpts, "a" * 64)
    assert [r.title for r in requirements] == ["Orders"] and len(requirements[0].citations) == 1
    assert (rejected_claims, rejected_citations) == (2, 1)


def test_invalid_risk_fields_drop_only_that_risk(repo):
    excerpts = select_excerpts(*analyzed(repo))[0]
    good = {"excerpt_id": "E1", "start_line": 2, "end_line": 2, "quote": "Customers place orders"}
    payload = {"functional_requirements": [], "risks": [
        {"title": "No category", "description": "d", "severity": "high", "citations": [good]},
        {"title": "Fine", "description": "d", "category": "security", "severity": "low", "citations": [good]}]}
    _, risks, rejected_claims, _ = validate_claims(payload, excerpts, "a" * 64)
    assert [risk.title for risk in risks] == ["Fine"] and rejected_claims == 1


@pytest.mark.parametrize("payload", [None, [], {"functional_requirements": "x", "risks": []}, {"risks": []}])
def test_malformed_payload_is_rejected(repo, payload):
    with pytest.raises(DiscoveryError, match="invalid_structured_output"):
        validate_claims(payload, select_excerpts(*analyzed(repo))[0], "a" * 64)


@pytest.mark.parametrize("status,code", [("REFUSED", "provider_refusal"), ("INCOMPLETE", "provider_incomplete"), ("INVALID", "invalid_structured_output")])
def test_provider_statuses(repo, status, code):
    with pytest.raises(DiscoveryError, match=code):
        understand_repository(*analyzed(repo), architecture_id="a" * 64, repository="shop", client=FakeClient(status=status))


def test_provider_exception_is_sanitized(repo):
    with pytest.raises(DiscoveryError, match="provider_unavailable"):
        understand_repository(*analyzed(repo), architecture_id="a" * 64, repository="shop",
                              client=FakeClient(error=RuntimeError("secret detail sk-abc")))


def test_nothing_to_send_makes_no_model_call(tmp_path):
    write(tmp_path, "data.json", "{}")
    client = FakeClient({"functional_requirements": [], "risks": []})
    result = understand_repository(*analyzed(tmp_path), architecture_id="a" * 64, repository="x", client=client)
    assert client.calls == [] and result.functional_requirements == result.risks == []
    assert any("no model call" in item for item in result.limitations)


def test_repository_code_is_never_executed(tmp_path):
    marker = tmp_path / "EXECUTED"
    write(tmp_path, "main.py", f"open({str(marker)!r}, 'w').write('x')\n")
    understand_repository(*analyzed(tmp_path), architecture_id="a" * 64, repository="x",
                          client=FakeClient({"functional_requirements": [], "risks": []}))
    assert not marker.exists()


def test_manifests_are_selected_after_documentation(repo):
    write(repo, "frontend/package.json", '{\n  "name": "shop-web",\n  "dependencies": {"next": "16"}\n}\n')
    write(repo, "Dockerfile", "FROM python:3.12\n")
    write(repo, "requirements.txt", "fastapi\nrequests\n")
    excerpts, _, _ = select_excerpts(*analyzed(repo))
    assert [(e.path, e.kind) for e in excerpts][:5] == [
        ("README.md", ExcerptKind.README), ("docs/design.md", ExcerptKind.DOCUMENT),
        ("Dockerfile", ExcerptKind.MANIFEST), ("requirements.txt", ExcerptKind.MANIFEST),
        ("frontend/package.json", ExcerptKind.MANIFEST)]
