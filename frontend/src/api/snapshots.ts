import type { SessionSummary, Snapshot } from "./types";

// Browser-side copy of each session's latest signed snapshot. On serverless
// hosting, instances do not share a database; if one has never seen a session,
// the client restores it from here and retries (see client.ts).
const PREFIX = "screenrag:snapshot:";

export function saveSnapshot(snapshot: Snapshot | null | undefined) {
  if (!snapshot) return;
  const current = loadSnapshot(snapshot.session_id);
  if (current && current.version > snapshot.version) return; // never go backwards
  try {
    localStorage.setItem(PREFIX + snapshot.session_id, JSON.stringify(snapshot));
  } catch {
    /* storage full or disabled: the session still works while the instance lives */
  }
}

export function loadSnapshot(sessionId: string): Snapshot | null {
  try {
    const raw = localStorage.getItem(PREFIX + sessionId);
    return raw ? (JSON.parse(raw) as Snapshot) : null;
  } catch {
    return null;
  }
}

export function forgetSnapshot(sessionId: string) {
  try {
    localStorage.removeItem(PREFIX + sessionId);
  } catch {
    /* ignore */
  }
}

/** Summaries of locally known sessions, for the history page. */
export function localSessionSummaries(roleTitles: Record<string, string>): SessionSummary[] {
  const out: SessionSummary[] = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (!key?.startsWith(PREFIX)) continue;
      const s = (JSON.parse(localStorage.getItem(key) ?? "null") as Snapshot | null)?.summary;
      if (!s) continue;
      out.push({
        id: s.id,
        candidate_name: s.candidate_name,
        role_id: s.role_id,
        role_title: s.role_title ?? roleTitles[s.role_id] ?? s.role_id,
        custom_role: s.role_id.startsWith("custom_"),
        status: s.status,
        mode: s.mode,
        created_at: s.created_at,
        updated_at: s.updated_at,
        completed_at: s.completed_at,
        overall_score: s.overall_score,
        progress: {
          planned: s.planned,
          primary_asked: s.primary_asked,
          asked: s.asked,
          answered: s.answered,
          skipped: s.skipped,
          follow_ups: s.follow_ups,
          current_difficulty_offset: s.difficulty_offset,
        },
      });
    }
  } catch {
    /* corrupted entry: ignore */
  }
  return out;
}
