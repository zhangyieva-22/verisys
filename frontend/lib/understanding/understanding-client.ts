import { apiErrorMessage } from "../api-errors";
import { sourceBody, type RepositorySource } from "../repository-source";
import { refreshBody, validStored, type StoredResult } from "../stored";
// Manually mirrored API DTO. Every claim is model-inferred and never verified.
export type ExcerptKind = "README" | "DOCUMENT" | "MANIFEST" | "ROUTE_SOURCE" | "INTEGRATION_SOURCE" | "ENTRY_POINT" | "TEST_INDEX";
export type Citation = { path: string; start_line: number; end_line: number; quote: string; excerpt_kind: ExcerptKind };
export type InferredRequirement = { id: string; title: string; description: string; citations: Citation[]; status: "INFERRED_NOT_VERIFIED" };
export type RiskCategory = "security" | "reliability" | "performance" | "data" | "maintainability" | "operability";
export type InferredRisk = InferredRequirement & { category: RiskCategory; severity: "high" | "medium" | "low" };
export type SourceSummary = { path: string; kind: ExcerptKind; first_line: number; last_line: number; line_count: number; truncated: boolean };
export type UnderstandingResult = {
  architecture_id: string; provider: string; model: string; prompt_version: string;
  functional_requirements: InferredRequirement[]; risks: InferredRisk[]; sources: SourceSummary[];
  limitations: string[]; input_truncated: boolean; rejected_claims: number; rejected_citations: number;
  stored?: StoredResult | null;
};
export type UnderstandingState =
  | { status: "IDLE" | "GENERATING"; result: null; error: null }
  | { status: "READY"; result: UnderstandingResult; error: null }
  | { status: "ERROR"; result: null; error: string; stale: boolean };
export const idleUnderstanding: UnderstandingState = { status: "IDLE", result: null, error: null };

const KINDS = ["README", "DOCUMENT", "MANIFEST", "ROUTE_SOURCE", "INTEGRATION_SOURCE", "ENTRY_POINT", "TEST_INDEX"];
const CATEGORIES = ["security", "reliability", "performance", "data", "maintainability", "operability"];
const count = (value: unknown) => Number.isInteger(value) && (value as number) >= 0;
const line = (value: unknown) => Number.isInteger(value) && (value as number) >= 1;
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object";
export function citation(value: unknown): value is Citation {
  return record(value) && typeof value.path === "string" && typeof value.quote === "string" && line(value.start_line) &&
    line(value.end_line) && (value.end_line as number) >= (value.start_line as number) && KINDS.includes(String(value.excerpt_kind));
}
function claim(value: unknown): value is InferredRequirement {
  return record(value) && ["id", "title", "description"].every(key => typeof value[key] === "string") &&
    value.status === "INFERRED_NOT_VERIFIED" && Array.isArray(value.citations) && value.citations.length > 0 && value.citations.every(citation);
}
function risk(value: unknown): value is InferredRisk {
  return claim(value) && CATEGORIES.includes(String((value as Record<string, unknown>).category)) &&
    ["high", "medium", "low"].includes(String((value as Record<string, unknown>).severity));
}
function source(value: unknown): value is SourceSummary {
  return record(value) && typeof value.path === "string" && KINDS.includes(String(value.kind)) && line(value.first_line) &&
    line(value.last_line) && count(value.line_count) && typeof value.truncated === "boolean";
}
export function validUnderstanding(data: unknown): data is UnderstandingResult {
  return record(data) && ["architecture_id", "provider", "model", "prompt_version"].every(key => typeof data[key] === "string") &&
    Array.isArray(data.functional_requirements) && data.functional_requirements.every(claim) &&
    Array.isArray(data.risks) && data.risks.every(risk) && Array.isArray(data.sources) && data.sources.every(source) &&
    Array.isArray(data.limitations) && data.limitations.every(item => typeof item === "string") &&
    typeof data.input_truncated === "boolean" && count(data.rejected_claims) && count(data.rejected_citations) && validStored(data.stored);
}
export class UnderstandingApiError extends Error {
  constructor(message: string, readonly code: string) { super(message); }
}
export async function generateUnderstanding(source: RepositorySource | string, architectureId: string, signal: AbortSignal, refresh = false): Promise<UnderstandingResult> {
  let response: Response;
  try {
    response = await fetch("/api/understanding", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...sourceBody(source), expected_architecture_id: architectureId, ...refreshBody(refresh) }), signal,
    });
  } catch {
    throw new Error("Cannot reach the understanding service. Check the local backend connection.");
  }
  let data;
  try { data = await response.json(); }
  catch { throw new Error("Understanding returned an invalid response."); }
  if (!response.ok) {
    const code = typeof data?.error?.code === "string" ? data.error.code : "UNDERSTANDING_FAILED";
    throw new UnderstandingApiError(apiErrorMessage(code, typeof data?.error?.message === "string" ? data.error.message : "Understanding could not be completed."), code);
  }
  if (!validUnderstanding(data)) throw new Error("Understanding returned an invalid response.");
  if (data.architecture_id !== architectureId) throw new UnderstandingApiError(
    "The understanding snapshot differs from the displayed analysis. Analyze the repository again.", "ANALYSIS_STALE");
  return data;
}
