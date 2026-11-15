import type { AnswerTelemetry } from "../state/useAnswerTelemetry";
import { forgetSnapshot, loadSnapshot, localSessionSummaries, saveSnapshot } from "./snapshots";
import type {
  AnswerResponse,
  Benchmark,
  Health,
  NextQuestionResponse,
  ReportResponse,
  RetrievalMode,
  Role,
  SearchResponse,
  SessionDetail,
  SessionSummary,
  Snapshot,
} from "./types";

const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "") + "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the server. Is the backend running?");
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const err = body?.error;
    throw new ApiError(
      response.status,
      err?.code ?? "http_error",
      err?.message ?? `Request failed (${response.status})`,
      err?.details ?? {},
    );
  }
  return body as T;
}

const json = (data: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});

/**
 * Session-scoped request with self-healing. The browser sends the version of its
 * latest snapshot; an API instance that does not know the session, or holds an
 * older copy, answers 404. The client then restores the session from its signed
 * snapshot and retries once. Newer snapshots in responses replace the stored one.
 */
async function sessionRequest<T>(sessionId: string, path: string, init: RequestInit = {}): Promise<T> {
  const call = () => {
    const snapshot = loadSnapshot(sessionId);
    const headers = new Headers(init.headers);
    if (snapshot) headers.set("X-Session-Version", String(snapshot.version));
    return request<T>(path, { ...init, headers });
  };
  const keep = (result: T) => {
    saveSnapshot((result as { snapshot?: Snapshot | null })?.snapshot);
    return result;
  };
  try {
    return keep(await call());
  } catch (e) {
    const snapshot = loadSnapshot(sessionId);
    if (!(e instanceof ApiError) || e.status !== 404 || !snapshot) throw e;
    // Restore and replay in ONE request: a separate restore call could land on
    // a different serverless instance than the retry.
    const original = typeof init.body === "string" ? init.body : null;
    const headers = new Headers({
      "Content-Type": "application/json",
      "X-Session-Restore": "1",
      "X-Original-Method": (init.method ?? "GET").toUpperCase(),
      "X-Session-Version": String(snapshot.version),
    });
    const envelope = {
      snapshot,
      body: original ? btoa(unescape(encodeURIComponent(original))) : null,
      content_type: original ? "application/json" : null,
    };
    return keep(await request<T>(path, { method: "POST", headers, body: JSON.stringify(envelope) }));
  }
}

export interface CreateSessionInput {
  roleId: string;
  candidateName: string;
  numQuestions: number;
  resumeFile?: File | null;
  resumeText?: string;
}

export const api = {
  health: () => request<Health>("/health"),
  roles: () => request<Role[]>("/roles"),
  /** Server sessions merged with the ones this browser holds snapshots for. */
  listSessions: async (roleTitles: Record<string, string> = {}) => {
    const remote = await request<SessionSummary[]>("/sessions");
    // Serverless instances can hold older copies: keep whichever copy of each
    // session has progressed further.
    const progressOf = (s: SessionSummary) =>
      2 * s.progress.asked + s.progress.answered + s.progress.skipped + (s.status === "completed" ? 1000 : 0);
    const merged = new Map<string, SessionSummary>();
    for (const s of [...remote, ...localSessionSummaries(roleTitles)]) {
      const current = merged.get(s.id);
      if (!current || progressOf(s) > progressOf(current)) merged.set(s.id, s);
    }
    return [...merged.values()].sort((a, b) => b.created_at.localeCompare(a.created_at));
  },
  getSession: (id: string) => sessionRequest<SessionDetail>(id, `/sessions/${id}`),
  deleteSession: async (id: string) => {
    forgetSnapshot(id);
    try {
      await request<void>(`/sessions/${id}`, { method: "DELETE" });
    } catch (e) {
      if (!(e instanceof ApiError) || e.status !== 404) throw e;
    }
  },
  createSession: (input: CreateSessionInput) => {
    const form = new FormData();
    form.append("role_id", input.roleId);
    form.append("candidate_name", input.candidateName);
    form.append("num_questions", String(input.numQuestions));
    if (input.resumeFile) form.append("resume", input.resumeFile);
    else if (input.resumeText) form.append("resume_text", input.resumeText);
    return request<SessionDetail>("/sessions", { method: "POST", body: form }).then((s) => {
      saveSnapshot(s.snapshot);
      return s;
    });
  },
  nextQuestion: (id: string) =>
    sessionRequest<NextQuestionResponse>(id, `/sessions/${id}/questions/next`, { method: "POST" }),
  answer: (id: string, questionId: string, text: string, telemetry?: AnswerTelemetry) =>
    sessionRequest<AnswerResponse>(id, `/sessions/${id}/questions/${questionId}/answer`, json({ text, telemetry })),
  skip: (id: string, questionId: string) =>
    sessionRequest<AnswerResponse>(id, `/sessions/${id}/questions/${questionId}/skip`, { method: "POST" }),
  complete: (id: string) => sessionRequest<ReportResponse>(id, `/sessions/${id}/complete`, { method: "POST" }),
  report: (id: string) => sessionRequest<ReportResponse>(id, `/sessions/${id}/report`),
  search: (roleId: string, query: string, mode: RetrievalMode, topK = 5) =>
    request<SearchResponse>("/knowledge/search", json({ role_id: roleId, query, mode, top_k: topK })),
  benchmark: () => request<Benchmark>("/knowledge/benchmark"),
};
