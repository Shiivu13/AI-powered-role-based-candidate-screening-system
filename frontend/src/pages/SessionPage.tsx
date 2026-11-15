import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { SpeakerIcon } from "../components/icons";
import { PlanList, ProfileCard } from "../components/ProfilePlan";
import { AnswerBox, Feedback, QuestionHeader, TracePanel, Transcript } from "../components/QuestionViews";
import { ReportView } from "../components/ReportView";
import { Card, Chip, ErrorBanner, Spinner, Stepper } from "../components/ui";
import { useInterview } from "../state/useInterview";
import { useVoiceMode } from "../state/useVoiceMode";

const STAGE_INDEX = { loading: 1, overview: 1, asking: 2, feedback: 2, finished: 2, report: 3, error: 1 } as const;

export default function SessionPage() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const { state, next, submit, skip, hint, complete, clearError } = useInterview(sessionId);
  const { phase, session, current, report, busy, error, planDone } = state;
  const voice = useVoiceMode();
  const [listenSignal, setListenSignal] = useState(0);
  const spokenFor = useRef<string | null>(null);

  // Voice mode: read each new open question aloud, then start listening.
  useEffect(() => {
    if (!voice.enabled || phase !== "asking" || !current || current.status !== "asked" || busy === "generating") return;
    if (spokenFor.current === current.id) return;
    spokenFor.current = current.id;
    voice.speak(current.text, () => setListenSignal((n) => n + 1));
  }, [voice, phase, current, busy]);

  if (phase === "loading") return <div className="page center"><Spinner label="Loading session…" /></div>;
  if (phase === "error" || !session)
    return (
      <div className="page">
        <ErrorBanner message={error ?? "Session not found"} />
        <button className="btn" onClick={() => navigate("/")}>Back to start</button>
      </div>
    );

  const p = session.progress;
  const pct = Math.min(100, Math.round((p.primary_asked / Math.max(p.planned, 1)) * 100));

  return (
    <div className="page">
      <Stepper active={STAGE_INDEX[phase]} />
      <div className="session-head">
        <div>
          <h1>{session.candidate_name}</h1>
          <div className="muted">
            {session.mode === "assessment" && <Chip tone="purple">Assessment mode</Chip>}{" "}
            {session.role_title} · {session.plan.length} planned topics
            {session.resume_filename && ` · ${session.resume_filename}`}
          </div>
        </div>
        {phase !== "overview" && phase !== "report" && (
          <div className="progress-wrap" aria-label="Interview progress">
            <div className="small muted">
              {p.primary_asked}/{p.planned} topics · {p.follow_ups} follow-ups · difficulty{" "}
              {p.current_difficulty_offset > 0 ? "↑ raised" : p.current_difficulty_offset < 0 ? "↓ eased" : "on plan"}
            </div>
            <div className="bar">
              <div className="bar-fill fill-blue" style={{ width: `${pct}%` }} />
            </div>
          </div>
        )}
      </div>

      {error && <ErrorBanner message={error} onClose={clearError} />}

      {phase === "overview" && (
        <div className="grid-2">
          <ProfileCard profile={session.profile} roleTitle={session.role_title} />
          <Card
            title="Interview plan"
            actions={
              <button className="btn btn-primary" onClick={next} disabled={!!busy}>
                {busy === "generating" ? <Spinner label="Retrieving context & writing Q1…" /> : "Start interview →"}
              </button>
            }
          >
            <p className="muted small">
              Topics were chosen from the resume (verify claims) and the role's core competencies (probe gaps). Each question is
              generated from passages retrieved for these queries.
            </p>
            <PlanList plan={session.plan} />
          </Card>
        </div>
      )}

      {(phase === "asking" || phase === "feedback" || phase === "finished") && (
        <div className="interview-layout">
          <aside>
            <Card title="Progress">
              <Transcript questions={session.questions} currentId={current?.id} />
            </Card>
            <Card title="Plan">
              <PlanList plan={session.plan} activeIndex={current?.plan_index} />
            </Card>
          </aside>
          <main>
            {phase === "finished" ? (
              <Card title="All planned topics covered">
                <p>The interview plan is complete. Generate the final report to see the analysis.</p>
                <button className="btn btn-primary" onClick={complete} disabled={!!busy}>
                  {busy === "completing" ? <Spinner label="Analysing session…" /> : "Generate report →"}
                </button>
              </Card>
            ) : current ? (
              <Card className="question-card">
                <QuestionHeader q={current} />
                {busy === "generating" ? (
                  <div className="generating">
                    <Spinner label="Retrieving knowledge-base context and generating the next question…" />
                  </div>
                ) : (
                  <>
                    <p className="q-text">{current.text}</p>
                    {voice.supported && (
                      <div className="row">
                        <button
                          type="button"
                          className={`btn btn-small btn-ghost voice-toggle ${voice.enabled ? "on" : ""}`}
                          onClick={() => voice.setEnabled(!voice.enabled)}
                          title="Interviewer reads each question aloud, then the mic starts"
                        >
                          <SpeakerIcon /> Voice mode {voice.enabled ? "on" : "off"}
                        </button>
                        <button type="button" className="btn btn-small btn-ghost" onClick={() => (voice.speaking ? voice.stop() : voice.speak(current.text))}>
                          {voice.speaking ? "Stop reading" : "Read aloud"}
                        </button>
                      </div>
                    )}
                    {phase === "asking" && current.status === "asked" ? (
                      <AnswerBox
                        key={current.id}
                        q={current}
                        busy={busy === "evaluating"}
                        onSubmit={(t, telemetry) => {
                          voice.stop();
                          submit(current.id, t, telemetry);
                        }}
                        onSkip={() => skip(current.id)}
                        onHint={() => hint(current.id)}
                        hintBusy={busy === "hinting"}
                        listenSignal={listenSignal}
                      />
                    ) : (
                      <>
                        <Feedback q={current} />
                        <div className="row end">
                          <button className="btn btn-ghost" onClick={complete} disabled={!!busy}>
                            End interview now
                          </button>
                          {planDone ? (
                            <button className="btn btn-primary" onClick={complete} disabled={!!busy}>
                              {busy === "completing" ? <Spinner label="Analysing…" /> : "Finish & see report →"}
                            </button>
                          ) : (
                            <button className="btn btn-primary" onClick={next} disabled={!!busy}>
                              Next question →
                            </button>
                          )}
                        </div>
                      </>
                    )}
                    <TracePanel q={current} />
                  </>
                )}
              </Card>
            ) : null}
            {phase === "asking" && (
              <div className="row end">
                <button className="btn btn-link" onClick={complete} disabled={!!busy}>
                  End interview early
                </button>
              </div>
            )}
          </main>
        </div>
      )}

      {phase === "report" && report && <ReportView report={report} session={session} onRestart={() => navigate("/")} />}
    </div>
  );
}
