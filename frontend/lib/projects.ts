import { validGitHubURL } from './repository-source';
import type { AnalysisResult } from './architecture/analysis-client';
import type { AnalysisIntent } from './repository-source';

export const PROJECTS_KEY = 'verisys.recent-projects.v1';
export type RecentProject = {
  url: string; requestedRef: string | null; sha: string; name: string;
  ownerRepository: string; architectureId: string; analyzedAt: string;
  mode: AnalysisIntent['mode'];
};
const bounded = (value: unknown, max: number): value is string => typeof value === 'string' && value.length > 0 && value.length <= max;
export function readProjects(storage: Pick<Storage, 'getItem'>): RecentProject[] {
  try {
    const data = JSON.parse(storage.getItem(PROJECTS_KEY) ?? '[]');
    if (!Array.isArray(data)) return [];
    const projects: RecentProject[] = [];
    for (const p of data.slice(0, 20)) {
      if (!p || !bounded(p.url, 512) || !validGitHubURL(p.url) ||
        !bounded(p.sha,40) || !/^[0-9a-f]{40}$/.test(p.sha) || !bounded(p.architectureId,64) || !/^[0-9a-f]{64}$/.test(p.architectureId) ||
        !bounded(p.name, 100) || p.ownerRepository !== p.url.replace('https://github.com/', '') ||
        !(p.requestedRef === null || (bounded(p.requestedRef, 256) && /^[A-Za-z0-9_][A-Za-z0-9_./-]*$/.test(p.requestedRef) && !p.requestedRef.includes('..') && !p.requestedRef.includes('//') && !p.requestedRef.endsWith('/'))) ||
        !bounded(p.analyzedAt, 32) || !Number.isFinite(Date.parse(p.analyzedAt)) || !['PROACTIVE','ON_DEMAND'].includes(p.mode) ||
        projects.some(item => item.url === p.url)) continue;
      // Explicit whitelist: storage can never inject IR, provider output or result authority.
      projects.push({url:p.url, requestedRef:p.requestedRef, sha:p.sha, name:p.name,
        ownerRepository:p.ownerRepository, architectureId:p.architectureId, analyzedAt:p.analyzedAt, mode:p.mode});
    }
    return projects;
  } catch { return []; }
}
export function writeProjects(storage: Pick<Storage, 'setItem'>, projects: RecentProject[]): boolean {
  try { storage.setItem(PROJECTS_KEY, JSON.stringify(projects.slice(0, 20).map(p => ({
    url:p.url, requestedRef:p.requestedRef, sha:p.sha, name:p.name, ownerRepository:p.ownerRepository,
    architectureId:p.architectureId, analyzedAt:p.analyzedAt, mode:p.mode,
  })))); return true; } catch { return false; }
}
export function recentProject(result: AnalysisResult, intent: AnalysisIntent): RecentProject | null {
  const repo = result.repository;
  if (repo.source?.type !== 'github' || !repo.resolved_commit_sha) return null;
  return {url:repo.source.url, requestedRef:repo.requested_ref ?? null, sha:repo.resolved_commit_sha,
    name:repo.name.split('/').pop()!, ownerRepository:repo.name, architectureId:result.architecture_id,
    analyzedAt:new Date().toISOString(), mode:intent.mode};
}
