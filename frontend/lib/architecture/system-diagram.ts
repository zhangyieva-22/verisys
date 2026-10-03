/**
 * Layered system diagram: a presentation grouping of detected graph facts, optionally
 * merged with AI-inferred components. Detected items come only from the analysis graph;
 * inferred items keep their checked citations and are never mixed into detected facts.
 */
import type { ArchitectureGraph, ArchitectureNode, ExecutionFlow, SourceLocation } from './types';
import { callSites } from './types';
import { flowLabel } from '../overview/assessment';
import type { Citation } from '../understanding/understanding-client';

export type DiagramLayerKind = 'CLIENT' | 'FRONTEND' | 'API' | 'PACKAGES' | 'AI_SERVICES' | 'EXTERNAL_SERVICES' | 'DATA' | 'INFRASTRUCTURE';
export type DiagramOrigin = 'DETECTED' | 'INFERRED';
export type DiagramChip = { label: string; nodeId: string };
export type DiagramItem = {
  id: string; label: string; detail: string | null; origin: DiagramOrigin;
  /** Set when the item is exactly one graph node, so the existing Inspector can show it. */
  nodeId: string | null;
  sources: SourceLocation[]; citations: Citation[]; chips: DiagramChip[]; members: string[];
};
export type DiagramLayer = { kind: DiagramLayerKind; title: string; items: DiagramItem[] };
export type DiagramStep = { label: string; origin: DiagramOrigin; citations: Citation[]; sources: SourceLocation[] };
export type DiagramPath = { origin: DiagramOrigin; title: string; steps: DiagramStep[] };
export type SystemDiagram = { main: DiagramLayer[]; side: DiagramLayer[]; paths: DiagramPath[]; testModules: number };
export type InferredComponent = { id: string; layer: DiagramLayerKind; label: string; detail: string; citations: Citation[]; status: 'INFERRED_NOT_VERIFIED' };
export type InferredStep = { label: string; citations: Citation[]; status: 'INFERRED_NOT_VERIFIED' };

export const LAYER_TITLES: Record<DiagramLayerKind, string> = {
  CLIENT: 'Client', FRONTEND: 'Frontend', API: 'API', PACKAGES: 'Packages', AI_SERVICES: 'AI services',
  EXTERNAL_SERVICES: 'External services', DATA: 'Data', INFRASTRUCTURE: 'Infrastructure',
};
export const MAIN_LAYERS: DiagramLayerKind[] = ['CLIENT', 'FRONTEND', 'API', 'PACKAGES', 'AI_SERVICES'];
export const SIDE_LAYERS: DiagramLayerKind[] = ['EXTERNAL_SERVICES', 'DATA', 'INFRASTRUCTURE'];
const AI_LIBRARIES = new Set(['openai', 'langchain_openai']);
const MAX_PACKAGES = 8;

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`;
function detected(id: string, label: string, detail: string | null, nodes: ArchitectureNode[], extra: Partial<DiagramItem> = {}): DiagramItem {
  return { id, label, detail, origin: 'DETECTED', nodeId: nodes.length === 1 ? nodes[0].id : null,
    sources: nodes.flatMap(node => node.source_locations).slice(0, 5), citations: [], chips: [], members: [], ...extra };
}
export function isTestModule(name: string): boolean {
  const parts = name.split('.');
  return parts.some(part => part === 'tests' || part === 'test') || parts[parts.length - 1].startsWith('test_') || parts[parts.length - 1].endsWith('_test');
}

/** Group modules by the first segment after their longest shared prefix. */
export function packageGroups(names: string[]): Map<string, string[]> {
  const split = names.map(name => name.split('.'));
  let common = 0;
  while (split.length > 1 && split.every(parts => parts.length > common + 1 && parts[common] === split[0][common])) common++;
  const groups = new Map<string, string[]>();
  for (const parts of split) {
    const key = parts.length > common ? parts[common] : parts[parts.length - 1];
    groups.set(key, [...(groups.get(key) ?? []), parts.join('.')]);
  }
  return new Map([...groups.entries()].sort(([a], [b]) => a.localeCompare(b)));
}

function flowPath(flow: ExecutionFlow): DiagramPath {
  const steps = new Map(flow.steps.map(step => [step.id, step]));
  const ordered: string[] = []; const queue = flow.trigger ? [flow.trigger] : flow.steps.map(step => step.id);
  while (queue.length) {
    const id = queue.shift()!;
    if (ordered.includes(id) || !steps.has(id)) continue;
    ordered.push(id);
    queue.push(...flow.transitions.filter(t => t.source === id && t.target !== id).map(t => t.target));
  }
  return { origin: 'DETECTED', title: flow.name, steps: ordered.map(id => steps.get(id)!).map(step =>
    ({ label: flowLabel(step), origin: 'DETECTED', citations: [], sources: step.source_locations.slice(0, 3) })) };
}

export function buildSystemDiagram(graph: ArchitectureGraph): SystemDiagram {
  const of = (type: ArchitectureNode['type']) => graph.nodes.filter(node => node.type === type);
  const layers = new Map<DiagramLayerKind, DiagramItem[]>();
  const add = (kind: DiagramLayerKind, item: DiagramItem) => layers.set(kind, [...(layers.get(kind) ?? []), item]);

  const routes = of('API_ROUTE');
  const frameworks = of('FRAMEWORK');
  const chips = routes.map(route => ({ label: route.label, nodeId: route.id }));
  for (const framework of frameworks) add('API', detected(framework.id, framework.label, plural(routes.length, 'route'), [framework], { chips }));
  if (!frameworks.length && routes.length) add('API', detected('api:routes', 'HTTP routes', plural(routes.length, 'route'), routes, { chips }));

  const modules = of('MODULE');
  const product = modules.filter(node => !isTestModule(node.label));
  const groups = [...packageGroups(product.map(node => node.label)).entries()];
  for (const [name, members] of groups.slice(0, MAX_PACKAGES)) {
    const nodes = product.filter(node => members.includes(node.label));
    add('PACKAGES', detected(`package:${name}`, name, plural(members.length, 'module'), nodes, { members }));
  }
  if (groups.length > MAX_PACKAGES) {
    const rest = groups.slice(MAX_PACKAGES).flatMap(([, members]) => members);
    add('PACKAGES', detected('package:more', `+${groups.length - MAX_PACKAGES} more`, plural(rest.length, 'module'), [], { members: rest }));
  }

  for (const service of of('EXTERNAL_SERVICE')) {
    const calls = callSites(service).length;
    const detail = [service.subtitle, calls ? plural(calls, 'call site') : 'presence only'].filter(Boolean).join(' · ');
    add(AI_LIBRARIES.has(service.subtitle ?? '') ? 'AI_SERVICES' : 'EXTERNAL_SERVICES', detected(service.id, service.label, detail, [service]));
  }
  const tools = of('TOOL');
  if (tools.length) add('AI_SERVICES', detected('ai:tools', 'Agent tools', tools.map(tool => tool.label).slice(0, 4).join(', ') + (tools.length > 4 ? ` +${tools.length - 4}` : ''), tools));
  for (const flow of graph.execution_flows ?? []) add('AI_SERVICES', detected(`flow:${flow.id}`, flow.name, 'Source-declared workflow', [], { sources: flow.source_locations.slice(0, 3) }));
  for (const store of of('DATASTORE')) add('DATA', detected(store.id, store.label, store.subtitle, [store]));

  const layer = (kind: DiagramLayerKind): DiagramLayer => ({ kind, title: LAYER_TITLES[kind], items: layers.get(kind) ?? [] });
  return { main: MAIN_LAYERS.map(layer), side: SIDE_LAYERS.map(layer),
    paths: (graph.execution_flows ?? []).slice(0, 1).map(flowPath), testModules: modules.length - product.length };
}

/** Add inferred components and path; detected items always win on a label clash. */
export function mergeEnrichment(diagram: SystemDiagram, components: InferredComponent[], path: InferredStep[]): SystemDiagram {
  const merge = (layer: DiagramLayer): DiagramLayer => {
    const taken = new Set(layer.items.map(item => item.label.toLowerCase()));
    const inferred = components.filter(c => c.layer === layer.kind && !taken.has(c.label.toLowerCase())).map(c =>
      ({ id: c.id, label: c.label, detail: c.detail || null, origin: 'INFERRED' as const, nodeId: null, sources: [], citations: c.citations, chips: [], members: [] }));
    return { ...layer, items: [...layer.items, ...inferred] };
  };
  const paths = path.length > 1 ? [...diagram.paths, { origin: 'INFERRED' as const, title: 'Main request path',
    steps: path.map(step => ({ label: step.label, origin: 'INFERRED' as const, citations: step.citations, sources: [] })) }] : diagram.paths;
  return { ...diagram, main: diagram.main.map(merge), side: diagram.side.map(merge), paths };
}

export const diagramIsEmpty = (diagram: SystemDiagram) =>
  [...diagram.main, ...diagram.side].every(layer => !layer.items.length) && !diagram.paths.length;
