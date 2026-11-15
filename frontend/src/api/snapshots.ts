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

interface SnapshotData {
  session: {
    id: string;
    candidate_name: string;
    role_id: string;
    status: SessionSummary["status"];
    created_at: string;
    updated_at: string;
    completed_at: string | null;
    plan: unknown[];
    difficulty_offset: number;
  };
  questions: { kind: string; status: string }[];
  report: { data: { overall_score?: number } } | null;
}

/** Summaries of locally known sessions, for the history page. */
export function localSessionSummaries(roleTitles: Record<string, string>): SessionSummary[] {
  const out: SessionSummary[] = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (!key?.startsWith(PREFIX)) continue;
      const snap = JSON.parse(localStorage.getItem(key) ?? "null") as Snapshot | null;
      if (!snap) continue;
      const json = atob(snap.body.replace(/-/g, "+").replace(/_/g, "/"));
      const data = JSON.parse(new TextDecoder().decode(Uint8Array.from(json, (c) => c.charCodeAt(0)))) as SnapshotData;
      const s = data.session;
      const qs = data.questions;
      out.push({
        id: s.id,
        candidate_name: s.candidate_name,
        role_id: s.role_id,
        role_title: roleTitles[s.role_id] ?? s.role_id,
        status: s.status,
        created_at: s.created_at,
        updated_at: s.updated_at,
        completed_at: s.completed_at,
        overall_score: data.report?.data?.overall_score ?? null,
        progress: {
          planned: s.plan.length,
          primary_asked: qs.filter((q) => q.kind === "primary").length,
          asked: qs.length,
          answered: qs.filter((q) => q.status === "answered").length,
          skipped: qs.filter((q) => q.status === "skipped").length,
          follow_ups: qs.filter((q) => q.kind === "follow_up").length,
          current_difficulty_offset: s.difficulty_offset,
        },
      });
    }
  } catch {
    /* corrupted entry: ignore */
  }
  return out;
}
