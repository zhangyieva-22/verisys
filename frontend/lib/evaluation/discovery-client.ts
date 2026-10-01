// Manually mirrored narrow API DTO; candidate policy belongs to the backend.
export type SuggestedVerification = {
  id: string;
  name: string;
  category: string;
  reason: string;
  architecture_subject_ids: string[];
  applicability: "APPLICABLE" | "NOT_APPLICABLE" | "UNKNOWN";
  priority: "HIGH" | "MEDIUM" | "LOW";
  required_evidence: string[];
  verification_mode: "STATIC" | "RUNTIME" | "PERFORMANCE" | "INFRASTRUCTURE";
  execution_support: "SUPPORTED" | "PARTIAL" | "NOT_AVAILABLE";
  limitations: string[];
};
export type DiscoveryResult = {
  candidates: SuggestedVerification[];
  architecture_id: string;
  catalog_version: string;
  limitations: string[];
  input_truncated: boolean;
};
export type DiscoveryState =
  | { status: "IDLE" | "DISCOVERING"; result: null; error: null }
  | { status: "READY" | "EMPTY"; result: DiscoveryResult; error: null }
  | { status: "ERROR"; result: null; error: string; stale: boolean };
export const idleDiscovery: DiscoveryState = { status: "IDLE", result: null, error: null };

function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === "string");
}
function candidate(value: unknown): value is SuggestedVerification {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return ["id", "name", "category", "reason"].every(key => typeof v[key] === "string") &&
    ["architecture_subject_ids", "required_evidence", "limitations"].every(key => strings(v[key])) &&
    ["APPLICABLE", "NOT_APPLICABLE", "UNKNOWN"].includes(String(v.applicability)) &&
    ["HIGH", "MEDIUM", "LOW"].includes(String(v.priority)) &&
    ["STATIC", "RUNTIME", "PERFORMANCE", "INFRASTRUCTURE"].includes(String(v.verification_mode)) &&
    ["SUPPORTED", "PARTIAL", "NOT_AVAILABLE"].includes(String(v.execution_support));
}
export class DiscoveryApiError extends Error {
  constructor(message: string, readonly code: string) { super(message); }
}
export async function discoverVerifications(path: string, architectureId: string, signal: AbortSignal): Promise<DiscoveryResult> {
  let response: Response;
  try {
    response = await fetch("/api/evaluations/discover", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repository_path: path, expected_architecture_id: architectureId }), signal,
    });
  } catch {
    throw new Error("Cannot reach discovery. Check the local backend connection.");
  }
  let data;
  try { data = await response.json(); }
  catch { throw new Error("Discovery returned an invalid response."); }
  if (!response.ok) throw new DiscoveryApiError(typeof data?.error?.message === "string" ? data.error.message : "Discovery could not be completed.", typeof data?.error?.code === "string" ? data.error.code : "DISCOVERY_FAILED");
  if (!Array.isArray(data?.candidates) || !data.candidates.every(candidate) ||
    typeof data.architecture_id !== "string" || typeof data.catalog_version !== "string" ||
    typeof data.input_truncated !== "boolean" || !strings(data.limitations)) {
    throw new Error("Discovery returned an invalid response.");
  }
  if (data.architecture_id !== architectureId) throw new DiscoveryApiError(
    "The discovery snapshot differs from the displayed analysis. Analyze the repository again.", "ANALYSIS_STALE");
  return data as DiscoveryResult;
}
