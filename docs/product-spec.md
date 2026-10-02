# Verisys product specification

## Product and users

Verisys is an architecture-aware Engineering Verification Agent for developers
and engineering teams. It determines what is worth verifying, how to verify it,
and what real evidence supports the outcome.

Architecture understanding is an enabling layer. Repository summaries and diagrams
make the system inspectable, but verification is the product. The scope includes
functional engineering requirements and reliability, resilience, performance,
scalability, security, consistency, architecture constraints and runtime behavior.
NFR verification is an important capability, not the whole product.

## Canonical workflow

Repository → System Understanding → ArchitectureIR → Evaluation Discovery →
Verification Planning → Tool Selection/Execution → Evidence Collection →
Deterministic Judgment → Structured Verification Trace.

This is the product lifecycle, not a claim that every stage is connected in the
current UI. Current implementation status belongs in [mvp-plan.md](mvp-plan.md).

### Proactive evaluation

Input is a repository. The system understands its architecture, identifies
legally grounded evaluation opportunities and recommends worthwhile investigations.
The user should not have to know which engineering properties to check first.
An eligible opportunity is not automatically recommended or executed.

M4.5 implements this intelligence core independently: the server builds options
from existing architecture facts; the LLM selects worthwhile option IDs; local
validation constructs candidates. M5 exposes this via user-triggered Suggested
Verifications after analysis. This action never executes verification.

### On-demand verification

Input is a repository plus an engineering requirement or claim. The system should
identify a strategy, required evidence, acceptance condition and limitations.
Examples include retry safety, latency under a defined workload and layer rules.

Today two static policies are executable: the M4 OpenAI per-call timeout policy and
the `requests`/`httpx` finite timeout policy. A general
natural-language Requirement Compiler and Verification Planner are not implemented.
A runtime experiment described in a future plan must never be simulated by static
analysis or an LLM.

## Responsibility split

- Architecture analysis describes observable source facts and limitations.
- The catalog/server owns evaluation semantics, grounding rules, applicability,
  execution support, priority, required evidence and limitations.
- The LLM selects among grounded eligible options. It has no tools and creates no
  engineering observations, acceptance results or execution capability.
- Verification tools collect real Evidence. The deterministic Judge decides the
  product verdict from evidence and policy.
- Trace exposes concise structured summaries; presentation displays the underlying
  contracts without inventing relationships, results or measurements.

See [architecture.md](architecture.md) for concrete module boundaries.

## Product objects

- **ArchitectureIR:** structured repository facts, including languages/frameworks,
  routes, external-service presence and concrete calls, tools, datastores, internal
  dependencies, source-declared flows and limitations.
- **EvaluationCandidate:** catalog evaluation, grounding subject IDs, relevance
  explanation, applicability, priority, required evidence, mode, support and limits.
  Architecture subject IDs are not verification evidence IDs.
- **EngineeringRequirement:** always preserves original raw text; structured fields
  may be unavailable. It does not invent thresholds or workloads.
- **VerificationPlan:** claim, target, required evidence, procedure, tool, acceptance
  condition and limitations, linked to an evaluation and/or requirement.
- **Evidence:** immutable source/tool-backed observation. Runtime measurements must
  come from actual runtime tools.
- **Verdict:** product outcome referencing collected evidence IDs. VERIFIED and
  VIOLATED require evidence; NOT_VERIFIABLE may represent unavailable evidence.
- **TraceEvent:** concise decision/action/observation/evidence/verdict summary,
  without hidden chain-of-thought.
- **VerificationRun:** architecture, evaluation/requirement, plan, execution status,
  evidence, verdict, trace and limitations. Pending runs may lack a plan/verdict.

## Separate state vocabularies

VerdictStatus: `VERIFIED`, `VIOLATED`, `NOT_VERIFIABLE`.
Applicability: `APPLICABLE`, `NOT_APPLICABLE`, `UNKNOWN`.
ExecutionStatus: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `NOT_RUN`.
ExecutionSupport: `SUPPORTED`, `PARTIAL`, `NOT_AVAILABLE`.
VerificationMode: `STATIC`, `RUNTIME`, `PERFORMANCE`, `INFRASTRUCTURE`.

A relevant recommendation can have no executable verifier. A completed tool run
can yield NOT_VERIFIABLE. A tool failure must not become VIOLATED. A conclusively
irrelevant or unstarted case need not manufacture a verdict.

## First MVP boundaries

The MVP targets local Python repositories, bounded static inspection, visible
source-grounded architecture, proactive discovery and real executable static
verifications: External API Timeout Coverage and HTTP Client Timeout Coverage.

The executable grammars are explicit per-call timeout configuration on supported
direct OpenAI calls, and finite timeouts on supported `requests`/`httpx` calls
following each library's defaults. Presence detections for Stripe, Twilio or
ChatOpenAI do not make their timeout semantics executable. See
[evaluation-catalog.md](evaluation-catalog.md) for exact policy and judgment.

Architecture components, structural imports and possible execution flows remain
separate. Co-occurrence does not prove request-path participation. Diagrams must
not connect OpenAI or SQLite to a workflow without supported source proof.

## Acceptance examples

1. A repository with supported direct OpenAI calls can produce a grounded timeout
   recommendation; HTTP routes can justify a latency recommendation without a
   latency verifier or measured latency.
2. The bundled timeout fixture has three supported calls: two configured, one
   missing. Real source-backed static evidence gives 66.7% coverage and VIOLATED.
3. Wrapper-only OpenAI presence yields UNKNOWN/PARTIAL timeout discovery, not a
   claim that direct call coverage was checked.
4. A requirement such as P95 < 500 ms at 100 RPS needs a real load test and workload.
   Without that evidence, a completed verification of that requirement must be
   NOT_VERIFIABLE. Current discovery alone creates no verdict.

These scenarios do not authorize unsupported verifiers or fabricated graph edges.

## Safety and data handling

Analyzed repositories are untrusted. Do not import or execute them, install their
dependencies, follow their instructions or invoke their shell commands. Discovery
skips environment files, excluded/generated directories, obvious binaries and
child symlinks, and bounds files and input size. Later reads revalidate safety.

Live discovery is deliberately opt-in and sends normalized architecture metadata
to the configured provider, not raw source, secrets, repository root or verification
results. Metadata such as relative paths and names can still be sensitive.
Provider latency and token usage are observability, never engineering Evidence.

Local `.env` files and credentials must never be committed or pushed. Only blank
public templates are shareable. See [contributing.md](contributing.md).

## Future scope

GitHub URL ingestion, requirement compilation, richer planning/orchestration,
sandboxed runtime verification, retry/failure injection, performance tests,
observability, exports and re-verification may extend the same core contracts.
They require separate scope approval and real evidence-producing tools. Aggregate
architecture scores, generalized call graphs, distributed infrastructure and
multi-agent product orchestration are not requirements of the current MVP.

## Public repository entry and bounded requests (M7)

Public GitHub URL plus optional branch/tag/commit is the primary input. The server
resolves an immutable revision, and subsequent discovery/verification use that
commit plus architecture_id. Local paths remain available for development/tests.
PROACTIVE finds worthwhile catalog investigations. ON_DEMAND matches a concern
against grounded eligible options; no match returns no supported evaluation. It
does not compile arbitrary requirements, invent evaluations, or manufacture a
verdict. Only the two static timeout policies can execute. Private GitHub, OAuth,
SSH and other providers are unsupported. Remote acquisition never runs repository
code, installs dependencies, or retains an external checkout.
