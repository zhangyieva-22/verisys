# Engineering evaluation catalog

This document defines current evaluation semantics and distinguishes discovery
from execution. Runtime code in `verisys/evaluation/catalog.py` is the trusted
versioned catalog; `verification/timeout.py` and `judge.py` implement M4's policy.
Policy changes require coordinated tests, documentation and explicit scope approval.

## Ownership and current catalog

The server owns stable IDs, names/categories, property/purpose, signal and rationale
allowlists, required evidence, modes, execution support rules, priority, limitations
and verifier availability. The LLM only selects eligible option IDs. It cannot
redefine acceptance, infer capability or produce Evidence/Verdict.

Catalog version: `engineering-evaluations-v2`. Five entries are selectable; v2 added
HTTP Client Timeout Coverage to the four M4.5 entries. Their default discovery priority is MEDIUM. The explicitly selected M4 run
has its own existing HIGH priority; that is not an LLM business ranking.

### External API Timeout Coverage

ID: `external-api-timeout-coverage-v1`. Category: Reliability. Mode: STATIC.
Property: explicit per-call timeout configuration.

- `supported_openai_calls`: direct `openai` service subjects with supported concrete
  calls. Discovery applicability APPLICABLE; execution support SUPPORTED.
- `openai_wrapper_presence`: `openai`/`langchain_openai` presence without supported
  concrete calls. Discovery applicability UNKNOWN; support PARTIAL.

The installed verifier covers only the documented direct OpenAI per-call grammar.
Wrapper presence cannot be paired with the direct-call rationale. Fresh supported
call scope and per-call static observations are required to verify, not merely an
architecture summary. A candidate never establishes repository-wide coverage.

### HTTP Client Timeout Coverage

ID: `http-client-timeout-coverage-v1`. Category: Reliability. Mode: STATIC.
Property: finite timeout on outbound `requests` and `httpx` calls.

- `supported_http_client_calls`: `requests`/`httpx` service subjects with supported concrete
  calls. Discovery applicability APPLICABLE; execution support SUPPORTED.
- `http_client_presence`: `requests`/`httpx` presence without supported concrete calls.
  Discovery applicability UNKNOWN; support PARTIAL.

The installed verifier follows each library's documented defaults; see
[the HTTP client timeout contract](#http-client-timeout-contract) below.

### Retry Safety

ID: `retry-safety-v1`. Category: Reliability. Mode: RUNTIME.
Rationale: `source_declared_retry_loop`.

A source-declared conditional self-loop can justify investigation. Subjects are
ExecutionFlow IDs; transitions/steps are supporting facts. Discovery applicability
UNKNOWN; support NOT_AVAILABLE. A repeated path does not prove actual retries,
external effects or retry safety. Required evidence includes an explicit safety
requirement, actual side effects and a controlled runtime retry experiment.

### API Latency

ID: `api-latency-v1`. Category: Performance. Mode: PERFORMANCE.
Rationale: `http_api_routes`.

Detected HTTP route components justify APPLICABLE/NOT_AVAILABLE recommendations.
A running environment, defined workload, acceptance threshold and executed load-test
measurements are required. Static source establishes neither P95 nor throughput.

### Tool Side-Effect Safety

ID: `tool-side-effect-safety-v1`. Category: Reliability. Mode: RUNTIME.
Rationale: `tool_candidates_in_workflow`.

A grounded workflow tool-candidate set creates an opportunity bound to its flow
and projected TOOL components. Applicability UNKNOWN; support NOT_AVAILABLE.
Candidate tools do not prove external side effects, execution order or per-request
selection. Actual effects, an explicit safety requirement and controlled runtime
observations are required.

## Eligible options and selection

The deterministic layer constructs options from retained validated architecture
subjects and catalog predicates. Each option has option_id, architecture_id,
evaluation_id, relevance_reason, allowed_subject_ids and architecture_summary.
Only projected component IDs and ExecutionFlow IDs are selectable subjects.
ExecutionStep IDs never become top-level subjects or selectable option identities.

The request-specific structured-output enum contains exactly supplied option IDs:

```json
{"selected_option_ids": []}
```

Empty selection is allowed; eligible options are not returned automatically.
The current bound is six selected options: five evaluation families, with both timeout
evaluations potentially split into direct-call and presence-only opportunities. IDs/order are
stable for identical normalized input. Inputs, including options, are bounded;
truncation propagates honestly. No identifier is shortened into another identity.

Unknown IDs, duplicates, extra authoritative fields or stale/tampered snapshot
options reject the entire response. Expansion remains server-controlled and still
checks catalog identity, subject kinds/IDs and rationale predicates. The model
cannot author a new rationale/subject combination through this schema.

If direct and wrapper timeout options are both selected, the server produces one
UNKNOWN/PARTIAL candidate with combined subjects/reasons/limitations. Other options
are grouped by their grounded evaluation/rationale. The final candidate's evidence-ID
list is distinct from its architecture_subject_ids; component IDs are never evidence.

## M4 executable timeout contract

Claim:

> All supported OpenAI API call sites must define an explicit per-call timeout.

Tool: `python-static-timeout-v1`. Mode: STATIC. Scope is concrete direct `openai`
call families already recognized by the analyzer, not every possible external API.
Stripe, Twilio, ChatOpenAI wrappers and arbitrary client patterns are unsupported.
Construction references are not concrete API calls.

Per-call outcomes:

- **CONFIGURED:** explicit positive finite numeric timeout literal.
- **MISSING:** no explicit per-call timeout, or invalid literal such as None, zero,
  negative, boolean or nonnumeric values.
- **UNKNOWN:** symbolic expressions or expanded keywords. Variables are not
  evaluated; `**kwargs` stays unknown even beside an explicit timeout.

A client constructor timeout does not satisfy this per-call policy. The verifier
makes no claim about SDK defaults, effective runtime timeout inheritance, wrapper
behavior or runtime reliability. It does not store arbitrary argument values.

Fresh discovery/analysis establish supported scope. Inspection checks safe reads,
content hashes and exact call location (file/line/UTF-8 byte column). Evidence
contains immutable per-call observations and a scope manifest. The judge validates
provenance and manifest links before applying these rules:

1. Any conclusive MISSING yields VIOLATED, even if other observations are unknown.
2. No MISSING, but unknown observations or incomplete scope, yields NOT_VERIFIABLE.
3. Nonempty complete scope with all calls CONFIGURED yields VERIFIED.
4. Conclusively empty supported scope yields NOT_APPLICABLE/NOT_RUN, no verdict.
5. Empty incomplete scope yields applicability UNKNOWN and NOT_VERIFIABLE.

Acceptance is:

```text
total > 0
AND configured == total
AND missing == 0
AND unknown == 0
AND scope_complete
```

`total = configured + missing + unknown`. Definitive coverage percentage is emitted
only for nonempty complete scope without unknown observations. Unknown is not
counted as missing. The golden example gives 2 configured, 1 missing, 0 unknown,
66.7%, VIOLATED. Architecture limitations conservatively prevent complete-scope
VERIFIED/NOT_APPLICABLE; their prose is not interpreted to invent completeness.
Execution support can be PARTIAL while execution status is COMPLETED.

Repositories should remain stable during inspection. Hash checks cover discovered
source, including initially call-free files, but cannot guarantee an atomic snapshot
or detect every newly introduced file/directory change.

## HTTP client timeout contract

Claim:

> Every supported requests and httpx call site has a finite timeout.

Tool: `python-static-http-timeout-v1`. Mode: STATIC. It shares the M4 scope manifest,
safe re-reads, hash checks, exact call identity and judge rules above; only call
classification differs. The design and its accepted decisions are in
[http-client-timeout.md](http-client-timeout.md).

Supported calls are the module functions `get`, `options`, `head`, `post`, `put`,
`patch`, `delete` and `request` (plus `stream` for `httpx`), and the same methods on a
simple name bound to `requests.Session()`/`requests.session()` or
`httpx.Client(...)`/`httpx.AsyncClient(...)`, including `with`/`async with` bindings.

Per-call outcomes follow each library's defaults: `requests` never times out by
default, while `httpx` defaults to five seconds and client methods inherit the client's
timeout. Each CONFIGURED observation records `timeout_source`: `call`, `client` or
`library_default`.

- **CONFIGURED:** a positive finite literal, a `requests` `(connect, read)` or `httpx`
  four-element tuple of positive finite literals, or `httpx.Timeout(...)` with only
  positive finite literal arguments, on the call; otherwise, for `httpx` only, the
  client's positive literal timeout or the library default.
- **MISSING:** a `requests` call without `timeout`; `None` anywhere in the effective
  timeout (call or `httpx` client); invalid literals such as zero, negative, boolean,
  string values or a tuple of the wrong length.
- **UNKNOWN:** non-literal timeouts, expanded keywords, unresolved `httpx` client
  constructors, clients whose identity differs between branches, and calls without
  `timeout` on a `requests` session that has `.mount(...)` anywhere in the module,
  because a custom adapter may supply a timeout.

`library_default` reports the documented default of current `httpx` releases; the
installed version is not checked. A finite timeout does not establish that its value
is appropriate. Wrappers, adapters, `.send()` and clients passed between functions
are not resolved.

## State and failure semantics

A recommendation is an investigation opportunity, not a verification result.
Applicability, support, mode, execution status and verdict remain separate.
A missing runtime verifier must say NOT_AVAILABLE; discovery creates no verdict.
A completed verification without sufficient evidence must say NOT_VERIFIABLE.
Provider/API failure or invalid selection must never become successful `[]`.
Valid empty selection succeeds. Missing key/SDK, timeout, refusal, incomplete output,
unknown options and semantic mismatch are controlled discovery failures.

The registry maps `external-api-timeout-coverage-v1` to `verify_timeout_coverage` and
`http-client-timeout-coverage-v1` to `verify_http_timeout_coverage`. Lookup describes
availability and does not execute anything. Other entries have no verifier.

## Future catalog directions

These are product directions, not selectable M4.5 entries or installed verifiers:

- Reliability: idempotency and duplicate-effect safety.
- Resilience: worker recovery, retry behavior and dead-letter queue coverage.
- Performance: throughput and error rate under load.
- Scalability: concurrent behavior, throughput degradation and resource saturation.
- Architecture: cycles, layer rules, direct database access and synchronous dependency
  constraints, only with supported structural/request-path evidence.
- Data consistency: duplicate writes, transaction safety and external side effects.
- Security: authentication, authorization, tenant isolation and input validation.
- Functional engineering requirements: explicit project-defined claims and tests.

Thresholds should come from an explicit user requirement, documented team policy,
a clearly labeled recommended baseline or an actual structural invariant. Do not
invent business criticality, workload or performance targets. No aggregate
architecture health score is part of this catalog.

For implementation extension points, see [the evaluation extension path](architecture.md#evaluation-extension-path).
