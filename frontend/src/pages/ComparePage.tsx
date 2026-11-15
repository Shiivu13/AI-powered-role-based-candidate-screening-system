import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Report, Role, SessionSummary } from "../api/types";
import { UsersIcon } from "../components/icons";
import { Card, Chip, ErrorBanner, ScoreBadge, Spinner, scoreTone } from "../components/ui";

interface Row {
  session: SessionSummary;
  report: Report;
}

const REC_TONE: Record<string, string> = { strong_yes: "green", yes: "green", borderline: "amber", no: "red" };
const DIMS = ["correctness", "depth", "application", "communication"] as const;

/** Recruiter view: every completed interview for one role, side by side. */
export default function ComparePage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [roleId, setRoleId] = useState("");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .roles()
      .then((r) => {
        setRoles(r);
        setRoleId(r[0]?.id ?? "");
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!roleId) return;
    setRows(null);
    (async () => {
      try {
        const titles = Object.fromEntries(roles.map((r) => [r.id, r.title]));
        const sessions = (await api.listSessions(titles)).filter((s) => s.role_id === roleId && s.status === "completed");
        const loaded = await Promise.all(
          sessions.map(async (s) => {
            try {
              return { session: s, report: (await api.report(s.id)).report };
            } catch {
              return null;
            }
          }),
        );
        setRows(loaded.filter((r): r is Row => r !== null).sort((a, b) => b.report.overall_score - a.report.overall_score));
      } catch (e) {
        setError((e as Error).message);
      }
    })();
  }, [roleId, roles]);

  const topics = useMemo(() => {
    const seen = new Map<string, string>();
    rows?.forEach((r) => r.report.topic_breakdown.forEach((t) => seen.set(t.topic_id, t.topic_name)));
    return [...seen.entries()];
  }, [rows]);

  return (
    <div className="page">
      <h1 className="row">
        <UsersIcon size={22} /> Compare candidates
      </h1>
      <p className="muted">
        Completed interviews for one role, ranked by overall score. Each cell is the candidate's score on that topic; empty cells
        mean the topic was not part of that candidate's personalised plan.
      </p>
      {error && <ErrorBanner message={error} onClose={() => setError(null)} />}
      <Card>
        <label className="field" style={{ maxWidth: 320 }}>
          <span>Role</span>
          <select value={roleId} onChange={(e) => setRoleId(e.target.value)} className="select">
            {roles.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title}
              </option>
            ))}
          </select>
        </label>
        {!rows ? (
          <Spinner label="Loading reports…" />
        ) : rows.length === 0 ? (
          <p className="muted">
            No completed interviews for this role yet. <Link to="/">Run one</Link>.
          </p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Candidate</th>
                  <th>Overall</th>
                  <th>Recommendation</th>
                  {DIMS.map((d) => (
                    <th key={d}>{d}</th>
                  ))}
                  {topics.map(([id, name]) => (
                    <th key={id} title={name}>
                      {name.length > 16 ? name.slice(0, 15) + "…" : name}
                    </th>
                  ))}
                  <th>Integrity</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ session, report }, i) => {
                  const byTopic = Object.fromEntries(report.topic_breakdown.map((t) => [t.topic_id, t.score]));
                  return (
                    <tr key={session.id}>
                      <td>{i + 1}</td>
                      <td>
                        <Link to={`/sessions/${session.id}`}>{session.candidate_name}</Link>
                        {session.mode === "assessment" && <div className="small muted">assessment</div>}
                      </td>
                      <td>
                        <ScoreBadge score={report.overall_score} />
                      </td>
                      <td>
                        <Chip tone={REC_TONE[report.recommendation.code]}>{report.recommendation.label.split(" - ")[0]}</Chip>
                      </td>
                      {DIMS.map((d) => (
                        <td key={d} className="small mono">
                          {report.competencies?.[d]?.toFixed(1) ?? "—"}
                        </td>
                      ))}
                      {topics.map(([id]) => (
                        <td key={id} className="heat-cell">
                          {byTopic[id] == null ? (
                            <span className="muted">·</span>
                          ) : (
                            <div className={`heat heat-${scoreTone(byTopic[id])}`}>{byTopic[id].toFixed(1)}</div>
                          )}
                        </td>
                      ))}
                      <td>
                        {report.insights.integrity?.flagged_answers.length ? (
                          <Chip tone="amber">{report.insights.integrity.flagged_answers.length} flagged</Chip>
                        ) : (
                          <Chip tone="green">clean</Chip>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
