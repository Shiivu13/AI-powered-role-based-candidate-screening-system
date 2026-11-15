import type { Report, SessionDetail } from "../api/types";
import { DownloadIcon, FlagIcon, PrintIcon, ShieldIcon } from "./icons";
import { Feedback, QuestionHeader, TracePanel } from "./QuestionViews";
import { Card, Chip, ScoreBar, ScoreRing } from "./ui";

const REC_TONE: Record<string, string> = { strong_yes: "green", yes: "green", borderline: "amber", no: "red" };
const CLAIM: Record<string, { label: string; tone: string }> = {
  verified: { label: "Verified", tone: "green" },
  partially_verified: { label: "Partially verified", tone: "amber" },
  not_verified: { label: "Not verified", tone: "red" },
};

function download(session: SessionDetail, report: Report) {
  const blob = new Blob([JSON.stringify({ session, report }, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `interview-${session.candidate_name.replace(/\s+/g, "_")}-${session.id.slice(0, 8)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

/** Radar of topic scores: the shape shows at a glance where the candidate is
 * strong (resume-anchored axes in blue) and where the role's core gaps are. */
function SkillRadar({ topics }: { topics: Report["topic_breakdown"] }) {
  if (topics.length < 3) return null;
  const size = 300;
  const c = size / 2;
  const r = 100;
  const n = topics.length;
  const angle = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2;
  const point = (i: number, v: number) => [c + Math.cos(angle(i)) * r * (v / 10), c + Math.sin(angle(i)) * r * (v / 10)];
  const poly = topics.map((t, i) => point(i, Math.max(t.score, 0.3)).join(",")).join(" ");
  return (
    <svg viewBox={`-110 -10 ${size + 220} ${size + 20}`} width="100%" style={{ maxWidth: 520 }} role="img" aria-label="Topic score radar">
      {[2.5, 5, 7.5, 10].map((v) => (
        <polygon key={v} className="radar-grid" points={topics.map((_, i) => point(i, v).join(",")).join(" ")} />
      ))}
      {topics.map((_, i) => {
        const [x, y] = point(i, 10);
        return <line key={i} x1={c} y1={c} x2={x} y2={y} className="radar-grid" />;
      })}
      <polygon points={poly} className="radar-area" />
      {topics.map((t, i) => {
        const [x, y] = point(i, Math.max(t.score, 0.3));
        const [lx, ly] = point(i, 12.6);
        const anchor = Math.abs(lx - c) < 8 ? "middle" : lx > c ? "start" : "end";
        const label = t.topic_name.length > 22 ? t.topic_name.slice(0, 21) + "…" : t.topic_name;
        return (
          <g key={t.topic_id}>
            <circle cx={x} cy={y} r={3.5} className={t.source === "resume" ? "radar-dot-resume" : "radar-dot-core"} />
            <text x={lx} y={ly} textAnchor={anchor} dominantBaseline="middle" className="radar-label">
              {label} ({t.score.toFixed(1)})
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function IntegritySummary({ integrity }: { integrity: NonNullable<Report["insights"]["integrity"]> }) {
  return (
    <Card title={<span className="row"><ShieldIcon /> Answer integrity</span>}>
      {integrity.flagged_answers.length === 0 ? (
        <p className="muted">No paste, copy, speed or tab-switch signals were raised.</p>
      ) : (
        <ul className="tight">
          {integrity.flagged_answers.map((a) => (
            <li key={a.position}>
              <FlagIcon size={13} /> Q{a.position} ({a.topic_name}): {a.flags.map((f) => f.detail).join("; ")}
            </li>
          ))}
        </ul>
      )}
      <p className="small muted">{integrity.note}</p>
    </Card>
  );
}

function DifficultyChart({ points }: { points: Report["insights"]["difficulty_progression"] }) {
  const w = 320;
  const h = 120;
  const pad = 22;
  if (points.length === 0) return null;
  const x = (i: number) => pad + (points.length === 1 ? 0 : (i * (w - 2 * pad)) / (points.length - 1));
  const yScore = (s: number) => h - pad - (s / 10) * (h - 2 * pad);
  const yDiff = (d: number) => h - pad - ((d - 1) / 2) * (h - 2 * pad);
  const scorePath = points
    .map((p, i) => (p.score == null ? null : `${x(i)},${yScore(p.score)}`))
    .filter(Boolean)
    .join(" ");
  const diffPath = points.map((p, i) => `${x(i)},${yDiff(p.difficulty)}`).join(" ");
  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Score and difficulty per question">
        <line x1={pad} x2={w - pad} y1={h - pad} y2={h - pad} className="axis" />
        <polyline points={diffPath} className="line-diff" />
        <polyline points={scorePath} className="line-score" />
        {points.map((p, i) => (
          <g key={i}>
            {p.score != null && <circle cx={x(i)} cy={yScore(p.score)} r={3.5} className="dot-score" />}
            <text x={x(i)} y={h - 6} textAnchor="middle" className="tick">
              {p.position}
            </text>
          </g>
        ))}
      </svg>
      <figcaption className="small muted">
        <span className="legend legend-score" /> score (0–10) <span className="legend legend-diff" /> difficulty (1–3) per question
      </figcaption>
    </figure>
  );
}

export function ReportView({ report, session, onRestart }: { report: Report; session: SessionDetail; onRestart: () => void }) {
  const ins = report.insights;
  return (
    <div className="report">
      <Card className="report-hero">
        <div className="hero-row">
          <ScoreRing score={report.overall_score} />
          <div className="grow">
            <h2>{report.candidate_name}</h2>
            <div className="muted">{report.role_title}</div>
            <div className="rec">
              <Chip tone={REC_TONE[report.recommendation.code]}>{report.recommendation.label}</Chip>
              <Chip>trend: {ins.score_trend.replace("_", " ")}</Chip>
              <Chip>{report.narrative.mode === "llm" ? "LLM debrief" : "Rule-based debrief"}</Chip>
            </div>
            <p>{report.narrative.summary}</p>
          </div>
          <div className="col-actions">
            <button className="btn" onClick={() => download(session, report)}>
              <DownloadIcon /> Export JSON
            </button>
            <button className="btn btn-ghost" onClick={() => window.print()}>
              <PrintIcon /> Print
            </button>
            <button className="btn btn-primary" onClick={onRestart}>
              New interview
            </button>
          </div>
        </div>
        <div className="stats">
          <div>
            <b>{ins.questions_asked}</b>
            <span>questions</span>
          </div>
          <div>
            <b>{ins.follow_ups}</b>
            <span>follow-ups</span>
          </div>
          <div>
            <b>{ins.skipped}</b>
            <span>skipped</span>
          </div>
          <div>
            <b>{ins.avg_response_seconds != null ? `${Math.round(ins.avg_response_seconds)}s` : "—"}</b>
            <span>avg response</span>
          </div>
          <div>
            <b>{ins.avg_answer_words}</b>
            <span>avg words</span>
          </div>
        </div>
      </Card>

      <div className="grid-2">
        <Card title="Score by topic">
          <div className="radar-wrap">
            <SkillRadar topics={report.topic_breakdown} />
          </div>
          <ul className="topic-scores">
            {report.topic_breakdown.map((t) => (
              <li key={t.topic_id}>
                <div className="row between">
                  <span>
                    {t.topic_name}{" "}
                    <Chip tone={t.source === "resume" ? "blue" : "purple"}>{t.source === "resume" ? "resume" : "role core"}</Chip>
                  </span>
                  <strong>{t.score.toFixed(1)}</strong>
                </div>
                <ScoreBar score={t.score} />
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Interview dynamics">
          <DifficultyChart points={ins.difficulty_progression} />
          <p className="small muted">
            Grounded in: {ins.grounding.books_used.join(", ") || "—"} · {ins.grounding.llm_generated}/{ins.questions_asked} questions
            LLM-generated
          </p>
        </Card>
      </div>

      <div className="grid-2">
        <Card title="Resume claims vs. demonstrated knowledge">
          {report.resume_claims.length === 0 ? (
            <p className="muted">No resume-anchored topics were assessed.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Topic</th>
                  <th>Resume evidence</th>
                  <th>Score</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {report.resume_claims.map((c) => (
                  <tr key={c.topic_name}>
                    <td>{c.topic_name}</td>
                    <td className="small">{c.evidence.slice(0, 4).join(", ")}</td>
                    <td>{c.score.toFixed(1)}</td>
                    <td>
                      <Chip tone={CLAIM[c.status]?.tone}>{CLAIM[c.status]?.label ?? c.status}</Chip>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="small">{report.narrative.resume_alignment}</p>
        </Card>
        <Card title="Debrief">
          <h4 className="ok">Strengths</h4>
          <ul className="tight">
            {report.narrative.strengths.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <h4 className="warn">Improvement areas</h4>
          <ul className="tight">
            {report.narrative.improvement_areas.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <h4>Suggested next steps</h4>
          <ul className="tight">
            {report.narrative.suggested_next_steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </Card>
      </div>

      {report.insights.integrity && <IntegritySummary integrity={report.insights.integrity} />}

      <Card title="Full transcript">
        <ol className="qa-list">
          {session.questions.map((q) => (
            <li key={q.id} className={q.kind === "follow_up" ? "follow" : ""}>
              <QuestionHeader q={q} />
              <p className="q-text">{q.text}</p>
              <Feedback q={q} />
              <TracePanel q={q} />
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
