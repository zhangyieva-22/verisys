# Understanding layer: inferred requirements and risks

Status: **Implemented.**

## Purpose

Verification answers narrow questions with real evidence.
It cannot say what a system is for or where its risks are, because that needs reading code and documentation and interpreting them.
The understanding layer fills that gap: a language model proposes functional requirements and engineering risks, and every proposal cites the exact source text it relies on.

Every item is labelled **Inferred — not verified**.
A valid citation proves the quoted text exists at that location; it does not prove the claim is true.

## Accepted decisions

1. **The server picks the input; the model only reads it.** One model call per request, with a deterministic, size-limited selection.
2. **An explicit button triggers it.** Nothing is sent to the model until the user clicks Generate Understanding; analysis never triggers it.
3. **A separate Understanding section** in the project workspace shows the results, apart from verified results.

## Flow

Analyzed repository → excerpt selection and secret redaction → one structured model call → citation checks → inferred claims → Understanding section.

### Excerpt selection (`verisys/understanding/selection.py`)

Only files that discovery found are read, through the same safe readers as analysis.
Discovery records documentation and manifest paths (`.md`, `.rst`, `.txt`, `README*`, `package.json`, `pyproject.toml`, `setup.cfg`, `Dockerfile` and compose files) without reading them; they never affect source scope, limitations or `architecture_id`.

Priority order:

1. The root README.
2. Other documentation: root Markdown/reST files (except changelogs, licences and similar) and files under `docs/`, `doc/` or `documentation/`, up to six documents in total.
3. Manifests: `requirements.txt`, `package.json`, `pyproject.toml`, `setup.cfg`, `Dockerfile` and compose files, shallowest first, up to six files and 60 lines each.
4. Source around detected API routes (3 lines before to 40 after each route).
5. Source around detected external services, datastores and tools (5 lines before to 15 after).
6. Entry-point files such as `main.py`, `app.py`, `cli.py` and `manage.py` (first 80 lines).
7. A test index: only the `def test_…` and `class Test…` lines of up to 20 test files.

Default limits: 1500 lines and 96 KiB in total, 200 lines per excerpt, 400 characters per line.
Reaching a limit is reported as a limitation and sets `input_truncated`.

Likely secrets are replaced with `[REDACTED]` before anything is sent: OpenAI-style keys, AWS access keys, GitHub and Slack tokens, bearer tokens, private-key blocks, and quoted values assigned to names like `api_key`, `password`, `secret` or `token`.
Redaction is pattern-based and can miss secrets.
`.env` files are never read.

### Model call (`verisys/understanding/understand.py`)

The model receives trusted instructions, a short server-written architecture summary and the numbered excerpts.
Repository text is marked as untrusted data, and the model has no tools.
The response schema limits each citation's `excerpt_id` to the IDs actually sent.

The model is `VERISYS_UNDERSTANDING_MODEL`, or `VERISYS_DISCOVERY_MODEL` when that is unset; `OPENAI_API_KEY` is required.
The call uses a 90-second timeout and up to 6000 output tokens, and is never retried automatically.

### Citation checks

The server keeps a citation only if:

- its excerpt was sent;
- every line in its range was sent (so test-index citations are single lines);
- the range is at most 61 lines;
- its quote, after removing line-number prefixes and normalizing whitespace, is 3–300 characters and appears in the text of those lines.

A claim keeps its valid citations and is dropped if none remain, if its title or description is empty, or if it repeats an earlier title.
Risks also need a known category (security, reliability, performance, data, maintainability, operability) and severity (high, medium, low).
Dropped claims and citations are counted and reported, never repaired.

## API

`POST /api/understanding` takes the same repository source as discovery plus `expected_architecture_id`.
GitHub sources must be pinned to a full commit SHA, and a changed analysis returns `409 ANALYSIS_STALE` before any model call.
Errors: `503 UNDERSTANDING_CONFIGURATION_MISSING`, `502/504 UNDERSTANDING_PROVIDER_FAILED`, `502 UNDERSTANDING_VALIDATION_FAILED`.
If nothing can be selected, the response is empty and no model call is made.

The response contains `functional_requirements` and `risks` (each with `status: "INFERRED_NOT_VERIFIED"` and citations), `sources` (what was sent), `limitations`, `input_truncated`, and the counts of dropped claims and citations.

## System diagram enrichment

The Architecture tab's **System Diagram** view draws layers from detected facts only: API (frameworks and routes), Packages (internal modules grouped by the first segment after their shared prefix, tests hidden), AI services (OpenAI clients, agent tools, source-declared workflows), External services and Data.
That grouping is a frontend presentation of the analysis graph (`frontend/lib/architecture/system-diagram.ts`) and adds no facts.

**Enrich with AI** calls `POST /api/diagram/enrich`, which uses the same selection, redaction, model call and citation checks as understanding.
The model may add components to the layers CLIENT, FRONTEND, API, PACKAGES, AI_SERVICES, EXTERNAL_SERVICES, DATA and INFRASTRUCTURE, plus a request path of 2–8 steps.
Each component and step needs at least one valid citation; a request path with a single surviving step is dropped.
Inferred components are drawn with dashed borders and an "Inferred" mark, never replace a detected item with the same label, and are never added to the analysis graph.
Errors use the `DIAGRAM_` prefix with the same statuses as understanding.
The enrichment request is held by the project session, so leaving the Architecture tab neither cancels nor repeats it.

## Boundaries

- Inferred claims are never Evidence, never a Verdict, and never input to verification or discovery.
- The model cannot add files to its input or see anything outside the selected excerpts.
- Sending code to the model provider is a data-sharing decision: excerpts can contain proprietary logic, and redaction can miss secrets.
  Use it only on repositories whose code you may send to the configured provider.
- Results are saved locally and reused for the same pinned commit, `architecture_id`, model and prompt version; local-path requests always run again. See [saved results](architecture.md#saved-results).
