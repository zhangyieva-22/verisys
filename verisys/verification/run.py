"""Explicit static verification cases, not an evaluation profiler or general orchestrator."""
import hashlib
from dataclasses import dataclass
from pathlib import Path

from verisys.architecture import analyze_architecture
from verisys.models import EngineeringRequirement, EvaluationCandidate, TraceEvent, VerificationPlan, VerificationRun
from verisys.repository import discover_repository
from verisys.repository.discovery import DiscoveryLimits
from . import http_timeout, timeout
from .judge import judge_timeouts
from .static_timeouts import TimeoutPolicy, inspect_call_timeouts, stable_id


@dataclass(frozen=True)
class TimeoutCase:
    """Fixed requirement, plan and wording for one static timeout policy."""
    policy: TimeoutPolicy
    name: str
    target: str
    property: str
    source: str
    reason: str
    subject: str


OPENAI_CASE = TimeoutCase(timeout.POLICY, "External API Timeout Coverage",
    "supported concrete OpenAI API call sites in the repository", "explicit_per_call_timeout_configuration",
    "Golden Verification Case #1", "Explicitly selected OpenAI per-call timeout policy.", "OpenAI")
HTTP_CASE = TimeoutCase(http_timeout.POLICY, "HTTP Client Timeout Coverage",
    "supported concrete requests and httpx call sites in the repository", "finite_http_client_timeout",
    "HTTP client timeout policy", "Explicitly selected requests/httpx finite timeout policy.", "requests/httpx")


def timeout_requirement(case: TimeoutCase = OPENAI_CASE):
    return EngineeringRequirement(id=case.policy.policy_id, raw_requirement=case.policy.claim,
        target=case.target, property=case.property, metric="timeout_coverage",
        operator="==", threshold=1.0, unit="ratio", source=case.source)


def timeout_plan(requirement, case: TimeoutCase = OPENAI_CASE):
    return VerificationPlan(requirement_id=requirement.id, claim=requirement.raw_requirement,
        target=requirement.target, verification_mode="STATIC", tool=case.policy.tool,
        required_evidence=["Fresh supported call scope with source-content hashes",
                           "Per-call explicit timeout observations and exact source locations"],
        procedure=["Fresh safe discovery and architecture analysis", "Bounded source-matched per-call inspection",
                   "Collect immutable static evidence", "Apply the deterministic evidence-only judge"],
        acceptance_condition="total > 0 AND configured == total AND missing == 0 AND unknown == 0 AND scope_complete",
        limitations=list(case.policy.limitations))


def _verify(case: TimeoutCase, root: str | Path, limits: DiscoveryLimits | None) -> VerificationRun:
    policy = case.policy
    requirement = timeout_requirement(case)
    plan = timeout_plan(requirement, case)
    discovery = discover_repository(root, limits=limits)
    hashes = {}
    architecture = analyze_architecture(discovery,
        on_source=lambda path, data: hashes.__setitem__(path, hashlib.sha256(data).hexdigest()))
    evidence = inspect_call_timeouts(policy, discovery, architecture, hashes)
    judgment = judge_timeouts(evidence, policy_id=policy.policy_id, tool=policy.tool)
    scope = evidence[-1].observed_value
    evaluation = EvaluationCandidate(id=policy.policy_id, name=case.name, category="Reliability",
        applicability=judgment.applicability, priority="HIGH", reason=case.reason,
        verification_mode="STATIC", execution_support="SUPPORTED" if scope["scope_complete"] and not judgment.counts.unknown else "PARTIAL",
        required_evidence=list(plan.required_evidence))
    run_id = stable_id("timeout-run", [str(discovery.repository_root), [item.id for item in evidence]])
    trace = []
    def event(type_, stage, summary, metadata=None, linked=()):
        trace.append(TraceEvent(id=f"{run_id}:{len(trace) + 1}", type=type_, stage=stage,
            summary=summary, metadata=metadata or {}, related_evidence_ids=list(linked)))
    event("DECISION", "requirement", f"Explicit per-call {case.subject} requirement accepted.", {"requirement_id": requirement.id})
    event("DECISION", "planning", "STATIC timeout inspection selected.", {"tool": policy.tool, "applicability": judgment.applicability.value})
    event("ACTION", "inspection", f"Safely inspect source at freshly detected {case.subject} call locations.")
    event("OBSERVATION", "inspection", "Supported call locations processed.", {"total": judgment.counts.total})
    event("EVIDENCE", "collection", "Immutable static observations collected.", linked=[item.id for item in evidence])
    event("OBSERVATION", "coverage", "Configured, missing and unknown counts calculated.", judgment.counts.observed(scope["scope_complete"]))
    event("DECISION", "judgment", judgment.verdict.summary if judgment.verdict else f"No applicable supported {case.subject} calls; no verdict manufactured.")
    if judgment.verdict:
        event("VERDICT", "judgment", judgment.verdict.status.value, linked=judgment.verdict.evidence_ids)
    run = VerificationRun(id=run_id, architecture=architecture, evaluation=evaluation, requirement=requirement,
        plan=plan, execution_status="COMPLETED" if judgment.verdict else "NOT_RUN",
        evidence=evidence, verdict=judgment.verdict, trace=trace, limitations=list(evidence[-1].limitations))
    if run.verdict and not set(run.verdict.evidence_ids).issubset({item.id for item in run.evidence}):
        raise ValueError("Verdict references evidence outside this run")
    return run


def verify_timeout_coverage(root: str | Path, *, limits: DiscoveryLimits | None = None) -> VerificationRun:
    return _verify(OPENAI_CASE, root, limits)


def verify_http_timeout_coverage(root: str | Path, *, limits: DiscoveryLimits | None = None) -> VerificationRun:
    return _verify(HTTP_CASE, root, limits)
