import type { AnswerTelemetry } from "../state/useAnswerTelemetry";
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
  listSessions: () => request<SessionSummary[]>("/sessions"),
  getSession: (id: string) => request<SessionDetail>(`/sessions/${id}`),
  deleteSession: (id: string) => request<void>(`/sessions/${id}`, { method: "DELETE" }),
  createSession: (input: CreateSessionInput) => {
    const form = new FormData();
    form.append("role_id", input.roleId);
    form.append("candidate_name", input.candidateName);
    form.append("num_questions", String(input.numQuestions));
    if (input.resumeFile) form.append("resume", input.resumeFile);
    else if (input.resumeText) form.append("resume_text", input.resumeText);
    return request<SessionDetail>("/sessions", { method: "POST", body: form });
  },
  nextQuestion: (id: string) =>
    request<NextQuestionResponse>(`/sessions/${id}/questions/next`, { method: "POST" }),
  answer: (id: string, questionId: string, text: string, telemetry?: AnswerTelemetry) =>
    request<AnswerResponse>(`/sessions/${id}/questions/${questionId}/answer`, json({ text, telemetry })),
  skip: (id: string, questionId: string) =>
    request<AnswerResponse>(`/sessions/${id}/questions/${questionId}/skip`, { method: "POST" }),
  complete: (id: string) => request<ReportResponse>(`/sessions/${id}/complete`, { method: "POST" }),
  report: (id: string) => request<ReportResponse>(`/sessions/${id}/report`),
  search: (roleId: string, query: string, mode: RetrievalMode, topK = 5) =>
    request<SearchResponse>("/knowledge/search", json({ role_id: roleId, query, mode, top_k: topK })),
  benchmark: () => request<Benchmark>("/knowledge/benchmark"),
};
