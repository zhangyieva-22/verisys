# Verisys architecture

This document describes current implementation boundaries. Product intent is in
[product-spec.md](product-spec.md), exact verification policy in
[evaluation-catalog.md](evaluation-catalog.md), and sequencing in
[mvp-plan.md](mvp-plan.md). Do not interpret future capabilities as implemented.

## Current pipelines

Architecture presentation:

Tagged local/public GitHub source → bounded materialization → Repository Discovery → bounded static AST analysis →
ArchitectureIR → pure ArchitectureGraph projection → local API → frontend.

User-triggered evaluation discovery (M5):

Repository source at an immutable remote revision → fresh safe server analysis → ArchitectureIR →
normalized subject index → deterministic eligible options →
optional LLM option selection → strict local validation → EvaluationCandidate[] →
Suggested Verifications.

Explicit M4 verification:

Repository + fixed timeout requirement → VerificationPlan → fresh discovery and
analysis → safe static timeout inspection → immutable Evidence → evidence-only
Judge → Verdict + VerificationRun + structured Trace.

Discovery retains its independent Python entry point and now has a thin local
HTTP/UI adapter. M6 adds a narrow execution/result adapter over the unchanged M4 core. There is no general orchestrator.

## Package responsibilities

- `verisys/models/`: typed shared domain objects and schema invariants; no execution.
- `verisys/repository/`: discovery, effective limits and safe source reading.
- `verisys/architecture/`: bounded AST understanding, finite flow extraction and
  deterministic graph projection; no evaluation selection or verification.
- `verisys/evaluation/`: catalog, normalized input/contracts, deterministic rules
  and options, selection validation and optional provider adapter.
- `verisys/verification/`: M4 static tool, evidence-only judge, fixed run assembly
  and registry lookup; no general planning or runtime executor.
- `verisys/api/`: local analysis request validation and adapters over existing code.
- `frontend/`: presentation DTO types, React Flow adapters, workspace and Inspector.
- `tests/`, `frontend/tests/`, `examples/`: focused behavior tests and static fixtures.

Architecture analysis must not depend on evaluation discovery. Provider-specific
SDK objects stay behind the provider interface. The evaluation layer may look up
verifier availability; it must never invoke the registry. Frontend geometry and
selection state stay outside domain DTOs.

## Shared contracts and mutation

Python `verisys/models/graph.py`, `verisys/models/execution.py` and the response
models in `verisys/api/app.py` are manually synchronized with
`frontend/lib/architecture/types.ts` and `frontend/lib/architecture/analysis-client.ts`.
`frontend/lib/evaluation/discovery-client.ts` mirrors the narrow suggestion DTO.
`frontend/next.config.ts` owns the analysis/discovery proxies. Serialized contract changes
require coordinated frontend types/client updates and backend/frontend tests;
there is no contract code generation. The renderer consumes the graph DTO, not IR.

`verisys/models/base.py` rejects extra fields and validates assignment. Identity,
subject-link and provenance fields are frozen where their models require it; not
all models are wholly immutable. Construct a validated replacement when changing
frozen links rather than assuming arbitrary mutation or using unchecked copies.
Evidence-owned observation data is a JSON snapshot, returned as decoded copies.

## Repository discovery and safe reads

`discover_repository(root, limits=...)` validates a local directory and returns
relative Python paths in deterministic order, skipped items/reasons, effective
limits, truncation and limitations. The root is canonicalized; all child symlinks,
including internal ones, are skipped to avoid aliases and loops.

`verisys.repository.discovery.DiscoveryLimits` bounds filesystem discovery and
source ingestion. It is distinct from `verisys.evaluation.contracts.DiscoveryLimits`,
which bounds normalized subjects, objects, strings and provider input bytes.
Do not interchange these configuration models.

Defaults are 1 MiB per file, 1000 files, 20 MiB total source and 100,000 directory
entries. Exclusions include `.git`, virtual environments, node_modules, caches,
vendor/generated/build/dist directories, `.env`/`.env.*`, non-Python files,
non-regular files and obvious binaries. Consult `repository/discovery.py` for the
full exclusion set and reason enum.

`analyze_architecture(discovery, limits=...)` reuses discovery's effective limits.
An explicit override can only tighten them. Safe reads revalidate containment,
regular-file status, child symlinks and size; remaining aggregate budget constrains
ingestion before a complete file is read. Sanitized rejection categories include
outside_root, symlink, non_regular_file, file_too_large, aggregate_budget_exhausted
and read_error.

POSIX directory descriptors and NOFOLLOW protections are the current filesystem
boundary. This is not an atomic repository snapshot: concurrent writes, new files
and directory changes remain limitations. Keep the repository stable during a run.
No analyzed source is executed or imported, and its dependencies are not installed.

## Architecture analysis

The analyzer parses safely read Python source with AST and records supported facts.
Syntax/read failures, truncation, ambiguous bindings and unsupported constructs
remain explicit limitations rather than guessed architecture.

Supported bounded patterns include:

- FastAPI/APIRouter aliases and simple object bindings, GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS/TRACE decorators,
  literal/keyword paths and handler source locations. Router prefix composition
  and dynamic route construction are unresolved.
- Import/binding-grounded OpenAI, Stripe and Twilio client/call patterns.
  Client presence references are separate from concrete supported API call sites.
- ChatOpenAI import/construction presence through exact `langchain_openai` bindings.
  Wrapper invoke/stream/factory behavior is not reconstructed.
- Bare `@tool` bound to `langchain_core.tools.tool`, including aliases, yielding
  function-definition references. Decorator factories remain unsupported.
- Explicit resolved `sqlite3.connect` presence, without storing database paths,
  tables, active connection state or inferred database relationships.
- Simple discovered internal imports/relative imports. Unresolved or third-party
  imports do not become internal edges; this is not a generalized dependency graph.

Clear rebinding, including assignment expressions and supported attribute
replacement, invalidates confident bindings. Known local-library collisions from
discovery make identities ambiguous. There is no generalized import/source-root
resolution, data-flow engine or arbitrary cross-file client resolver.

`SourceLocation` is immutable: relative file, one-based line, optional zero-based
UTF-8 byte column from AST. These columns are not character indexes.

`ExternalService.source_locations` support service presence (imports, construction,
possibly supported calls); `call_sites` identify concrete supported API expressions.
The latter are inputs a verification tool may inspect. Neither field proves a
runtime call happened or establishes an API-handler relationship by co-occurrence.

## Source-declared ExecutionFlow

Components, structural dependencies and ExecutionFlow are separate concepts.
Each step and transition retains source locations. Flow facts are possible source
control flow, not Verification Evidence, verification Trace or runtime observations.

The finite grammar covers an explicitly imported StateGraph in a named local
factory, simple graph binding, literal node registration, explicit entry/add_edge,
literal add_conditional_edges mappings with named conditions, and direct return of
`graph.compile()`. START and END are boundaries; conditions are never evaluated.
Unsupported dynamic declarations fail closed.

A bounded cross-file association supports a FastAPI handler's direct invocation
of an explicitly imported binding initialized by the proven local factory. Proof
retains route, import, invoke, graph construction/compile and exported binding
locations. A supported normal return consuming the unchanged result can add the
handler return; exception paths and actual successful execution are not proved.

Candidate tools require a directly imported literal list/tuple iterated in the
registered handler with explicit loop-variable invoke. They are a set, never tool
ordering or per-request selection. Arbitrary cross-file calls, factories, re-exports,
mutating collections, nested captures and inferred side effects are unsupported.
OpenAI/SQLite helper participation is not linked without supported proof.

## Graph projection and UI

`project_architecture_graph(ir)` is a pure projection: no source reads or further
architecture inference. Stable IDs and canonical ordering support repeatable dumps.
Current component types are FRAMEWORK, API_ROUTE, EXTERNAL_SERVICE, MODULE, TOOL,
DATASTORE. Exact repeated facts merge; source locations are retained honestly.

Architecture subject IDs are opaque server-generated identifiers tied to the
architecture snapshot. Use existing generators and supplied indexes; do not
construct IDs manually or parse them for semantics. Identity is repeatable for
identical inputs, not guaranteed persistent across source moves or revisions.

Dependency projection includes modules represented by internal dependency
endpoints; it is not a complete module inventory or generalized runtime graph.
Dependency View shows MODULE + source-backed IMPORTS. System Flow uses explicit
ExecutionFlow transitions, with source-defined condition labels in the Inspector.
IMPORTS do not become execution. Co-located components create no CALLS/CONTAINS
edges. Framework source references may be unavailable under the current schema.

System Flow is the default. Tool Execution remains one primary step with candidate
tools in its Inspector. Unproven external-service/datastore participation remains
under Other detected components, unconnected. UI labels/edge geometry may be
simplified for readability while original identities, conditions and references
remain inspectable. React Flow state/layout belongs only to frontend adapters.

## M4.5 normalized input and eligible options

Discovery accepts ArchitectureIR, never a repository path. Normalization reuses
projected component and ExecutionFlow IDs. Step IDs occur only within flow facts.
It retains routes, presence/concrete-call distinctions, tools, datastores, declared
flow steps/transitions/conditions/candidates and source limitations without adding
relationships. MODULE presence does not imply execution.

Input version is `evaluation-discovery-input-v2`; prompt version is
`evaluation-option-selection-v2`; catalog version is `engineering-evaluations-v1`.
Default budgets: 128 subjects, 1024 objects, 512 characters per repository-derived
string and 64 KiB canonical UTF-8 JSON including catalog/options. Trusted static
catalog text is exempt from the repository-string cap, not the total byte cap.
Whole subjects/options are omitted when necessary; identifiers are never shortened.
Flows with omitted component/tool references are omitted. Truncation is visible
and propagated, never evidence of absence. A fixed envelope that cannot fit fails.

Ordering is canonicalized. SHA-256 covers normalized architecture, catalog,
versions and limitation flags, excluding architecture_id and derived options.
Option IDs hash that snapshot ID with evaluation/rationale/subject bindings.
Options reference the snapshot, avoid circular hashing, and count toward input
budgets. Changing the discovery input version legitimately changes the hash.

The server uses existing catalog predicates to construct eligible options before
generation. A request-specific schema enum allows only supplied option IDs; output
is `{"selected_option_ids": [...]}`. An empty selection is valid. Options are legal
opportunities, not automatic recommendations. See the catalog for exact bindings.

Validation checks schema, known/unique IDs, snapshot consistency and deterministic
option rebuild. Expansion still checks catalog IDs, subject IDs/kinds and rationale
signals. Invalid responses fail as a whole. Candidate metadata, explanation,
applicability, mode, support, priority, required evidence and limitations are all
server-owned. Mixed selected direct/wrapper timeout opportunities merge into one
conservative UNKNOWN/PARTIAL candidate with unioned subjects and explanations.

## Provider boundary and observability

`StructuredGenerationClient` returns provider-independent structured data/status.
OpenAI is an optional SDK adapter using schema-constrained Responses parsing.
Trusted instructions are separate from repository-derived untrusted data. No tools
are available. Root, raw source/config, credentials, results and UI layout are absent.
Architecture metadata is transmitted during deliberate live use and may be sensitive.

Model name is configured; no universal temperature is assumed. Defaults are 30-second
timeout, no automatic retries, store=False, disabled provider input truncation and
2048 output tokens. Transport refusal/incomplete status is checked before parsing.
Provider/discovery failures such as missing API credentials/SDK, timeout, API
error, invalid output and semantic validation failure use controlled DiscoveryError
categories, never successful empty results. Opt-in test setup is separate: missing
repository/model variables can raise KeyError, missing credentials an AssertionError,
and invalid OpenAIConfig values a validation error before discovery begins.

Empty complete architecture may skip generation. Empty incomplete/truncated context
fails explicitly. Diagnostics hold bounded provider/model/request IDs, versions,
hash, selected IDs, outcome/category, latency and token usage. They retain no raw
provider text, credentials or chain-of-thought. Provider latency is not runtime Evidence.

Only the opt-in live test loads project-root dotenv in application/test code, with
override=False. Explicit Uvicorn --env-file startup may populate process environment. Routine
tests use fake clients or HTTP mocks; no network/key is required. Importing the
provider/domain/backend never implicitly loads dotenv or starts generation.

## M4 evidence and judgment

The verifier re-discovers scope, records analysis content hashes and revalidates
safe reads before inspecting already-supported call expressions. Per-call observations
and one scope manifest are immutable STATIC_ANALYSIS Evidence. The judge consumes
only those observations, checks provenance/manifest consistency, and applies the
exact policy in [evaluation-catalog.md](evaluation-catalog.md).

EngineeringRequirement preserves raw text. VerificationPlan subject links are
frozen. Evidence snapshots observed values as JSON; callers receive decoded copies,
and limitations are tuples. Verdict is frozen and references evidence IDs; the run
assembly validates those references against collected evidence. This does not add
a general cross-object resolver to shared schemas.

## Local HTTP boundary

`POST /api/analyze` accepts a tagged local/GitHub source (legacy repository_path is local-only) and
returns repository identity, ArchitectureIR, ArchitectureGraph and architecture_id
from the existing canonical evaluation normalizer. Validation and
sanitized errors remain in the API adapter. The Next.js proxy forwards requests
to the local backend; no implicit fixture fallback is permitted.

The backend accepts the two documented localhost browser origins, rejects other
explicit origins and should remain on loopback. This is not authentication,
multi-tenant isolation or a production service. There is no persistence or runtime executor. M7 adds public GitHub archive intake.

### Suggested Verifications (M5)

`POST /api/evaluations/discover` accepts source, expected_architecture_id and selection mode;
browser-authored IR/candidates and extra fields are rejected. It reuses safe
server analysis and the existing M4.5 public entry point. The expected ID is only
a freshness precondition: a mismatch with fresh normalized architecture returns
409/ANALYSIS_STALE before generation, with no candidates. Browser input never
replaces authoritative analysis. The dependency
`discovery_client` constructs the existing OpenAI adapter from process
OPENAI_API_KEY and VERISYS_DISCOVERY_MODEL; application code never loads dotenv.

The response contains candidates (id, name, category, reason, architecture_subject_ids,
applicability, priority, required_evidence, verification_mode, execution_support,
limitations, can_execute), architecture_id, catalog_version, limitations and input_truncated.
It excludes provider internals, prompts, option payloads, diagnostics, Evidence and
Verdict. Repository failures retain analysis errors; configuration errors return
503/DISCOVERY_CONFIGURATION_MISSING, provider errors 502 (timeout 504)/
DISCOVERY_PROVIDER_FAILED, and invalid discovery output/context returns
502/DISCOVERY_VALIDATION_FAILED. Unexpected adapter errors return sanitized
500/DISCOVERY_FAILED. Successful empty selection is HTTP 200 with candidates [].

The workspace mounts suggestions only after successful analysis. For remote input, an explicit Analyze action starts one automatic discovery after
analysis. Local development can use a deliberate Discover Verifications click. Ordinary
rerenders and StrictMode replay cannot duplicate provider requests. IDLE/DISCOVERING/READY/EMPTY/ERROR are separate. Starting any new analysis
unmounts suggestions, aborts the browser request and ignores late responses.
Abort does not guarantee cancellation of an already-running backend/provider call.
In-flight clicks are blocked. Discovery sends the displayed analysis ID; stale
responses clear suggestions and prompt explicit reanalysis without automatic retry.
The hash identifies bounded normalized architecture facts/options, not every source
byte; unrepresented changes may leave it unchanged. Filesystem reads are not atomic;
keep source stable. Successful suggestions match the displayed normalized snapshot.
No suggestion is a result, and no verifier runs. System Flow/Dependency View
continue to render only the existing architecture graph.

## Evaluation extension path

Catalog metadata → deterministic eligibility rules → eligible discovery options →
LLM option selection → deterministic candidate expansion/validation → verifier
registry lookup for executable capability.

- `verisys/evaluation/catalog.py` defines evaluation metadata and rationale codes.
- `verisys/evaluation/rules.py` owns signal checks and candidate policy;
  `options.py` constructs snapshot-bound eligible options.
- `contracts.py` defines selection contracts; `normalize.py` builds bounded input.
- `providers.py` adapts structured generation; `discovery.py` validates selections
  and expands candidates deterministically.
- `verisys/verification/registry.py` maps executable evaluation IDs to verifiers.
  Lookup does not execute them; tool/evidence/judge behavior stays in verification.

Adding an evaluation and adding a verifier are separate operations. Catalog
presence does not imply executable support. Eligibility does not belong in provider
code; providers determine neither applicability nor Evidence/Verdict. Coordinate
catalog identities, rationale rules, versioned contracts and tests when extending.

## Extension rules

Extend the same domain contracts deliberately. A new analyzer pattern needs source
proof and conservative failure behavior; a new verifier needs an explicit policy,
real observations and deterministic judgment where possible. Runtime execution
requires separate sandbox design. Do not scaffold generalized call graphs, agent
frameworks, databases, distributed queues or observability integrations merely
because the roadmap mentions them. Coordinate shared contract changes through PRs.

## Verification execution and result experience (M6)

`POST /api/evaluations/verify` accepts only source (or legacy local repository_path), evaluation_id and
expected_architecture_id. It performs fresh safe analysis and rejects snapshot
mismatches with 409/ANALYSIS_STALE before resolving or executing a verifier. Only
the existing catalog/registry timeout verifier is installed. It constructs its own
requirement/plan, freshly inspects source, collects immutable Evidence and applies
the existing deterministic Judge. No discovery/provider dependency is involved;
verification needs no API key. A second architecture ID check prevents publishing a
run whose independent analysis differs from the requested normalized snapshot.
This does not make filesystem inspection atomic or hash every source byte.

The narrow result DTO exposes evaluation identity, architecture_id, applicability,
execution_status, verification_mode, optional verdict_status and verdict evidence
IDs, policy, deterministic summary/counts/coverage, evidence provenance/observations,
limitations and factual trace summaries. The projection copies the Judge's recorded
coverage; it does not judge again. NOT_APPLICABLE retains no Verdict and no percentage.
Mixed missing/unknown remains VIOLATED with incomplete coverage. Tool exceptions
return sanitized 500/VERIFICATION_FAILED, never an engineering NOT_VERIFIABLE.
Unknown/unregistered evaluations return 400/VERIFICATION_UNSUPPORTED; malformed
requests return 400/VERIFICATION_BAD_REQUEST. Repository failures retain analysis errors.

Suggestions expose can_execute derived from installed catalog/registry capability,
independent of applicability and execution_support. UNKNOWN/PARTIAL timeout candidates
can run; other suggestions remain disabled. IDLE/RUNNING/RESULT/ERROR execution
states block duplicate requests. Reanalysis or new discovery clears old results;
abort/late-response guards protect the browser, without promising backend cancellation.
The frontend renders server-owned conclusions and source locations, with separate
missing/unknown styling and expandable evidence/trace. No excerpts are fabricated.

## Public GitHub intake and trigger modes (M7)

`repository/source.py` defines a discriminated RepositorySource: local path or HTTPS
GitHub owner/repository URL with optional ref. No schemes/hosts, credentials, ports,
queries, fragments, tree URLs or encoded path tricks outside this grammar are accepted.
`.git` suffix and trailing slash are canonicalized. An API request supplies exactly
one source; old repository_path is retained for local development compatibility.

`repository/github.py` owns acquisition behind an injectable materializer/fetcher.
It constructs HTTPS api.github.com metadata/commit URLs and codeload.github.com
archive URLs. Redirects and final hosts must match this exact allowlist. It sends no
credentials and disables implicit proxy routing. Public metadata must confirm
private=false. GitHub deliberately conflates private/not-found in unauthenticated
404 responses; the controlled error preserves that ambiguity.

Requested branch/tag/default branch is resolved to a full 40-character commit SHA.
Analyze returns URL, requested_ref, resolved_commit_sha and the pinned source.
Later requests require the full SHA and expected_architecture_id. They reacquire and
analyze that commit, never a moving ref; mismatched architecture stops generation
or verification. Architecture root identity is excluded by the existing normalizer;
public remote IR uses the URL instead of the private temp root. Relative source
references/graph facts remain unchanged. No temp path is returned to the browser.

Archives are gzip tar streams, not git checkouts. Only regular files/directories
under one archive prefix are materialized in a server-owned TemporaryDirectory.
Traversal, absolute/backslash paths, duplicate names, symlinks, hardlinks, sparse
and special files fail closed. No extractall, git, hooks, filters, submodule handling,
dependency installation or source execution exists. All exits clean the temporary
root, including provider/tool/analysis failure. Archive limitations cause acquisition
failure rather than silently claiming a complete repository.

Remote defaults (independent of Python discovery budgets): 20 MiB compressed
response, 100 MiB extracted payload, 5 MiB per file, 10,000 archive entries,
30-second request socket timeout plus a monotonic download deadline. Each read
checks the deadline; a blocking read remains bounded by the socket timeout.
Decoded tar headers/padding/trailing data are also bounded by extracted-byte budget
plus 2048 bytes per allowed entry and 1 MiB framing allowance. Gzip footer validation
remains enabled. Limits are configurable for offline tests.

PROACTIVE preserves existing grounded discovery. ON_DEMAND supplies 1–2000 characters
of untrusted request_text in a separate SelectionInput envelope alongside unchanged
normalized architecture. The prompt matches only supplied eligible option IDs and
allows empty selection. Output schema, snapshot validation, expansion and every
candidate field remain server-owned. Request text changes selection intent, never
architecture identity or acceptance semantics; it is not a Requirement Compiler.
ON_DEMAND no-match is HTTP 200 with candidates=[], distinct from provider failure.
Selecting a performance concern cannot produce latency evidence without a verifier.

The URL form provides optional ref and mode; ON_DEMAND reveals the concern field.
The resolved short SHA is visible. Input/mode changes clear prior graph/suggestions/
results; new actions establish new snapshots. Automatic discovery is guarded against
StrictMode replay and ordinary rerenders; in-flight analysis/discovery/execution are
deduplicated. Explicit retry remains a separate user action. Verification receives
only the pinned source, expected architecture_id and evaluation_id; no provider call.
The existing local-only browser-origin/loopback boundary still applies: this is not
a hosted authenticated multi-tenant service. No private GitHub or other host support.
