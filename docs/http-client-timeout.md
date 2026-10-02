# Design: HTTP client timeout coverage (`requests` and `httpx`)

Status: **Implemented.** The four review decisions were accepted as recommended.
The normative contract is in [evaluation-catalog.md](evaluation-catalog.md#http-client-timeout-contract).

## Goal

Add a second executable static verification: every supported outbound HTTP call made with `requests` or `httpx` has a finite timeout.
It reuses the M4 evidence model (per-call observations plus one scope manifest), the deterministic judge and the existing verification API and UI.

This is the most valuable timeout check for typical Python services.
`requests` has no default timeout, so a call without one can block forever when a server stops responding.

## Library semantics

The policy follows each library's real behavior, verified against current sources (`requests` 2.34.2, `httpx` 0.28.1):

| | `requests` | `httpx` |
| --- | --- | --- |
| Default per-call timeout | `None` (wait forever) | 5 seconds |
| Client-level timeout | None; `Session` has no timeout setting | `Client(timeout=...)` / `AsyncClient(timeout=...)`, default 5 seconds |
| Client method without `timeout` | No timeout | Inherits the client's timeout |
| `timeout=None` | No timeout | Disables the timeout |
| Accepted values | Number, or `(connect, read)` tuple | Number, `httpx.Timeout(...)`, or `None` |

Because of these differences, one rule such as "no explicit per-call timeout means MISSING" would be wrong.
It would flag safe `httpx` code that relies on the 5-second default.

## Policy

Claim: *Every supported `requests` and `httpx` call site has a finite timeout.*

Each call gets one of the existing three statuses, plus a new `timeout_source` field that says where the finite timeout comes from:

| Situation | Status | `timeout_source` |
| --- | --- | --- |
| Positive finite numeric literal per call | CONFIGURED | `call` |
| `requests` `(connect, read)` tuple of positive finite literals | CONFIGURED | `call` |
| `httpx.Timeout(...)` whose arguments are all positive finite literals | CONFIGURED | `call` |
| `httpx` client method without `timeout`, client constructed with a positive literal timeout | CONFIGURED | `client` |
| `httpx` module function, or client method on a client constructed without `timeout` | CONFIGURED | `library_default` |
| `requests` call without `timeout` | MISSING | — |
| `timeout=None`, a `None` inside a tuple or `httpx.Timeout`, or an invalid literal (zero, negative, boolean, string) | MISSING | — |
| `httpx` client method without `timeout` on a client constructed with `timeout=None` | MISSING | — |
| Variable or other non-literal expression, `**kwargs`, or an `httpx` client whose constructor cannot be resolved | UNKNOWN | — |
| `requests` call on a session that has `.mount(...)` called on it | UNKNOWN (`custom_adapter`) | — |

The last rule avoids a common false positive.
Production code often mounts an `HTTPAdapter` subclass that adds a default timeout, so a call without `timeout` may still be safe.

The existing judge rules apply unchanged: any MISSING call gives VIOLATED; any UNKNOWN call or incomplete scope gives NOT_VERIFIABLE; otherwise VERIFIED.
As with the OpenAI policy, finding violations does not require complete scope, but VERIFIED does.

## Supported call patterns

- `requests`: module functions `get`, `options`, `head`, `post`, `put`, `patch`, `delete` and `request`, and the same methods on a simple name bound to `requests.Session()` or `requests.session()`.
- `httpx`: the same module functions plus `stream`, and the same methods on a simple name bound to `httpx.Client(...)` or `httpx.AsyncClient(...)`, including inside `await`.
- Unsupported, reported as a limitation: `httpx` `.send()` (its timeout comes from `build_request`), clients held in attributes or passed in as parameters, `functools.partial`, wrapper functions, and dynamic method names.

The existing binding rules apply: aliased imports work, and rebinding or local-module collisions make an identity ambiguous.

## Analyzer changes

### New service family

`requests` and `httpx` join the analyzer's service table as `ExternalService(name="Outbound HTTP", client_library="requests" | "httpx")`.
Imports and client construction count as presence; supported calls are recorded as `call_sites`, with the same split between presence and calls as for OpenAI.
Client bindings keep a reference to their constructor call, so the verifier can inspect the client-level `timeout` argument.

### `with` and `async with` blocks

The analyzer currently skips every `with` body with the limitation "With service/route bindings are unsupported; body not inspected".
`with httpx.Client() as client:` is the standard `httpx` usage, so without a change most `httpx` calls would be invisible.

Proposed change: inspect `with` and `async with` bodies like straight-line code.
`with <supported constructor>(...) as <simple name>:` binds that name for the body, and other `as` targets clear any binding of their names, as an assignment does.

This changes existing results: OpenAI calls inside `with` blocks become visible, and the "body not inspected" limitation disappears for them.
Their OpenAI timeout result may change, for example from NOT_VERIFIABLE to VERIFIED or VIOLATED.
That is more accurate, but it is a visible change to an existing policy's results.

## Catalog and discovery

- New entry `http-client-timeout-coverage-v1`: category Reliability, mode STATIC, `verifier_available=True`.
- Rationales: `supported_http_client_calls` (APPLICABLE, SUPPORTED) and `http_client_presence` (presence without supported calls: UNKNOWN, PARTIAL), mirroring the OpenAI direct-call and wrapper rules.
- Catalog version becomes `engineering-evaluations-v2`; the selection bound grows from five to six options.
- The catalog is part of the hashed discovery input, so **every** `architecture_id` changes once with v2, not only those of repositories using `with` or HTTP clients.
  Open sessions get the existing stale-analysis error until they analyze again; recent repositories always reanalyze when reopened.
- The existing `external-api-timeout-coverage-v1` entry, claim and verifier stay unchanged.

## Verification and evidence

- New tool ID `python-static-http-timeout-v1`, registered in `verification/registry.py`.
- Per-call observations keep the M4 shape, adding `timeout_source`, and record `timeout_literal` as a number or a `[connect, read]` pair.
- The scope manifest, hash checks, exact call-location matching and completeness rules are shared with the OpenAI verifier.
  The shared parts move into a common module instead of being copied.
- `judge_timeouts` takes the policy and tool IDs as parameters; its decision rules do not change.

## Frontend

The existing verification result panel shows the counts and per-call observations.
It gains a label for `timeout_source`, so the user can see which calls rely on the `httpx` 5-second default.
DTO changes are limited to that optional field.

## Out of scope

- `urllib.request`, `urllib3`, `aiohttp`, gRPC and other clients.
- Timeouts set through custom adapters, environment variables or wrappers; these become UNKNOWN, never CONFIGURED.
- Whether the timeout value is appropriate; any positive finite value passes.
- Retries, connection pools and runtime behavior.
- Reading dependency manifests to confirm the installed library version; `library_default` reports the documented default of current releases as a limitation.

## Tests

- Status table: one test per row, for each library, sync and async.
- Binding: aliases, sessions and clients, rebinding, local `requests.py` or `httpx.py` collisions, client constructor resolution, `.mount(...)`.
- `with` support: client binding, scoping after the block, OpenAI calls inside `with` now detected, other `as` targets.
- Discovery: new rationales, presence-only partial support, the six-option bound and catalog v2.
- Verifier and judge: VERIFIED, VIOLATED and NOT_VERIFIABLE end to end, stale-source detection, and an OpenAI regression showing identical results for repositories without `with` blocks.
- API and frontend: executing the new evaluation and showing `timeout_source`.

## Decisions for review

1. **Separate evaluation instead of extending the OpenAI one.**
   Recommendation: separate, so the existing claim, ID and results stay stable and each policy states exactly what it covers.
2. **Should the `httpx` 5-second default count as CONFIGURED?**
   Recommendation: yes, with `timeout_source="library_default"` shown in the UI.
   The alternative (strict: explicit timeouts only) would mark most `httpx` code as VIOLATED even though it cannot hang forever.
3. **Inspect `with` / `async with` bodies.**
   Recommendation: yes; without it the `httpx` check is mostly blind.
   It changes some existing OpenAI results and architecture IDs, as described above.
4. **Treat sessions with `.mount(...)` as UNKNOWN.**
   Recommendation: yes, to avoid false VIOLATED results for the timeout-adapter pattern.
