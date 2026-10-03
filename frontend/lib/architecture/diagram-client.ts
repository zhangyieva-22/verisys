import { apiErrorMessage } from "../api-errors";
import { sourceBody, type RepositorySource } from "../repository-source";
import { citation } from "../understanding/understanding-client";
import type { SourceSummary } from "../understanding/understanding-client";
import type { InferredComponent, InferredStep } from "./system-diagram";
import { LAYER_TITLES } from "./system-diagram";

// Manually mirrored API DTO for opt-in diagram enrichment; every item is inferred.
export type DiagramEnrichment = {
  architecture_id: string; provider: string; model: string; prompt_version: string;
  components: InferredComponent[]; request_path: InferredStep[]; sources: SourceSummary[];
  limitations: string[]; input_truncated: boolean; rejected_claims: number; rejected_citations: number;
};
export type EnrichmentState =
  | { status: "IDLE" | "ENRICHING"; result: null; error: null }
  | { status: "READY"; result: DiagramEnrichment; error: null }
  | { status: "ERROR"; result: null; error: string; stale: boolean };
export const idleEnrichment: EnrichmentState = { status: "IDLE", result: null, error: null };

const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object";
const cited = (value: Record<string, unknown>) => Array.isArray(value.citations) && value.citations.length > 0 && value.citations.every(citation);
export function validEnrichment(data: unknown): data is DiagramEnrichment {
  return record(data) && ["architecture_id", "provider", "model", "prompt_version"].every(key => typeof data[key] === "string") &&
    Array.isArray(data.components) && data.components.every(item => record(item) && typeof item.id === "string" &&
      typeof item.label === "string" && typeof item.detail === "string" && String(item.layer) in LAYER_TITLES &&
      item.status === "INFERRED_NOT_VERIFIED" && cited(item)) &&
    Array.isArray(data.request_path) && data.request_path.every(step => record(step) && typeof step.label === "string" &&
      step.status === "INFERRED_NOT_VERIFIED" && cited(step)) &&
    Array.isArray(data.sources) && Array.isArray(data.limitations) && data.limitations.every(item => typeof item === "string") &&
    typeof data.input_truncated === "boolean" && Number.isInteger(data.rejected_claims) && Number.isInteger(data.rejected_citations);
}
export class DiagramApiError extends Error {
  constructor(message: string, readonly code: string) { super(message); }
}
export async function enrichDiagram(source: RepositorySource | string, architectureId: string): Promise<DiagramEnrichment> {
  let response: Response;
  try {
    response = await fetch("/api/diagram/enrich", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...sourceBody(source), expected_architecture_id: architectureId }) });
  } catch {
    throw new Error("Cannot reach the diagram service. Check the local backend connection.");
  }
  let data;
  try { data = await response.json(); }
  catch { throw new Error("Diagram enrichment returned an invalid response."); }
  if (!response.ok) {
    const code = typeof data?.error?.code === "string" ? data.error.code : "DIAGRAM_FAILED";
    throw new DiagramApiError(apiErrorMessage(code, typeof data?.error?.message === "string" ? data.error.message : "Diagram enrichment could not be completed."), code);
  }
  if (!validEnrichment(data)) throw new Error("Diagram enrichment returned an invalid response.");
  if (data.architecture_id !== architectureId) throw new DiagramApiError(
    "The enrichment snapshot differs from the displayed analysis. Analyze the repository again.", "ANALYSIS_STALE");
  return data;
}
