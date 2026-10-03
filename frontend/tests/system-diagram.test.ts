import "./dom-setup";
import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { demoGraph } from "../lib/architecture/demo";
import { buildSystemDiagram, mergeEnrichment, packageGroups, isTestModule, diagramIsEmpty } from "../lib/architecture/system-diagram";
import { validEnrichment, idleEnrichment, type DiagramEnrichment } from "../lib/architecture/diagram-client";
import { SystemDiagramView } from "../components/architecture/SystemDiagram";
import type { ArchitectureGraph } from "../lib/architecture/types";

const citation = { path: 'README.md', start_line: 2, end_line: 2, quote: 'A Next.js web app', excerpt_kind: 'README' } as const;
const enrichment: DiagramEnrichment = { architecture_id: 'a'.repeat(64), provider: 'openai', model: 'm', prompt_version: 'diagram-enrichment-v1',
  components: [
    { id: 'c1', layer: 'FRONTEND', label: 'Next.js web app', detail: 'Browser UI', citations: [citation], status: 'INFERRED_NOT_VERIFIED' },
    { id: 'c2', layer: 'AI_SERVICES', label: 'openai', detail: 'duplicate of detected', citations: [citation], status: 'INFERRED_NOT_VERIFIED' }],
  request_path: [{ label: 'Browser', citations: [citation], status: 'INFERRED_NOT_VERIFIED' }, { label: 'API', citations: [citation], status: 'INFERRED_NOT_VERIFIED' }],
  sources: [{ path: 'README.md', kind: 'README', first_line: 1, last_line: 3, line_count: 3, truncated: false }],
  limitations: ['Inferred.'], input_truncated: false, rejected_claims: 0, rejected_citations: 0 };

test('package grouping strips the shared prefix and hides tests', () => {
  assert.deepEqual([...packageGroups(['verisys.api.app', 'verisys.api.verification', 'verisys.repository.discovery', 'verisys.models'])],
    [['api', ['verisys.api.app', 'verisys.api.verification']], ['models', ['verisys.models']], ['repository', ['verisys.repository.discovery']]]);
  assert.deepEqual([...packageGroups(['app'])], [['app', ['app']]]);
  assert.ok(isTestModule('tests.test_api') && isTestModule('pkg.test_x') && !isTestModule('pkg.latest'));
});

test('detected diagram groups only existing graph facts into layers', () => {
  const diagram = buildSystemDiagram(demoGraph);
  const layer = (kind: string) => [...diagram.main, ...diagram.side].find(item => item.kind === kind)!;
  assert.deepEqual(diagram.main.map(item => item.kind), ['CLIENT', 'FRONTEND', 'API', 'PACKAGES', 'AI_SERVICES']);
  assert.equal(layer('CLIENT').items.length, 0); assert.equal(layer('FRONTEND').items.length, 0);
  const api = layer('API').items[0];
  assert.equal(api.chips.length, demoGraph.nodes.filter(node => node.type === 'API_ROUTE').length);
  assert.ok(layer('PACKAGES').items.length > 0 && layer('PACKAGES').items.every(item => item.origin === 'DETECTED'));
  assert.ok(layer('AI_SERVICES').items.some(item => item.label === 'Agent tools'));
  assert.ok([...diagram.main, ...diagram.side].flatMap(item => item.items).every(item => item.origin === 'DETECTED' && item.citations.length === 0));
  assert.equal(diagram.paths.length, 1); assert.equal(diagram.paths[0].origin, 'DETECTED');
  assert.ok(diagram.paths[0].steps.length > 2);
});

test('enrichment adds inferred items, never overrides detected labels, and adds a path', () => {
  const detected = buildSystemDiagram(demoGraph);
  const merged = mergeEnrichment(detected, enrichment.components, enrichment.request_path);
  const frontend = merged.main.find(layer => layer.kind === 'FRONTEND')!;
  assert.deepEqual(frontend.items.map(item => [item.label, item.origin]), [['Next.js web app', 'INFERRED']]);
  const aiLabels = merged.main.find(layer => layer.kind === 'AI_SERVICES')!.items.map(item => item.label.toLowerCase());
  assert.equal(aiLabels.filter(label => label === 'openai').length, 1);
  assert.equal(merged.paths.at(-1)!.origin, 'INFERRED');
  assert.ok(validEnrichment(enrichment));
  assert.equal(validEnrichment({ ...enrichment, components: [{ ...enrichment.components[0], status: 'DETECTED' }] }), false);
  assert.equal(validEnrichment({ ...enrichment, components: [{ ...enrichment.components[0], layer: 'MOON' }] }), false);
});

test('an empty graph yields an empty diagram', () => {
  const empty: ArchitectureGraph = { nodes: [], edges: [], limitations: [], execution_flows: [] };
  assert.ok(diagramIsEmpty(buildSystemDiagram(empty)));
});

test('view renders layers, marks inferred items and triggers enrichment only on click', () => {
  let enriched = 0; const selected: string[] = [];
  try {
    const diagram = mergeEnrichment(buildSystemDiagram(demoGraph), enrichment.components, enrichment.request_path);
    const ui = render(createElement(SystemDiagramView, { diagram, enrichment: { status: 'READY', result: enrichment, error: null },
      selected: null, onSelect: item => selected.push(item.label), onEnrich: () => { enriched++; } }));
    assert.equal(enriched, 0);
    assert.ok(ui.getByLabelText('Frontend layer')); assert.equal(ui.queryByLabelText('Client layer'), null);
    assert.equal(ui.container.querySelectorAll('.diagram-item[data-origin="INFERRED"]').length, 1);
    fireEvent.click(ui.getByText('Next.js web app')); assert.deepEqual(selected, ['Next.js web app']);
    fireEvent.click(ui.getByRole('button', { name: /Re-enrich/ })); assert.equal(enriched, 1);
    assert.ok(ui.getByText(/Missing layers mean not detected, not absent/));
  } finally { cleanup(); }
  try {
    const ui = render(createElement(SystemDiagramView, { diagram: buildSystemDiagram(demoGraph), enrichment: idleEnrichment, selected: null, onSelect: () => {}, onEnrich: () => {} }));
    assert.ok(ui.getByRole('button', { name: /Enrich with AI/ }));
    assert.ok(ui.getByText(/likely secrets redacted/));
  } finally { cleanup(); }
});
