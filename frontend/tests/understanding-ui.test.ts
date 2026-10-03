import "./dom-setup";
import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { render, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { UnderstandingView } from "../components/understanding/UnderstandingView";
import { generateUnderstanding, validUnderstanding, type UnderstandingResult } from "../lib/understanding/understanding-client";

const originalFetch = globalThis.fetch;
const architectureId = 'a'.repeat(64);
const citation = { path: 'app/main.py', start_line: 5, end_line: 6, quote: '@app.post("/orders")', excerpt_kind: 'ROUTE_SOURCE' } as const;
const result: UnderstandingResult = {
  architecture_id: architectureId, provider: 'openai', model: 'fixture-model', prompt_version: 'understanding-claims-v1',
  functional_requirements: [{ id: 'r1', title: 'Place orders', description: 'Customers create orders.', citations: [citation], status: 'INFERRED_NOT_VERIFIED' }],
  risks: [
    { id: 'k1', title: 'Verbose errors', description: 'Errors may leak details.', citations: [citation], status: 'INFERRED_NOT_VERIFIED', category: 'security', severity: 'low' },
    { id: 'k2', title: 'Payment call without timeout', description: 'The charge call can hang.', citations: [{ ...citation, start_line: 8, end_line: 8 }], status: 'INFERRED_NOT_VERIFIED', category: 'reliability', severity: 'high' }],
  sources: [{ path: 'README.md', kind: 'README', first_line: 1, last_line: 2, line_count: 2, truncated: false }],
  limitations: ['Claims are inferred.'], input_truncated: false, rejected_claims: 1, rejected_citations: 2,
};
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
function restore() { cleanup(); globalThis.fetch = originalFetch; }
const props = { source: '/projects/shop', architectureId, onAnalyze: () => {} };

test('client accepts only inferred claims with citations', () => {
  assert.ok(validUnderstanding(result));
  const requirement = result.functional_requirements[0];
  for (const broken of [
    { ...result, functional_requirements: [{ ...requirement, status: 'VERIFIED' }] },
    { ...result, functional_requirements: [{ ...requirement, citations: [] }] },
    { ...result, risks: [{ ...result.risks[0], severity: 'critical' }] },
    { ...result, functional_requirements: [{ ...requirement, citations: [{ ...citation, start_line: 0 }] }] },
    { ...result, rejected_claims: -1 },
  ]) assert.equal(validUnderstanding(broken), false);
});

test('client rejects a snapshot for another analysis', async () => {
  globalThis.fetch = async () => response({ ...result, architecture_id: 'b'.repeat(64) });
  try { await assert.rejects(generateUnderstanding('/projects/shop', architectureId, new AbortController().signal), /Analyze the repository again/); }
  finally { restore(); }
});

test('nothing is sent until the button is clicked; repeated clicks make one call', async () => {
  let calls = 0; let resolve!: (r: Response) => void;
  globalThis.fetch = async (url, options) => {
    calls++; assert.equal(url, '/api/understanding');
    assert.deepEqual(JSON.parse(String(options?.body)), { repository_path: '/projects/shop', expected_architecture_id: architectureId });
    return new Promise<Response>(done => { resolve = done; });
  };
  try {
    const ui = render(createElement(UnderstandingView, props));
    assert.equal(calls, 0); assert.ok(ui.getByText(/Nothing is sent until you click/));
    const button = ui.getByRole('button', { name: 'Generate Understanding' });
    fireEvent.click(button); fireEvent.click(button);
    assert.equal(calls, 1); assert.ok(ui.getByRole('button', { name: 'Generating…' }).hasAttribute('disabled'));
    resolve(response(result));
    await waitFor(() => assert.ok(ui.getByText('Place orders')));
  } finally { restore(); }
});

test('every claim is labelled inferred and shows its citations; risks are ordered by severity', async () => {
  globalThis.fetch = async () => response(result);
  try {
    const ui = render(createElement(UnderstandingView, props));
    fireEvent.click(ui.getByRole('button', { name: 'Generate Understanding' }));
    await waitFor(() => assert.ok(ui.getByText('Place orders')));
    assert.equal(ui.getAllByText('Inferred — not verified').length, 3);
    assert.ok(ui.getAllByText('app/main.py:L5–L6').length >= 2);
    assert.ok(ui.getByText('app/main.py:L8'));
    const titles = [...ui.container.querySelectorAll('.inferred-claim[data-severity] h3')].map(node => node.textContent);
    assert.deepEqual(titles, ['Payment call without timeout', 'Verbose errors']);
    assert.ok(ui.getByText(/1 unsupported claim\(s\) dropped/));
    assert.ok(ui.getByText('What was sent to the model'));
    assert.ok(ui.getByRole('button', { name: 'Regenerate' }));
  } finally { restore(); }
});

test('empty results never imply absence of risk', async () => {
  globalThis.fetch = async () => response({ ...result, functional_requirements: [], risks: [] });
  try {
    const ui = render(createElement(UnderstandingView, props));
    fireEvent.click(ui.getByRole('button', { name: 'Generate Understanding' }));
    await waitFor(() => assert.ok(ui.getByText(/does not establish that the repository has no risks/)));
    assert.ok(ui.getByText(/No functional requirement was proposed/));
  } finally { restore(); }
});

test('stale analysis disables generation and offers re-analysis; configuration errors are explained', async () => {
  let analyzed = 0;
  globalThis.fetch = async () => response({ error: { code: 'ANALYSIS_STALE', message: 'stale' } }, 409);
  try {
    const ui = render(createElement(UnderstandingView, { ...props, onAnalyze: () => { analyzed++; } }));
    fireEvent.click(ui.getByRole('button', { name: 'Generate Understanding' }));
    await waitFor(() => assert.ok(ui.getByRole('alert')));
    assert.ok(ui.getByRole('button', { name: 'Generate Understanding' }).hasAttribute('disabled'));
    fireEvent.click(ui.getByRole('button', { name: /Analyze Repository again/ })); assert.equal(analyzed, 1);
  } finally { restore(); }
  globalThis.fetch = async () => response({ error: { code: 'UNDERSTANDING_CONFIGURATION_MISSING', message: 'x' } }, 503);
  try {
    const ui = render(createElement(UnderstandingView, props));
    fireEvent.click(ui.getByRole('button', { name: 'Generate Understanding' }));
    await waitFor(() => assert.ok(ui.getByText(/needs a configured model and API key/)));
  } finally { restore(); }
});

test('sidebar order is Overview, Understanding, Architecture, Verifications', async () => {
  const { AppSidebar } = await import('../components/layout/AppSidebar');
  try {
    const ui = render(createElement(AppSidebar, { section: 'Overview', onSelect: () => {} }));
    assert.deepEqual([...ui.container.querySelectorAll('.nav-item span')].map(node => node.textContent),
      ['Overview', 'Understanding', 'Architecture', 'Verifications']);
  } finally { cleanup(); }
});
