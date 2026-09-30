"""Schema tests only; observations below are explicitly synthetic fixtures."""
import pytest
from pydantic import TypeAdapter, ValidationError

from verisys.models import (
    APIRoute, Applicability, ArchitectureIR, Dependency, EngineeringRequirement,
    EvaluationCandidate, Evidence, EvidenceType, ExecutionStatus, ExecutionSupport,
    ExternalService, SourceLocation, TraceEvent, TraceEventType, Verdict,
    VerdictStatus, VerificationMode, VerificationPlan, VerificationRun,
)


@pytest.fixture
def objects():
    location = SourceLocation(file="fixtures/client.py", line=12, column=0)
    architecture = ArchitectureIR(
        repository_root="fixtures/demo", languages=["Python"], frameworks=["FastAPI"],
        api_routes=[APIRoute(method="POST", path="/documents", handler="create", source_location=location)],
        external_services=[ExternalService(name="Example API", client_library="example", call_sites=[location])],
        dependencies=[Dependency(source_component="api", target_component="client", dependency_type="import", source_location=location)],
    )
    evaluation = EvaluationCandidate(
        id="timeout", name="Timeout Coverage", category="Reliability",
        applicability="APPLICABLE", priority="HIGH", reason="Synthetic fixture",
        verification_mode="STATIC", execution_support="SUPPORTED",
    )
    requirement = EngineeringRequirement(id="req", raw_requirement="All calls need timeouts.")
    plan = VerificationPlan(
        evaluation_id="timeout", claim=requirement.raw_requirement,
        verification_mode="STATIC", required_evidence=["call sites"],
        tool="fixture", acceptance_condition="protected == total",
    )
    evidence = Evidence(
        id="ev1", type="STATIC_ANALYSIS", source="synthetic fixture",
        claim="Timeout configured", observed_value=True, source_location=location,
        tool="fixture",
    )
    verdict = Verdict(
        status="VERIFIED", evaluation_id="timeout", evidence_ids=[evidence.id],
        expected=1, observed=1, summary="Synthetic fixture verdict",
    )
    trace = TraceEvent(
        id="t1", type="EVIDENCE", stage="collect", summary="Fixture supplied",
        related_evidence_ids=[evidence.id], metadata={"synthetic": True},
    )
    run = VerificationRun(
        id="run", architecture=architecture, evaluation=evaluation,
        requirement=requirement, plan=plan, execution_status="COMPLETED",
        evidence=[evidence], verdict=verdict, trace=[trace],
    )
    return [location, architecture, evaluation, requirement, plan, evidence, verdict, trace, run]


def test_all_models_construct(objects):
    assert len(objects) == 9
    run = objects[-1]
    assert run.architecture.api_routes[0].source_location.line == 12
    assert run.architecture.external_services[0].call_sites[0].column == 0
    assert run.evaluation.applicability is Applicability.APPLICABLE
    assert run.plan.verification_mode is VerificationMode.STATIC
    assert run.evidence[0].type is EvidenceType.STATIC_ANALYSIS


ENUMS = [VerdictStatus, Applicability, VerificationMode, ExecutionStatus,
         EvidenceType, TraceEventType, ExecutionSupport]


@pytest.mark.parametrize("enum", ENUMS)
def test_every_enum_value_and_invalid_values(enum):
    adapter = TypeAdapter(enum)
    for member in enum:
        assert adapter.validate_python(member.value) is member
    with pytest.raises(ValidationError):
        adapter.validate_python("INVALID")


@pytest.mark.parametrize("index,field,value", [
    (2, "applicability", "VERIFIED"), (2, "verification_mode", "PENDING"),
    (2, "execution_support", "COMPLETED"), (4, "verification_mode", "UNKNOWN"),
    (5, "type", "VERIFIED"), (6, "status", "FAILED"),
    (7, "type", "RUNTIME"), (8, "execution_status", "VIOLATED"),
])
def test_model_fields_reject_wrong_enum_values(objects, index, field, value):
    model = objects[index]
    data = model.model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        type(model).model_validate(data)


def test_all_default_containers_are_isolated(objects):
    # Check every default list/dict on the nine models, not just ArchitectureIR.
    for model in objects:
        required = {
            (field.validation_alias or name): (
                model.observed_value if name == "observation_json" else getattr(model, name)
            )
            for name, field in type(model).model_fields.items() if field.is_required()
        }
        if isinstance(model, Verdict):
            required["status"] = VerdictStatus.NOT_VERIFIABLE
        for name in ("evaluation_id", "requirement_id", "evaluation", "requirement"):
            if name in type(model).model_fields and getattr(model, name) is not None:
                required[name] = getattr(model, name)
        first = type(model)(**required)
        second = type(model)(**required)
        for name, field in type(model).model_fields.items():
            left, right = getattr(first, name), getattr(second, name)
            if field.default_factory is not None and isinstance(left, (list, dict)):
                assert left is not right
                if isinstance(left, list):
                    left.append("test mutation")
                else:
                    left["test"] = True
                assert not right


@pytest.mark.parametrize("raw", ["  Payment must be safe to retry.\n", "Unstructured claim"])
def test_requirement_preserves_raw_text(raw):
    requirement = EngineeringRequirement(id="r", raw_requirement=raw)
    assert requirement.raw_requirement == raw
    assert requirement.target is None
    assert requirement.model_dump()["raw_requirement"] == raw
    with pytest.raises(ValidationError):
        requirement.raw_requirement = "replacement"


def test_requirement_requires_original_text():
    with pytest.raises(ValidationError):
        EngineeringRequirement(id="r", metric="p95", threshold=500)


def test_verdict_references_evidence_ids(objects):
    run = objects[-1]
    assert run.verdict.evidence_ids == (run.evidence[0].id,)
    assert run.model_dump(mode="json")["verdict"]["evidence_ids"] == ["ev1"]


@pytest.mark.parametrize("status", list(ExecutionStatus))
def test_execution_status_does_not_change_verdict(objects, status):
    run = objects[-1]
    run.execution_status = status
    assert run.verdict.status is VerdictStatus.VERIFIED
    assert run.evaluation.execution_support is ExecutionSupport.SUPPORTED
    assert run.evaluation.applicability is Applicability.APPLICABLE


def test_pending_requirement_only_run_has_no_verdict():
    run = VerificationRun(
        id="pending", architecture=ArchitectureIR(repository_root="fixture"),
        requirement=EngineeringRequirement(id="r", raw_requirement="Claim"),
    )
    assert run.execution_status is ExecutionStatus.PENDING
    assert run.evaluation is run.plan is run.verdict is None
    assert run.evidence == run.trace == []


def test_requirement_only_plan_and_verdict():
    plan = VerificationPlan(requirement_id="r", claim="Claim", verification_mode="STATIC",
                            tool="fixture", acceptance_condition="condition")
    verdict = Verdict(requirement_id="r", status="NOT_VERIFIABLE", summary="No evidence")
    assert plan.evaluation_id is verdict.evaluation_id is None
    assert verdict.evidence_ids == ()


def test_subject_is_required(objects):
    for index in [4, 6, 8]:
        model = objects[index]
        data = model.model_dump()
        for field in ["evaluation_id", "requirement_id", "evaluation", "requirement"]:
            data.pop(field, None)
        with pytest.raises(ValidationError):
            type(model).model_validate(data)


@pytest.mark.parametrize("line,column", [(0, None), (-1, None), (1, -1)])
def test_invalid_source_coordinates(line, column):
    with pytest.raises(ValidationError):
        SourceLocation(file="fixture.py", line=line, column=column)


def test_evidence_requires_provenance(objects):
    data = objects[5].model_dump()
    for field in ["source", "tool"]:
        invalid = {**data, field: ""}
        with pytest.raises(ValidationError):
            Evidence.model_validate(invalid)


def test_trace_rejects_chain_of_thought_field(objects):
    with pytest.raises(ValidationError):
        TraceEvent.model_validate({**objects[7].model_dump(), "chain_of_thought": "hidden"})


def test_serialization_round_trip(objects):
    for model in objects:
        assert type(model).model_validate_json(model.model_dump_json()) == model
    run = objects[-1]
    dumped = run.model_dump(mode="json")
    assert dumped["execution_status"] == "COMPLETED"
    assert dumped["verdict"]["status"] == "VERIFIED"
    assert dumped["evidence"][0]["observed_value"] is True
    assert dumped["evidence"][0]["source_location"]["file"] == "fixtures/client.py"
    assert run.model_dump()["verdict"]["status"] is VerdictStatus.VERIFIED


@pytest.mark.parametrize("status", ["VERIFIED", "VIOLATED"])
def test_conclusive_verdict_requires_evidence(status):
    for evidence_ids in [None, []]:
        data = dict(status=status, evaluation_id="timeout", summary="Fixture")
        if evidence_ids is not None:
            data["evidence_ids"] = evidence_ids
        with pytest.raises(ValidationError, match="at least one evidence ID"):
            Verdict(**data)
    verdict = Verdict(status=status, evaluation_id="timeout", evidence_ids=["ev1"],
                      summary="Fixture")
    assert verdict.evidence_ids == ("ev1",)
    with pytest.raises(ValidationError):
        verdict.evidence_ids = ()
    assert verdict.evidence_ids == ("ev1",)


def test_not_verifiable_allows_zero_evidence_ids():
    verdict = Verdict(status="NOT_VERIFIABLE", requirement_id="r", summary="No evidence")
    assert verdict.evidence_ids == ()
    with pytest.raises(ValidationError):
        verdict.status = VerdictStatus.VERIFIED
    assert verdict.status is VerdictStatus.NOT_VERIFIABLE


@pytest.mark.parametrize("field,value", [
    ("id", "replacement"), ("type", EvidenceType.RUNTIME),
    ("source", "replacement"), ("tool", "replacement"),
    ("claim", "replacement"), ("observed_value", False),
    ("observation_json", "false"), ("source_location", None),
    ("limitations", ("replacement",)), ("unit", "ms"),
])
def test_evidence_fields_are_immutable(objects, field, value):
    evidence = objects[5]
    original = evidence.model_dump()
    with pytest.raises((ValidationError, AttributeError)):
        setattr(evidence, field, value)
    assert evidence.model_dump() == original


@pytest.mark.parametrize("field,value", [("file", "other.py"), ("line", 99), ("column", 9)])
def test_evidence_source_location_is_immutable(objects, field, value):
    location = objects[5].source_location
    original = location.model_dump()
    with pytest.raises(ValidationError):
        setattr(location, field, value)
    assert location.model_dump() == original


def test_evidence_nested_observation_is_an_immutable_snapshot():
    original = {"calls": [{"timeout": True}], "details": {"services": ["example"]}}
    limitations = ["Fixture only"]
    evidence = Evidence(id="ev", type="STATIC_ANALYSIS", source="fixture.py",
                        tool="fixture", claim="Fixture", observed_value=original,
                        limitations=limitations)
    original["calls"][0]["timeout"] = False
    limitations.append("changed")
    view = evidence.observed_value
    view["calls"][0]["timeout"] = False
    view["details"]["services"].append("changed")
    assert evidence.observed_value == {
        "calls": [{"timeout": True}], "details": {"services": ["example"]},
    }
    assert evidence.limitations == ("Fixture only",)
    with pytest.raises(AttributeError):
        evidence.limitations.append("changed")
    dumped = evidence.model_dump(mode="json")
    assert "observation_json" not in dumped
    assert dumped["observed_value"] == evidence.observed_value
    dumped["observed_value"]["calls"].clear()
    assert len(evidence.observed_value["calls"]) == 1
    assert Evidence.model_validate_json(evidence.model_dump_json()) == evidence


@pytest.mark.parametrize("index,fields", [
    (4, ["evaluation_id", "requirement_id"]),
    (6, ["evaluation_id", "requirement_id"]),
    (8, ["evaluation", "requirement"]),
])
def test_subject_links_are_frozen_and_rejections_preserve_validity(objects, index, fields):
    model = objects[index]
    original = model.model_dump()
    for field in fields:
        with pytest.raises(ValidationError):
            setattr(model, field, None)
        assert model.model_dump() == original
        assert type(model).model_validate(model.model_dump()) == model


@pytest.mark.parametrize("index", [4, 6, 8])
def test_subject_links_allow_validated_replacements(objects, index):
    model = objects[index]
    data = model.model_dump()
    if index == 8:
        data["evaluation"] = None
        data["requirement"] = {"id": "new", "raw_requirement": "Replacement claim"}
    else:
        data["evaluation_id"] = None
        data["requirement_id"] = "new"
    replacement = type(model).model_validate(data)
    assert replacement != model
    assert model.model_dump() != data
