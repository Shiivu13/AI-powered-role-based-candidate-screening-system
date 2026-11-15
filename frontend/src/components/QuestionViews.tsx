import { useEffect, useState } from "react";
import type { Integrity, Question, Rubric } from "../api/types";
import { useAnswerTelemetry, type AnswerTelemetry } from "../state/useAnswerTelemetry";
import { useSpeech } from "../state/useSpeech";
import { BulbIcon, MicIcon, SearchIcon, ShieldIcon } from "./icons";
import { Chip, DifficultyChip, Elapsed, ScoreBadge, ScoreBar, Spinner } from "./ui";

const TYPE_LABEL: Record<string, string> = {
  conceptual: "Conceptual",
  applied: "Applied",
  scenario: "Scenario",
  derivation: "Derivation",
  follow_up: "Follow-up",
};

export function QuestionHeader({ q }: { q: Question }) {
  return (
    <div className="q-meta">
      <Chip tone={q.kind === "follow_up" ? "purple" : "blue"}>
        {q.kind === "follow_up" ? "↳ Follow-up" : `Q${q.position}`} · {q.topic_name}
      </Chip>
      <Chip>{TYPE_LABEL[q.question_type] ?? q.question_type}</Chip>
      <DifficultyChip level={q.difficulty} label={q.difficulty_label} />
    </div>
  );
}

export function AnswerBox({
  q,
  busy,
  onSubmit,
  onSkip,
  onHint,
  hintBusy = false,
  listenSignal = 0,
}: {
  q: Question;
  busy: boolean;
  onSubmit: (text: string, telemetry: AnswerTelemetry) => void;
  onSkip: () => void;
  onHint?: () => void;
  hintBusy?: boolean;
  /** Incremented by voice mode when the interviewer finishes reading the question. */
  listenSignal?: number;
}) {
  const [text, setText] = useState("");
  const telemetry = useAnswerTelemetry();
  const speech = useSpeech((phrase) => {
    if (!phrase) return;
    telemetry.addVoice(phrase.length + 1);
    setText((t) => (t && !t.endsWith(" ") ? `${t} ${phrase}` : `${t}${phrase}`));
  });
  useEffect(() => {
    if (listenSignal > 0 && speech.supported && !speech.listening) speech.start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listenSignal]);
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const send = () => {
    if (!text.trim()) return;
    speech.stop();
    onSubmit(text, telemetry.snapshot());
  };
  return (
    <div className="answer-box">
      {q.hint && (
        <div className="hint-box">
          <BulbIcon /> <span>{q.hint}</span> <span className="muted small">(hint used: -15% on this question)</span>
        </div>
      )}
      <div className="textarea-wrap">
        <textarea
          autoFocus
          rows={8}
          placeholder={
            speech.supported
              ? "Type your answer, or press the mic and talk it through. Explain your reasoning and give concrete examples…"
              : "Type your answer. Explain your reasoning and give concrete examples where you can…"
          }
          value={text}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
          onPaste={telemetry.onPaste}
          onKeyDown={(e) => {
            telemetry.onKeyDown();
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") send();
          }}
          maxLength={10000}
        />
        {speech.listening && (
          <div className="live-caption" aria-live="polite">
            <span className="rec-dot" /> {speech.interim || "Listening…"}
          </div>
        )}
      </div>
      <div className="answer-actions">
        <span className="muted small">
          {words} words · <Elapsed since={q.asked_at} /> · Ctrl/⌘+Enter to submit
          {speech.error && <span className="warn"> · {speech.error}</span>}
        </span>
        <div className="row">
          {speech.supported && (
            <button
              type="button"
              className={`btn btn-ghost ${speech.listening ? "btn-recording" : ""}`}
              onClick={speech.listening ? speech.stop : speech.start}
              disabled={busy}
              title="Answer by voice (browser speech recognition)"
            >
              <MicIcon /> {speech.listening ? "Stop" : "Speak"}
            </button>
          )}
          {onHint && !q.hint && (
            <button type="button" className="btn btn-ghost" onClick={onHint} disabled={busy || hintBusy} title="A nudge grounded in the reference material; costs 15% of this question's score">
              {hintBusy ? <Spinner /> : <BulbIcon />} Hint
            </button>
          )}
          <button className="btn btn-ghost" onClick={onSkip} disabled={busy}>
            Skip
          </button>
          <button className="btn btn-primary" onClick={send} disabled={busy || !text.trim()}>
            {busy ? <Spinner label="Evaluating…" /> : "Submit answer"}
          </button>
        </div>
      </div>
    </div>
  );
}

const FLAG_LABEL: Record<string, string> = {
  pasted_answer: "Pasted answer",
  copied_from_source: "Copied from reference text",
  implausible_speed: "Implausible typing speed",
  left_the_tab: "Left the interview tab",
};

export function IntegrityNote({ integrity }: { integrity: Integrity | null | undefined }) {
  if (!integrity) return null;
  const s = integrity.signals;
  return (
    <div className={`integrity integrity-${integrity.level}`}>
      <div className="integrity-head">
        <ShieldIcon />
        <strong>{integrity.level === "none" ? "No integrity concerns" : "Integrity signals for review"}</strong>
        <span className="muted small">advisory, not scored</span>
      </div>
      {integrity.flags.length > 0 && (
        <ul className="tight small">
          {integrity.flags.map((f) => (
            <li key={f.code}>
              <strong>{FLAG_LABEL[f.code] ?? f.code}:</strong> {f.detail}
            </li>
          ))}
        </ul>
      )}
      <div className="small muted mono">
        pasted {Math.round(s.paste_ratio * 100)}% · voice {Math.round(s.voice_ratio * 100)}% · verbatim overlap{" "}
        {Math.round(s.verbatim_source_overlap * 100)}% · focus lost {s.focus_losses}×
        {s.words_per_minute != null && ` · ${s.words_per_minute} wpm`}
      </div>
    </div>
  );
}

const RUBRIC_LABEL: Record<keyof Rubric, string> = {
  correctness: "Correctness",
  depth: "Depth",
  application: "Application",
  communication: "Communication",
};

export function RubricBars({ rubric }: { rubric: Partial<Rubric> | null | undefined }) {
  if (!rubric || Object.keys(rubric).length === 0) return null;
  return (
    <div className="rubric">
      {(Object.keys(RUBRIC_LABEL) as (keyof Rubric)[]).map((k) =>
        rubric[k] == null ? null : (
          <div key={k} className="rubric-row">
            <span className="small">{RUBRIC_LABEL[k]}</span>
            <ScoreBar score={rubric[k] as number} />
            <span className="small mono">{(rubric[k] as number).toFixed(1)}</span>
          </div>
        ),
      )}
    </div>
  );
}

export function Feedback({ q }: { q: Question }) {
  const a = q.answer;
  if (a?.hidden)
    return (
      <div className="feedback">
        <div className="feedback-head">
          <ShieldIcon /> <strong>Answer recorded</strong>
        </div>
        <p className="muted">Assessment mode: scores and feedback are revealed in the final report.</p>
      </div>
    );
  if (q.status === "skipped")
    return (
      <div className="feedback">
        <div className="feedback-head">
          <ScoreBadge score={0} /> <strong>Skipped</strong>
        </div>
        <ExpectedPoints q={q} />
      </div>
    );
  if (!a) return null;
  return (
    <div className="feedback">
      <div className="feedback-head">
        <ScoreBadge score={a.score} />
        <div>
          <strong className="cap">{a.verdict}</strong>
          <div className="muted small">
            Evaluated by {a.evaluation_mode === "llm" ? "LLM grader" : a.evaluation_mode === "rule" ? "rule" : "semantic-coverage grader"}
            {a.response_seconds != null && ` · answered in ${Math.round(a.response_seconds)}s`}
          </div>
        </div>
      </div>
      {a.feedback && <p>{a.feedback}</p>}
      <RubricBars rubric={a.rubric} />
      {a.hint_penalty ? <p className="small muted">Hint used: score reduced by {Math.round(a.hint_penalty * 100)}%.</p> : null}
      <div className="two-col">
        {a.covered_points.length > 0 && (
          <div>
            <h4 className="ok">Covered</h4>
            <ul className="tight">
              {a.covered_points.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
        )}
        {a.missing_points.length > 0 && (
          <div>
            <h4 className="warn">Missing</h4>
            <ul className="tight">
              {a.missing_points.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      {a.misconceptions.length > 0 && (
        <div>
          <h4 className="bad">Misconceptions</h4>
          <ul className="tight">
            {a.misconceptions.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}
      <IntegrityNote integrity={a.integrity} />
      <details className="details">
        <summary>Your answer</summary>
        <p className="pre">{a.text}</p>
      </details>
      <ExpectedPoints q={q} />
    </div>
  );
}

function ExpectedPoints({ q }: { q: Question }) {
  if (!q.expected_points?.length) return null;
  return (
    <details className="details">
      <summary>Reference answer points</summary>
      <ul className="tight">
        {q.expected_points.map((p) => (
          <li key={p}>{p}</li>
        ))}
      </ul>
    </details>
  );
}

export function TracePanel({ q }: { q: Question }) {
  const t = q.trace;
  if (!t) return null;
  const diag = t.retrieval.diagnostics as Record<string, unknown>;
  return (
    <details className="trace">
      <summary>
        <SearchIcon /> Why this question? Retrieval and generation trace
      </summary>
      <div className="trace-body">
        <p>
          <strong>Plan:</strong> {t.plan_item.reason}
        </p>
        {t.adaptive_note && (
          <p>
            <strong>Adaptation:</strong> {t.adaptive_note}
          </p>
        )}
        <p>
          <strong>Generated by:</strong> {t.generation.mode === "llm" ? `LLM (${t.generation.model})` : "offline grounded generator"} · prompt{" "}
          {t.generation.prompt_version}
          {t.generation.fallback_reason && <span className="warn"> · fell back: {t.generation.fallback_reason}</span>}
        </p>
        <p>
          <strong>Queries:</strong>
        </p>
        <ol className="mono tight small">
          {t.retrieval.queries.map((qq) => (
            <li key={qq}>{qq}</li>
          ))}
        </ol>
        <p className="small muted">
          Grounding: {String(diag.status)} · candidate pool {String(diag.candidate_pool)} · mean dense similarity{" "}
          {String(diag.mean_dense_similarity)} · chunks found by both retrievers {String(diag.chunks_agreed_by_both_retrievers)}
        </p>
        <div className="sources">
          {t.retrieval.chunks.map((c, i) => (
            <div key={c.chunk_id} className={`source ${c.used_by_question ? "used" : ""}`}>
              <div className="source-head">
                <strong>S{i + 1}</strong> {c.citation}
                {c.used_by_question && <Chip tone="green">used</Chip>}
              </div>
              <div className="small muted mono">
                rrf {c.rrf_score} · dense {c.dense_score ?? "—"} (#{c.dense_rank ?? "—"}) · bm25 #{c.bm25_rank ?? "—"}
              </div>
              <p className="snippet">{c.snippet.length > 500 ? c.snippet.slice(0, 500) + "…" : c.snippet}</p>
            </div>
          ))}
        </div>
      </div>
    </details>
  );
}

export function Transcript({ questions, currentId }: { questions: Question[]; currentId?: string }) {
  return (
    <ol className="transcript">
      {questions.map((q) => (
        <li key={q.id} className={`${q.id === currentId ? "current" : ""} ${q.kind === "follow_up" ? "follow" : ""}`}>
          <div className="t-head">
            <span className="small">
              {q.kind === "follow_up" ? "↳" : `Q${q.position}`} {q.topic_name}
            </span>
            {q.status === "asked" ? <Chip tone="amber">open</Chip> : <ScoreBadge score={q.status === "skipped" ? 0 : q.answer?.score} />}
          </div>
        </li>
      ))}
    </ol>
  );
}
