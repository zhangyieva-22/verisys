import type { ArchitectureGraph } from "./types";

export type AnalysisResult = {
  repository: { name: string; path: string };
  graph: ArchitectureGraph;
  // Returned for consumers that need the IR. The renderer consumes the graph DTO.
  architecture: unknown;
};
export type AnalysisState = {
  status: "EMPTY" | "ANALYZING" | "READY" | "ERROR";
  result: AnalysisResult | null;
  error: string | null;
};
export type AnalysisAction = { type: "start" } | { type: "success"; result: AnalysisResult } | { type: "error"; message: string };
export const emptyAnalysis: AnalysisState = { status: "EMPTY", result: null, error: null };
export function analysisReducer(_state: AnalysisState, action: AnalysisAction): AnalysisState {
  if (action.type === "start") return { status: "ANALYZING", result: null, error: null };
  if (action.type === "success") return { status: "READY", result: action.result, error: null };
  return { status: "ERROR", result: null, error: action.message };
}

export async function analyzeRepository(path: string): Promise<AnalysisResult> {
  let response: Response;
  try {
    response = await fetch("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ repository_path: path }) });
  } catch {
    throw new Error("Cannot reach the local analysis backend. Check that it is running.");
  }
  let data;
  try { data = await response.json(); } catch { throw new Error("The local analysis backend did not return a valid response."); }
  if (!response.ok) throw new Error(typeof data?.error?.message === "string" ? data.error.message : "Repository analysis could not be completed.");
  if (typeof data?.repository?.name !== "string" || typeof data?.repository?.path !== "string" ||
    !Array.isArray(data?.graph?.nodes) || !Array.isArray(data?.graph?.edges) ||
    !Array.isArray(data?.graph?.execution_flows) || !Array.isArray(data?.graph?.limitations)) {
    throw new Error("The local analysis backend returned an invalid analysis result.");
  }
  return data as AnalysisResult;
}
