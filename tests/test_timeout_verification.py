"""Real static source observations; repository fixtures are never imported."""
import hashlib
from pathlib import Path

import pytest

from verisys.architecture import analyze_architecture
from verisys.models import Evidence, VerificationRun
from verisys.repository import discover_repository
from verisys.repository.discovery import DiscoveryLimits
from verisys.verification import verify_timeout_coverage
from verisys.verification.judge import judge_timeouts
from verisys.verification.timeout import inspect_timeouts

ROOT = Path(__file__).resolve().parents[1]


def repository(tmp_path, calls, prefix='from openai import OpenAI\nclient = OpenAI()\n'):
    (tmp_path / 'app.py').write_text(prefix + '\n'.join(calls) + '\n')
    return tmp_path


def observations(run):
    return [item for item in run.evidence if item.observed_value['kind'] == 'call']


@pytest.mark.parametrize('arguments,status', [
    ('timeout=30', 'VERIFIED'), ('timeout=0.5', 'VERIFIED'), ('timeout=+10', 'VERIFIED'),
    ('', 'VIOLATED'), ('timeout=None', 'VIOLATED'), ('timeout=0', 'VIOLATED'),
    ('timeout=-1', 'VIOLATED'), ('timeout=True', 'VIOLATED'), ('timeout=False', 'VIOLATED'),
    ('timeout="private-secret"', 'VIOLATED'), ('timeout=1e309', 'VIOLATED'),
    ('timeout=timeout_value', 'NOT_VERIFIABLE'), ('**request_options', 'NOT_VERIFIABLE'),
    ('timeout=30, **request_options', 'NOT_VERIFIABLE'), ('timeout=make_timeout()', 'NOT_VERIFIABLE'),
])
def test_policy_literals_and_ambiguity(tmp_path, arguments, status):
    root = repository(tmp_path, [f'client.responses.create({arguments})'])
    run = verify_timeout_coverage(root)
    assert run.verdict.status == status
    assert run.execution_status == 'COMPLETED'
    assert run.evaluation.applicability == 'APPLICABLE'
    assert run.verdict.observed['total'] == 1
    assert 'private-secret' not in run.model_dump_json()
    assert run.verdict.observed['unknown'] == (status == 'NOT_VERIFIABLE')


def test_golden_exact_sources_counts_and_serialization():
    run = verify_timeout_coverage(ROOT / 'examples/timeout-coverage')
    assert run.verdict.status == 'VIOLATED'
    assert run.verdict.observed == dict(configured=2, missing=1, unknown=0, total=3,
                                      coverage_complete=True, coverage_percent=66.7)
    calls = observations(run)
    assert [(item.source_location.file, item.source_location.line, item.source_location.column) for item in calls] == [
        ('app.py', 4, 0), ('app.py', 5, 0), ('app.py', 6, 0)]
    assert [item.observed_value['operation'] for item in calls] == ['responses.create', 'embeddings.create', 'responses.create']
    assert set(run.verdict.evidence_ids) == {item.id for item in run.evidence}
    assert VerificationRun.model_validate_json(run.model_dump_json()) == run


def test_bundled_unknown():
    run = verify_timeout_coverage(ROOT / 'examples/timeout-unknown')
    assert run.verdict.status == 'NOT_VERIFIABLE'
    assert run.verdict.observed == dict(configured=0, missing=0, unknown=1, total=1,
                                      coverage_complete=False, coverage_percent=None)


def test_all_configured_and_determinism(tmp_path):
    root = repository(tmp_path, ['client.responses.create(timeout=30)'] * 3)
    first, second = verify_timeout_coverage(root), verify_timeout_coverage(root)
    assert first.verdict.status == 'VERIFIED'
    assert first.verdict.observed['configured'] == 3
    assert first.model_dump_json() == second.model_dump_json()
    assert first.trace == second.trace


@pytest.mark.parametrize('calls,status,counts', [
    (['timeout=30', '', 'timeout=x'], 'VIOLATED', (1, 1, 1)),
    (['timeout=30', 'timeout=x'], 'NOT_VERIFIABLE', (1, 0, 1)),
])
def test_mixed_counts(tmp_path, calls, status, counts):
    run = verify_timeout_coverage(repository(tmp_path, [f'client.responses.create({arg})' for arg in calls]))
    assert run.verdict.status == status
    assert tuple(run.verdict.observed[key] for key in ['configured', 'missing', 'unknown']) == counts
    assert run.verdict.observed['coverage_percent'] is None
    assert not run.verdict.observed['coverage_complete']
    assert any('incomplete' in item for item in run.verdict.limitations)


def test_same_line_columns_aliases_and_client_inheritance(tmp_path):
    root = repository(tmp_path, ['client.responses.create(timeout=30); client.embeddings.create()'],
                      'from openai import OpenAI as OAI\nclient = OAI(timeout=30)\n')
    run = verify_timeout_coverage(root)
    assert [(item.source_location.line, item.source_location.column) for item in observations(run)] == [(3, 0), (3, 37)]
    assert run.verdict.observed['configured'] == run.verdict.observed['missing'] == 1


@pytest.mark.parametrize('source', ['', 'import stripe\nstripe.Charge.create()\n',
                                  'from langchain_openai import ChatOpenAI\nclient=ChatOpenAI(timeout=30)\n'])
def test_no_applicable_calls_and_other_services(tmp_path, source):
    (tmp_path / 'app.py').write_text(source)
    run = verify_timeout_coverage(tmp_path)
    assert run.evaluation.applicability == 'NOT_APPLICABLE'
    assert run.execution_status == 'NOT_RUN'
    assert run.verdict is None
    assert not observations(run)
    if source:
        assert run.evidence[-1].observed_value['outside_grammar']
        assert any('outside this' in item for item in run.limitations)


def baseline(root):
    discovery = discover_repository(root)
    hashes = {}
    architecture = analyze_architecture(discovery, on_source=lambda path, data: hashes.update({path: hashlib.sha256(data).hexdigest()}))
    return discovery, architecture, hashes


@pytest.mark.parametrize('replacement', ['client.responses.create(timeout=20)\n', 'bad syntax !'])
def test_changed_source_never_reuses_old_architecture_as_conclusive(tmp_path, replacement):
    repository(tmp_path, ['client.responses.create(timeout=30)'])
    discovery, architecture, hashes = baseline(tmp_path)
    (tmp_path / 'app.py').write_text(replacement)
    evidence = inspect_timeouts(discovery, architecture, hashes)
    judgment = judge_timeouts(evidence)
    assert judgment.verdict.status == 'NOT_VERIFIABLE'
    assert evidence[0].observed_value['reason'] == 'source_changed'
    assert judgment.counts.unknown == 1


def test_unsafe_symlink_replacement(tmp_path):
    repository(tmp_path, ['client.responses.create(timeout=30)'])
    discovery, architecture, hashes = baseline(tmp_path)
    external = tmp_path.parent / (tmp_path.name + '-outside.py')
    external.write_text('raise RuntimeError("must not execute")')
    (tmp_path / 'app.py').unlink()
    (tmp_path / 'app.py').symlink_to(external)
    evidence = inspect_timeouts(discovery, architecture, hashes)
    assert evidence[0].observed_value['reason'] == 'outside_root'
    assert evidence[0].observed_value['source_sha256'] is None
    assert judge_timeouts(evidence).verdict.status == 'NOT_VERIFIABLE'


def test_parse_failures_and_incomplete_scope(tmp_path):
    repository(tmp_path, ['client.responses.create(timeout=30)'])
    (tmp_path / 'broken.py').write_text('not valid python !')
    run = verify_timeout_coverage(tmp_path)
    assert run.verdict.status == 'NOT_VERIFIABLE'
    assert run.verdict.observed['configured'] == 1
    assert run.evidence[-1].observed_value['scope_complete'] is False
    assert any('parse failed' in item for item in run.limitations)


def test_empty_but_truncated_scope_is_unknown(tmp_path):
    repository(tmp_path, ['client.responses.create(timeout=30)'])
    run = verify_timeout_coverage(tmp_path, limits=DiscoveryLimits(max_files=0))
    assert run.evaluation.applicability == 'UNKNOWN'
    assert run.verdict.status == 'NOT_VERIFIABLE'
    assert run.verdict.observed['coverage_percent'] is None


def test_discovery_limits_reused_before_ingestion(tmp_path, monkeypatch):
    root = repository(tmp_path, ['client.responses.create(timeout=30)'])
    discovery, architecture, hashes = baseline(root)
    import verisys.verification.static_timeouts as tool
    real = tool.read_python_source
    limits_seen = []
    def reader(*args, **kwargs):
        limits_seen.append(kwargs)
        return real(*args, **kwargs)
    monkeypatch.setattr(tool, 'read_python_source', reader)
    inspect_timeouts(discovery, architecture, hashes)
    assert limits_seen == [dict(max_file_bytes=discovery.limits.max_file_bytes,
                               remaining_bytes=discovery.limits.max_total_bytes)]


def test_no_execution_measurements_or_hidden_reasoning(tmp_path):
    marker = tmp_path / 'executed'
    root = repository(tmp_path, ['client.responses.create(timeout=30)'],
        f'from openai import OpenAI\nopen({str(marker)!r}, "w").write("ran")\nclient=OpenAI()\n')
    run = verify_timeout_coverage(root)
    assert not marker.exists()
    assert all(item.type == 'STATIC_ANALYSIS' and item.unit is None for item in run.evidence)
    assert {item.type.value for item in run.trace} == {'DECISION', 'ACTION', 'OBSERVATION', 'EVIDENCE', 'VERDICT'}
    assert all('chain_of_thought' not in item.model_dump() for item in run.trace)
    assert all(set(item.related_evidence_ids).issubset({e.id for e in run.evidence}) for item in run.trace)


def test_observer_keeps_architecture_serialization_unchanged(tmp_path):
    repository(tmp_path, ['client.responses.create(timeout=30)'])
    discovery = discover_repository(tmp_path)
    ordinary = analyze_architecture(discovery)
    observed = analyze_architecture(discovery, on_source=lambda path, data: None)
    run = verify_timeout_coverage(tmp_path)
    assert ordinary.model_dump_json() == observed.model_dump_json() == run.architecture.model_dump_json()
    assert set(ordinary.external_services[0].model_dump()) == {'name', 'client_library', 'call_sites', 'source_locations'}


def test_judge_rejects_manifest_mismatch(tmp_path):
    run = verify_timeout_coverage(repository(tmp_path, ['client.responses.create(timeout=30)']))
    with pytest.raises(ValueError, match='scope manifest'):
        judge_timeouts(run.evidence[1:])
    with pytest.raises(ValueError, match='duplicate'):
        judge_timeouts([*run.evidence, run.evidence[0]])
    scope = run.evidence[-1]
    data = scope.model_dump()
    data['observed_value']['call_evidence_ids'] = ['invented']
    with pytest.raises(ValueError, match='scope manifest'):
        judge_timeouts([run.evidence[0], Evidence.model_validate(data)])


def test_changes_in_previously_call_free_files_prevent_verified(tmp_path):
    repository(tmp_path, ['client.responses.create(timeout=30)'])
    other = tmp_path / 'other.py'
    other.write_text('value = 1\n')
    discovery, architecture, hashes = baseline(tmp_path)
    other.write_text('from openai import OpenAI\nclient=OpenAI()\nclient.responses.create()\n')
    evidence = inspect_timeouts(discovery, architecture, hashes)
    judgment = judge_timeouts(evidence)
    assert judgment.verdict.status == 'NOT_VERIFIABLE'
    assert judgment.counts.configured == 1
    assert evidence[-1].observed_value['scope_complete'] is False


def test_aggregate_budget_prevents_reread_before_ingestion(tmp_path, monkeypatch):
    repository(tmp_path, ['client.responses.create(timeout=30)'])
    discovery, architecture, hashes = baseline(tmp_path)
    data = discovery.model_dump()
    data['limits'] = DiscoveryLimits(max_total_bytes=0)
    discovery = type(discovery).model_validate(data)
    import verisys.repository.safe_read as reader
    def forbidden(*args):
        pytest.fail('exhausted budget must not read bytes')
    monkeypatch.setattr(reader.os, 'read', forbidden)
    evidence = inspect_timeouts(discovery, architecture, hashes)
    assert evidence[0].observed_value['reason'] == 'aggregate_budget_exhausted'
    assert judge_timeouts(evidence).verdict.status == 'NOT_VERIFIABLE'


def test_per_file_size_rejection_is_distinct(tmp_path):
    repository(tmp_path, ['client.responses.create(timeout=30)'])
    discovery, architecture, hashes = baseline(tmp_path)
    data = discovery.model_dump()
    data['limits'] = DiscoveryLimits(max_file_bytes=0)
    evidence = inspect_timeouts(type(discovery).model_validate(data), architecture, hashes)
    assert evidence[0].observed_value['reason'] == 'file_too_large'


def test_unmatched_coordinate_is_unknown(tmp_path):
    repository(tmp_path, ['client.responses.create(timeout=30)'])
    discovery, architecture, hashes = baseline(tmp_path)
    from verisys.models import SourceLocation
    architecture.external_services[0].call_sites = [SourceLocation(file='app.py', line=3, column=1)]
    evidence = inspect_timeouts(discovery, architecture, hashes)
    assert evidence[0].observed_value['reason'] == 'call_identity_unresolved'
    assert judge_timeouts(evidence).verdict.status == 'NOT_VERIFIABLE'


@pytest.mark.parametrize('prefix,call', [
    ('import openai as ai\n', 'ai.responses.create(timeout=30)'),
    ('from openai import AsyncOpenAI as A\nclient=A()\n', 'client.chat.completions.create(timeout=30)'),
    ('from openai import OpenAI\nfirst=OpenAI()\nclient=first\n', 'client.embeddings.create(timeout=30)'),
])
def test_supported_import_and_client_aliases(tmp_path, prefix, call):
    run = verify_timeout_coverage(repository(tmp_path, [call], prefix))
    assert run.verdict.status == 'VERIFIED'
    assert len(observations(run)) == 1


def test_other_services_are_not_generically_judged(tmp_path):
    repository(tmp_path, ['client.responses.create(timeout=30)',
                          'stripe.Charge.create(timeout=0)', 'twilio_client.messages.create()'],
               'from openai import OpenAI\nimport stripe\nfrom twilio.rest import Client\nclient=OpenAI()\ntwilio_client=Client()\n')
    run = verify_timeout_coverage(tmp_path)
    assert run.verdict.status == 'VERIFIED'
    assert run.verdict.observed['total'] == 1
    assert run.evidence[-1].observed_value['outside_grammar'] == ['stripe', 'twilio']


def test_evidence_snapshot_and_judge_without_filesystem(tmp_path, monkeypatch):
    run = verify_timeout_coverage(repository(tmp_path, ['client.responses.create(timeout=30)']))
    evidence = observations(run)[0]
    altered = evidence.observed_value
    altered['timeout_status'] = 'MISSING'
    assert evidence.observed_value['timeout_status'] == 'CONFIGURED'
    import verisys.repository.safe_read as reader
    def forbidden(*args, **kwargs):
        pytest.fail('judge must not read source')
    monkeypatch.setattr(reader.os, 'read', forbidden)
    assert judge_timeouts(run.evidence).verdict == run.verdict
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        evidence.tool = 'changed'

@pytest.mark.parametrize('arguments,status', [('timeout=10', 'VERIFIED'), ('', 'VIOLATED'), ('timeout=value', 'NOT_VERIFIABLE')])
def test_try_call_policy(tmp_path, arguments, status):
    repository(tmp_path, [f'try:\n    client.responses.create({arguments})\nexcept Exception:\n    pass'])
    result = verify_timeout_coverage(tmp_path)
    assert result.verdict.status == status
    assert len(observations(result)) == 1
    assert observations(result)[0].source_location.line == 4


def test_router_mount_does_not_invalidate_timeout_scope(tmp_path):
    repository(tmp_path, ['client.responses.create(timeout=10)',
                         'from fastapi import FastAPI, APIRouter', 'app=FastAPI()',
                         'router=APIRouter()', 'app.include_router(router)'])
    result = verify_timeout_coverage(tmp_path)
    assert result.verdict.status == 'VERIFIED'
    assert any('Router mounting' in item for item in result.limitations)


def test_try_rebinding_does_not_produce_false_calls(tmp_path):
    repository(tmp_path, ['try:\n    client=unrelated\n    client.responses.create(timeout=10)\nexcept Exception:\n    client.responses.create(timeout=10)',
                         'client.responses.create(timeout=10)'])
    result = verify_timeout_coverage(tmp_path)
    assert observations(result) == []
    assert result.verdict.status == 'NOT_VERIFIABLE'


def test_parse_failure_still_blocks_complete_scope(tmp_path):
    repository(tmp_path, ['client.responses.create(timeout=10)'])
    (tmp_path / 'broken.py').write_text('def broken(')
    assert verify_timeout_coverage(tmp_path).verdict.status == 'NOT_VERIFIABLE'
