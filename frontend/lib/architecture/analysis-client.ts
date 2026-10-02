import { sourceBody, type RepositorySource } from "../repository-source";
import type { ArchitectureGraph } from "./types";

export type AnalysisResult = {
  architecture_id: string;
  repository: { name: string; path: string | null; source?: RepositorySource; repository_url?: string | null; requested_ref?: string | null; resolved_commit_sha?: string | null };
  graph: ArchitectureGraph;
  // Returned for consumers that need the IR. The renderer consumes the graph DTO.
  architecture: unknown;
};
export type AnalysisState = {
  status: "EMPTY" | "ANALYZING" | "READY" | "ERROR";
  result: AnalysisResult | null;
  error: string | null;
};
export type AnalysisAction = { type: "clear" } | { type: "start" } | { type: "success"; result: AnalysisResult } | { type: "error"; message: string };
export const emptyAnalysis: AnalysisState = { status: "EMPTY", result: null, error: null };
export function analysisReducer(_state: AnalysisState, action: AnalysisAction): AnalysisState {
  if (action.type === "clear") return emptyAnalysis;
  if (action.type === "start") return { status: "ANALYZING", result: null, error: null };
  if (action.type === "success") return { status: "READY", result: action.result, error: null };
  return { status: "ERROR", result: null, error: action.message };
}

export async function analyzeRepository(source: RepositorySource | string): Promise<AnalysisResult> {
  let response: Response;
  try {
    response = await fetch("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sourceBody(source)) });
  } catch {
    throw new Error("Cannot reach the local analysis backend. Check that it is running.");
  }
  let data;
  try { data = await response.json(); } catch { throw new Error("The local analysis backend did not return a valid response."); }
  if (!response.ok) throw new Error(typeof data?.error?.message === "string" ? data.error.message : "Repository analysis could not be completed.");
  if (typeof data?.architecture_id !== "string" || !/^[0-9a-f]{64}$/.test(data.architecture_id) || typeof data?.repository?.name !== "string" || !(typeof data?.repository?.path === "string" || data?.repository?.path === null) ||
    !Array.isArray(data?.graph?.nodes) || !Array.isArray(data?.graph?.edges) ||
    !Array.isArray(data?.graph?.execution_flows) || !Array.isArray(data?.graph?.limitations)) {
    throw new Error("The local analysis backend returned an invalid analysis result.");
  }
  if (typeof source !== "string" && source.type === "github" &&
    (data.repository.source?.type !== "github" || typeof data.repository.resolved_commit_sha !== "string" ||
      !/^[0-9a-f]{40}$/.test(data.repository.resolved_commit_sha) || data.repository.source.ref !== data.repository.resolved_commit_sha ||
      ![source.url.replace(/\.git\/?$/, "").replace(/\/$/, "")].includes(data.repository.source.url) || data.repository.path !== null)) {
    throw new Error("The backend returned an invalid repository revision.");
  }
  return data as AnalysisResult;
}
