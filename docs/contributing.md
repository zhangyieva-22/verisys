# Contributing to Verisys

This guide is for human collaborators. [AGENTS.md](../AGENTS.md) defines shared
product/security invariants and coding-agent boundaries. [README.md](../README.md)
has local setup; [mvp-plan.md](mvp-plan.md) has current milestone status.

## Get oriented

Read the product specification and architecture before changing a layer. Inspect
the implementation/tests rather than assuming a roadmap capability is connected.
The local UI accepts public GitHub URL/ref input with PROACTIVE or ON_DEMAND discovery (M7); local-path intake remains a development/testing option.
M6 exposes the M4 timeout verifier through the local API/UI, and the `requests`/`httpx` timeout verifier uses the same path. Verification uses no provider; other suggested checks remain non-executable.

Install dependencies in your own Python environment and use `npm ci` in frontend.
Analyzed repositories do not need their dependencies installed and must never be
executed/imported by the static product. Store external clones and smoke-test outputs
outside Verisys; never add them to a PR.

## Branch and PR workflow

1. Agree on a small scope and acceptance behavior. Reference the milestone or issue
   in the PR; do not combine unrelated product changes.
2. Start a task branch from the shared main checkpoint. Coding-agent-created branches
   use `codex/<short-task-name>`; human contributors can use the team's agreed names.
3. Implement focused changes with behavior tests and relevant documentation.
4. Inspect the full diff/staged file list, run required checks and open a PR for review.
5. Resolve comments and merge through the agreed team process. Avoid direct pushes
   to shared main for routine collaboration and never force-push shared history.

This is a contribution workflow, not a claim that branch protection, CI gates or
CODEOWNERS are already configured. Automation can be added in a separately scoped
change. A coding agent should commit/push only when its user explicitly authorizes it.

## Coordinate shared boundaries

Package directories are responsibility boundaries, not exclusive ownership:

- Models/contracts: coordinate schema, enum, serialization and source-ID changes
  before overlapping work. Explain compatibility and migration in the PR.
- Repository/analyzer: preserve deterministic ordering, safe-read budgets and honest
  unsupported cases. New facts/relationships require source proof and false-positive tests.
- Graph/frontend: projection semantics and TypeScript DTOs must agree. Put layout
  changes in adapters, never domain IR. Do not update fixture semantics for prettier UI.
- Evaluation: catalog eligibility is deterministic; the LLM only selects option IDs.
  Add rules with conservative applicability/support and strict failure tests.
- Verification: acceptance policy, collected evidence and judgment stay separate.
  New executable capability requires real tools, explicit scope and focused tests.
- API: keep adapters thin. An approved Python core does not authorize an HTTP endpoint.

When simultaneous changes touch shared files, agree on a sequence/rebase strategy.
Preserve colleagues' uncommitted work; do not reset/delete changes you did not create.
Use separate checkouts/worktrees when concurrent tasks would conflict.

## Dependencies

Put required product dependencies in `pyproject.toml` base dependencies, test-only
libraries in `test`, and optional discovery SDK/local-development libraries in
`discovery`. Keep additions minimal and explain them in the PR. Frontend dependency
changes must include both `frontend/package.json` and `frontend/package-lock.json`;
use `npm ci` to reproduce the lockfile. Update canonical docs when contracts change.

## Validation

From the project root, with your environment active:

```sh
python -m pytest
git diff --check
```

For frontend changes, inside `frontend/`:

```sh
npm run typecheck
npm test
npm run build
```

Cross-layer contract changes need both sets. Routine tests use synthetic/static
fixtures, fake generation clients and HTTP mocks; no provider credentials or network
are required. The opt-in live test is skipped by default. Do not set
VERISYS_LIVE_DISCOVERY for routine validation; use `env -u VERISYS_LIVE_DISCOVERY
python -m pytest` on macOS/Linux if your shell previously enabled it.

### Discovery/provider tests

For discovery/provider changes, install the optional set from the project root:

```sh
python -m pip install -e '.[test,discovery]'
env -u VERISYS_LIVE_DISCOVERY python -m pytest
```

SDK adapter tests use `pytest.importorskip("openai")`; a base `.[test]` environment
can skip them. Review test skips and use the discovery set for this layer so mocked
adapter tests actually run. These tests require no credentials or live calls.
The live test must remain skipped during routine validation.

The golden static verification example is documented in README. Do not execute
fixture application code to validate source inspection. Existing real-repository
snapshots are offline data. Changes to snapshots should state repository identity,
commit, generation method and source grounding; do not copy code/secrets into them.

## Local credentials and live discovery

Copy the blank `.env.example` to project-root `.env`, then enter local values
without putting them in commands, chat, screenshots or shared notes. Required
variables are OPENAI_API_KEY and VERISYS_DISCOVERY_MODEL. The model is explicitly
configured; there is no default or automatic latest-model selection.

The live test loads the explicit project-root dotenv file **inside the opted-in
test only**, with override=False. Existing process values win. Putting a key or a
live opt-in flag into `.env` does not automatically start a test, provider call or
backend integration. Domain/provider/verification modules do not load dotenv.

To run deliberately against a separately available local repository:

```sh
VERISYS_LIVE_DISCOVERY=1 \
VERISYS_LIVE_REPOSITORY=/absolute/path/to/ecommerce-ai-agent \
python -m pytest tests/test_evaluation_live.py -s --tb=short
```

For the established ecommerce comparison, use the pinned checkout in
[the real-repository smoke test](#real-repository-smoke-test). Models may choose different valid
subsets; do not retry to obtain a desired recommendation set. Live failures should
report sanitized categories, not unrestricted provider error text or credentials.
Provider diagnostics are not Evidence or verification Trace. No verifier is run.

Normalized architecture metadata is sent to the configured provider. Raw source,
credentials, root/config values and results are excluded, but relative paths/names
can still reveal project information. Choose a repository you may send metadata for.

## Real-repository smoke test

Canonical repository: https://github.com/m-peker/ecommerce-ai-agent

Clone into a separate directory outside Verisys. Replace `/absolute/external/workspace`
with your own existing workspace; these commands do not install or execute the target:

```sh
git clone https://github.com/m-peker/ecommerce-ai-agent.git /absolute/external/workspace/ecommerce-ai-agent
git -C /absolute/external/workspace/ecommerce-ai-agent checkout --detach 3d38d5ab7fa0f27bd5c28488afa354abaf2577b4
git -C /absolute/external/workspace/ecommerce-ai-agent rev-parse HEAD
git -C /absolute/external/workspace/ecommerce-ai-agent status --short
```

HEAD must equal `3d38d5ab7fa0f27bd5c28488afa354abaf2577b4`; use a clean checkout.
For architecture smoke testing, start Verisys as described in README and analyze
this absolute path in the UI. Inspect the Dependency View, source grounding
and limitations. This requires no OpenAI key and never executes target code.
For core discovery smoke testing, install `.[test,discovery]` and deliberately run
the opt-in test above with VERISYS_LIVE_REPOSITORY pointing to this checkout.
For M5 HTTP/UI testing, start the backend with provider configuration in its process
environment, analyze this checkout and click Discover Verifications once. Discovery
sends normalized metadata, selects options and validates candidates; no verifier runs.

There is no checked-in snapshot-regeneration script or CLI. The existing public
Python path is `discover_repository` → `analyze_architecture` →
`project_architecture_graph`; their exports are in `verisys.repository` and
`verisys.architecture`. To intentionally refresh the offline fixture, serialize the
projected graph with `model_dump_json(indent=2)` into
`frontend/lib/architecture/ecommerce-agent.graph.json`. Verify the pinned clean
checkout first, inspect the JSON diff and source references, keep repository/commit
metadata in `frontend/lib/architecture/demo.ts` accurate, and run frontend validation.
Do not alter snapshot facts by hand for visual completeness. This is a reviewed
fixture update, not an automatic consequence of running a smoke test.

## Before staging or sharing

```sh
git status --short
git diff --check
git diff --cached --name-only
git diff --cached --check
git check-ignore .env
git ls-files -- .env
```

`.env` and secret-bearing `.env.*` must remain ignored and untracked. Only the blank
`.env.example` template is intended for Git. Ignore rules do not remove already
tracked files and do not guarantee a diff is secret-free: inspect new files and
staged content, too. Do not force-add secrets. If a real credential is accidentally
committed, stop sharing the change, rotate/revoke it and coordinate cleanup; deleting
it in a later commit does not remove it from history.

Never stage external clones, `/private/tmp` artifacts, node_modules, build output,
virtual environments, caches, private keys or actual provider credentials. Do not
print environment dumps or enable credential-bearing debug logs.

## PR and handoff content

Describe the concrete problem and resulting behavior for a reviewer who has not
seen the conversation. Include scope, contract/compatibility changes, exact checks,
known limitations and any fixture provenance. Distinguish planned behavior from
working code and discovery recommendations from engineering verdicts.

When handing work to another contributor, include branch/checkpoint, outstanding
uncommitted changes, files involved, completed tests and remaining approved scope.
Use concise structured summaries, never hidden model chain-of-thought. Documentation
changes should keep their responsibilities distinct: README for getting started,
product spec for intent, architecture for implementation contracts, catalog for
policy and milestone plan for status.

## Remote intake tests (M7)

Routine remote tests use bounded in-memory archives and injected fetchers/materializers;
no network, GitHub or provider credentials are required. Tests cover host validation,
links/traversal, byte/entry limits, stable error categories, cleanup, pinned revisions,
selection authority and remote execution of the unchanged timeout policy.
A public-repository smoke requires explicit authorization. Use the pinned ecommerce
commit above, at most one live proactive selection, and controlled on-demand
selection. Keep artifacts outside the checkout; never commit clones or credentials.
Backend startup still uses process configuration; no implicit dotenv loading added.
