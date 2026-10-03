// Server-reported reuse of a saved result; saved results are earlier runs, not new work.
export type StoredResult = { reused: boolean; saved_at: string | null };
export function validStored(value: unknown): boolean {
  if (value === undefined || value === null) return true;
  const v = value as Record<string, unknown>;
  return typeof value === 'object' && typeof v.reused === 'boolean' && (v.saved_at === null || typeof v.saved_at === 'string');
}
export function savedNote(stored: StoredResult | null | undefined): string | null {
  if (!stored?.reused) return null;
  const when = stored.saved_at ? new Date(stored.saved_at).toLocaleString() : 'an earlier run';
  return `Saved result from ${when} · reused without running again`;
}
/** Only send refresh when bypassing the saved result, so ordinary requests are unchanged. */
export const refreshBody = (refresh: boolean) => (refresh ? { refresh: true } : {});
