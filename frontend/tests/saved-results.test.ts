import "./dom-setup";
import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { render, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { SuggestedVerifications } from "../components/evaluation/SuggestedVerifications";
import { VerificationResult } from "../components/evaluation/VerificationResult";
import { savedNote, validStored } from "../lib/stored";

const originalFetch = globalThis.fetch;
const architectureId = 'a'.repeat(64);
const stored = { reused: true, saved_at: '2026-10-01T12:00:00+00:00' };
const candidate = { can_execute: false, id: 'api-latency-v1', name: 'API Latency', category: 'Performance', reason: 'Route.',
  architecture_subject_ids: ['route:x'], applicability: 'APPLICABLE', priority: 'MEDIUM', required_evidence: ['Load test'],
  verification_mode: 'PERFORMANCE', execution_support: 'NOT_AVAILABLE', limitations: [] };
const discovery = { architecture_id: architectureId, catalog_version: 'engineering-evaluations-v2', input_truncated: false, limitations: [], candidates: [candidate] };
const response = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });
function restore() { cleanup(); globalThis.fetch = originalFetch; }

test('stored metadata is optional and validated', () => {
  assert.ok(validStored(undefined) && validStored(null) && validStored({ reused: false, saved_at: null }));
  assert.equal(validStored({ reused: 'yes', saved_at: null }), false);
  assert.equal(savedNote({ reused: false, saved_at: '2026-10-01T12:00:00Z' }), null);
  assert.match(savedNote(stored)!, /^Saved result from .* reused without running again$/);
});

test('a reused discovery says so, and Regenerate bypasses the saved result', async () => {
  const bodies: Record<string, unknown>[] = [];
  globalThis.fetch = async (_url, options) => { bodies.push(JSON.parse(String(options?.body)));
    return response(bodies.length === 1 ? { ...discovery, stored } : { ...discovery, stored: { reused: false, saved_at: '2026-10-02T12:00:00+00:00' } }); };
  try {
    const ui = render(createElement(SuggestedVerifications, { repositoryPath: '/p', architectureId, onAnalyze: () => {} }));
    fireEvent.click(ui.getByRole('button', { name: 'Discover Verifications' }));
    await waitFor(() => assert.ok(ui.getByText(/Saved result from/)));
    assert.equal('refresh' in bodies[0], false);
    fireEvent.click(ui.getByRole('button', { name: 'Regenerate' }));
    await waitFor(() => assert.ok(ui.getByText('Fresh server-side analysis')));
    assert.equal(bodies[1].refresh, true);
  } finally { restore(); }
});

test('a reused verification result offers an explicit re-run', () => {
  let reruns = 0;
  const result = { evaluation_id: 'x', evaluation_name: 'Timeout', architecture_id: architectureId, applicability: 'APPLICABLE',
    execution_status: 'COMPLETED', verification_mode: 'STATIC', verdict_status: 'VERIFIED', verdict_evidence_ids: [], policy: 'p',
    summary: 's', counts: { configured: 1, missing: 0, unknown: 0, total: 1 }, coverage_complete: true, coverage_percent: 100,
    evidence: [], limitations: [], trace: [], stored } as const;
  try {
    const ui = render(createElement(VerificationResult, { result: { ...result, evidence: [], limitations: [], trace: [], verdict_evidence_ids: [] }, onRerun: () => { reruns++; } }));
    assert.ok(ui.getByText(/Saved result from/));
    fireEvent.click(ui.getByRole('button', { name: 'Re-run verification' })); assert.equal(reruns, 1);
  } finally { restore(); }
  try {
    const ui = render(createElement(VerificationResult, { result: { ...result, evidence: [], limitations: [], trace: [], verdict_evidence_ids: [], stored: { reused: false, saved_at: null } } }));
    assert.equal(ui.queryByText(/Saved result from/), null);
  } finally { restore(); }
});
