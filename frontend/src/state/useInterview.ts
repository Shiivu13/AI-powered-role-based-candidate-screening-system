import { useCallback, useEffect, useReducer } from "react";
import { api, ApiError } from "../api/client";
import type { Question, Report, SessionDetail } from "../api/types";
import type { AnswerTelemetry } from "./useAnswerTelemetry";

/**
 * Interview state machine for one session.
 *
 *   loading -> overview (status=ready) --start--> asking --submit--> feedback --next--> asking ...
 *                                                              \--(plan done)--> finished --complete--> report
 */
export type Phase = "loading" | "overview" | "asking" | "feedback" | "finished" | "report" | "error";

interface State {
  phase: Phase;
  session: SessionDetail | null;
  current: Question | null; // open question or the one whose feedback is shown
  report: Report | null;
  busy: null | "generating" | "evaluating" | "completing";
  error: string | null;
  planDone: boolean; // the last answer closed the plan: offer "finish" instead of "next"
}

type Action =
  | { type: "loaded"; session: SessionDetail; report: Report | null }
  | { type: "busy"; busy: State["busy"] }
  | { type: "question"; question: Question }
  | { type: "answered"; question: Question; done: boolean }
  | { type: "finished" }
  | { type: "report"; report: Report }
  | { type: "session"; session: SessionDetail }
  | { type: "error"; error: string; fatal?: boolean }
  | { type: "clearError" };

const initial: State = {
  phase: "loading",
  session: null,
  current: null,
  report: null,
  busy: null,
  error: null,
  planDone: false,
};

function upsertQuestion(session: SessionDetail | null, q: Question): SessionDetail | null {
  if (!session) return session;
  const exists = session.questions.some((x) => x.id === q.id);
  const questions = exists ? session.questions.map((x) => (x.id === q.id ? q : x)) : [...session.questions, q];
  return { ...session, questions };
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "loaded": {
      const { session, report } = action;
      if (session.status === "completed")
        return { ...state, session, report, phase: "report", busy: null, current: null };
      if (session.status === "ready") return { ...state, session, phase: "overview", busy: null };
      const open = session.questions.find((q) => q.id === session.current_question_id) ?? null;
      if (open) return { ...state, session, current: open, phase: "asking", busy: null };
      const last = session.questions[session.questions.length - 1] ?? null;
      return { ...state, session, current: last, phase: "feedback", busy: null };
    }
    case "session":
      return { ...state, session: action.session };
    case "busy":
      return { ...state, busy: action.busy, error: null };
    case "question":
      return {
        ...state,
        busy: null,
        phase: "asking",
        current: action.question,
        session: upsertQuestion(state.session, action.question),
      };
    case "answered":
      return {
        ...state,
        busy: null,
        phase: "feedback",
        current: action.question,
        session: upsertQuestion(state.session, action.question),
        error: null,
        planDone: action.done,
      };
    case "finished":
      return { ...state, busy: null, phase: "finished" };
    case "report":
      return { ...state, busy: null, phase: "report", report: action.report };
    case "error":
      return { ...state, busy: null, error: action.error, phase: action.fatal ? "error" : state.phase };
    case "clearError":
      return { ...state, error: null };
  }
}

const message = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : "Unexpected error");

export function useInterview(sessionId: string) {
  const [state, dispatch] = useReducer(reducer, initial);

  const refresh = useCallback(async () => {
    try {
      const session = await api.getSession(sessionId);
      const report = session.report_available ? (await api.report(sessionId)).report : null;
      dispatch({ type: "loaded", session, report });
    } catch (e) {
      dispatch({ type: "error", error: message(e), fatal: true });
    }
  }, [sessionId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const next = useCallback(async () => {
    dispatch({ type: "busy", busy: "generating" });
    try {
      const res = await api.nextQuestion(sessionId);
      if (res.done || !res.question) dispatch({ type: "finished" });
      else dispatch({ type: "question", question: res.question });
      // keep progress/status in sync
      dispatch({ type: "session", session: await api.getSession(sessionId) });
    } catch (e) {
      dispatch({ type: "error", error: message(e) });
    }
  }, [sessionId]);

  const submit = useCallback(
    async (questionId: string, text: string, telemetry?: AnswerTelemetry) => {
      dispatch({ type: "busy", busy: "evaluating" });
      try {
        const res = await api.answer(sessionId, questionId, text, telemetry);
        dispatch({ type: "answered", question: res.question, done: res.next_action === "complete" });
        dispatch({ type: "session", session: await api.getSession(sessionId) });
      } catch (e) {
        dispatch({ type: "error", error: message(e) });
      }
    },
    [sessionId],
  );

  const skip = useCallback(
    async (questionId: string) => {
      dispatch({ type: "busy", busy: "evaluating" });
      try {
        const res = await api.skip(sessionId, questionId);
        dispatch({ type: "answered", question: res.question, done: res.next_action === "complete" });
        dispatch({ type: "session", session: await api.getSession(sessionId) });
      } catch (e) {
        dispatch({ type: "error", error: message(e) });
      }
    },
    [sessionId],
  );

  const complete = useCallback(async () => {
    dispatch({ type: "busy", busy: "completing" });
    try {
      const res = await api.complete(sessionId);
      dispatch({ type: "session", session: await api.getSession(sessionId) });
      dispatch({ type: "report", report: res.report });
    } catch (e) {
      dispatch({ type: "error", error: message(e) });
    }
  }, [sessionId]);

  const clearError = useCallback(() => dispatch({ type: "clearError" }), []);

  return { state, next, submit, skip, complete, refresh, clearError };
}
