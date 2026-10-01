"""One explicit verification case, not an evaluation profiler or general orchestrator."""
import hashlib
from pathlib import Path

from verisys.architecture import analyze_architecture
from verisys.models import EngineeringRequirement, EvaluationCandidate, TraceEvent, VerificationPlan, VerificationRun
from verisys.repository import discover_repository
from verisys.repository.discovery import DiscoveryLimits
from .judge import judge_timeouts
from .timeout import CLAIM, POLICY_ID, POLICY_LIMITS, TOOL, inspect_timeouts, stable_id


def timeout_requirement():
    return EngineeringRequirement(id=POLICY_ID, raw_requirement=CLAIM,
        target="supported concrete OpenAI API call sites in the repository",
        property="explicit_per_call_timeout_configuration", metric="timeout_coverage",
        operator="==", threshold=1.0, unit="ratio", source="Golden Verification Case #1")


def timeout_plan(requirement):
    return VerificationPlan(requirement_id=requirement.id, claim=requirement.raw_requirement,
        target=requirement.target, verification_mode="STATIC", tool=TOOL,
        required_evidence=["Fresh supported call scope with source-content hashes",
                           "Per-call explicit timeout observations and exact source locations"],
        procedure=["Fresh safe discovery and architecture analysis", "Bounded source-matched per-call inspection",
                   "Collect immutable static evidence", "Apply the deterministic evidence-only judge"],
        acceptance_condition="total > 0 AND configured == total AND missing == 0 AND unknown == 0 AND scope_complete",
        limitations=list(POLICY_LIMITS))


def verify_timeout_coverage(root: str | Path, *, limits: DiscoveryLimits | None = None) -> VerificationRun:
    requirement = timeout_requirement()
    plan = timeout_plan(requirement)
    discovery = discover_repository(root, limits=limits)
    hashes = {}
    architecture = analyze_architecture(discovery,
        on_source=lambda path, data: hashes.__setitem__(path, hashlib.sha256(data).hexdigest()))
    evidence = inspect_timeouts(discovery, architecture, hashes)
    judgment = judge_timeouts(evidence)
    scope = evidence[-1].observed_value
    evaluation = EvaluationCandidate(id=POLICY_ID, name="External API Timeout Coverage", category="Reliability",
        applicability=judgment.applicability, priority="HIGH", reason="Explicitly selected OpenAI per-call timeout policy.",
        verification_mode="STATIC", execution_support="SUPPORTED" if scope["scope_complete"] and not judgment.counts.unknown else "PARTIAL",
        required_evidence=list(plan.required_evidence))
    run_id = stable_id("timeout-run", [str(discovery.repository_root), [item.id for item in evidence]])
    trace = []
    def event(type_, stage, summary, metadata=None, linked=()):
        trace.append(TraceEvent(id=f"{run_id}:{len(trace) + 1}", type=type_, stage=stage,
            summary=summary, metadata=metadata or {}, related_evidence_ids=list(linked)))
    event("DECISION", "requirement", "Explicit per-call OpenAI requirement accepted.", {"requirement_id": requirement.id})
    event("DECISION", "planning", "STATIC timeout inspection selected.", {"tool": TOOL, "applicability": judgment.applicability.value})
    event("ACTION", "inspection", "Safely inspect source at freshly detected OpenAI call locations.")
    event("OBSERVATION", "inspection", "Supported call locations processed.", {"total": judgment.counts.total})
    event("EVIDENCE", "collection", "Immutable static observations collected.", linked=[item.id for item in evidence])
    event("OBSERVATION", "coverage", "Configured, missing and unknown counts calculated.", judgment.counts.observed(scope["scope_complete"]))
    event("DECISION", "judgment", judgment.verdict.summary if judgment.verdict else "No applicable supported OpenAI calls; no verdict manufactured.")
    if judgment.verdict:
        event("VERDICT", "judgment", judgment.verdict.status.value, linked=judgment.verdict.evidence_ids)
    run = VerificationRun(id=run_id, architecture=architecture, evaluation=evaluation, requirement=requirement,
        plan=plan, execution_status="COMPLETED" if judgment.verdict else "NOT_RUN",
        evidence=evidence, verdict=judgment.verdict, trace=trace, limitations=list(evidence[-1].limitations))
    if run.verdict and not set(run.verdict.evidence_ids).issubset({item.id for item in run.evidence}):
        raise ValueError("Verdict references evidence outside this run")
    return run
