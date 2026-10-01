import "./dom-setup";
import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { render, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { demoGraph } from "../lib/architecture/demo";
import { analysisReducer, emptyAnalysis, analyzeRepository } from "../lib/architecture/analysis-client";

const originalFetch = globalThis.fetch;
const result = { repository: { name: 'payments-api', path: '/projects/payments-api' }, architecture: {}, graph: demoGraph };
async function workspace() {
  const { ArchitectureWorkspace } = await import('../components/architecture/ArchitectureGraph');
  return render(createElement(ArchitectureWorkspace));
}
function restore() { cleanup(); globalThis.fetch = originalFetch; }
function submit(ui: Awaited<ReturnType<typeof workspace>>) {
  fireEvent.click(ui.getByRole('button', { name: 'Analyze Repository' }));
  fireEvent.change(ui.getByLabelText('Local repository path'), { target: { value: '/projects/payments-api' } });
  fireEvent.click(ui.getByRole('button', { name: 'Analyze' }));
}

test('Analyze interaction exposes loading then replaces identity and feeds API-result views', async () => {
  let resolve!: (response: Response) => void;
  let submitted: unknown;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/analyze'); submitted = JSON.parse(String(options?.body));
    return await new Promise<Response>(done => { resolve = done; });
  };
  try {
    const ui = await workspace();
    assert.ok(ui.getByText('Understand your repository'));
    assert.equal(ui.queryByText('OFFLINE SNAPSHOT'), null);
    submit(ui);
    assert.ok(ui.getByRole('button', { name: 'Analyzing…' }).hasAttribute('disabled'));
    assert.deepEqual(submitted, { repository_path: '/projects/payments-api' });
    resolve(new Response(JSON.stringify(result), { status: 200 }));
    await waitFor(() => assert.ok(ui.getByText('REAL ANALYSIS')));
    assert.equal(ui.getAllByText('payments-api').length, 2);
    assert.ok(ui.getByText('Agent Workflow'));
    assert.ok(ui.getByText('7 candidate tools'));
    assert.equal(ui.queryByText('m-peker/ecommerce-ai-agent'), null);
    assert.ok(ui.getByText('Analysis limitations (40)'));
    fireEvent.click(ui.getByRole('button', { name: 'Dependency View' }));
    assert.equal(ui.container.querySelectorAll('.react-flow__node').length, 14);
  } finally { restore(); }
});

test('controlled errors show ERROR and never substitute a fixture', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ error: { code: 'REPOSITORY_NOT_FOUND', message: 'Repository path does not exist.' } }), { status: 404 });
  try {
    const ui = await workspace(); submit(ui);
    await waitFor(() => assert.ok(ui.getByText('Analysis failed')));
    assert.ok(ui.getAllByText('Repository path does not exist.').length > 0);
    assert.equal(ui.queryByText('Agent Workflow'), null);
    assert.equal(ui.queryByText('REAL ANALYSIS'), null);
    assert.equal(ui.container.querySelectorAll('.react-flow__node').length, 0);
  } finally { restore(); }
});

test('empty execution flows remain READY with dependencies and current limitation count', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ ...result, graph: { ...demoGraph, execution_flows: [], limitations: ['A current source limitation.'] } }), { status: 200 });
  try {
    const ui = await workspace(); submit(ui);
    await waitFor(() => assert.ok(ui.getByText('REAL ANALYSIS')));
    assert.ok(ui.getByText('No supported source-declared execution flow was detected. Inspect structural dependencies in Dependency View.'));
    assert.ok(ui.getByText('Analysis limitations (1)'));
    assert.ok(ui.getByText('A current source limitation.'));
    fireEvent.click(ui.getByRole('button', { name: 'Dependency View' }));
    assert.equal(ui.container.querySelectorAll('.react-flow__node').length, 14);
  } finally { restore(); }
});

test('new request and failure clear old results; network failure is controlled', async () => {
  const ready = analysisReducer(emptyAnalysis, { type: 'success', result });
  assert.equal(ready.status, 'READY');
  assert.deepEqual(analysisReducer(ready, { type: 'start' }), { status: 'ANALYZING', result: null, error: null });
  assert.equal(analysisReducer(ready, { type: 'error', message: 'Failure' }).result, null);
  globalThis.fetch = async () => { throw new Error('private socket stack'); };
  try { await assert.rejects(analyzeRepository('/projects/payments-api'), /Cannot reach the local analysis backend/); }
  finally { restore(); }
});
