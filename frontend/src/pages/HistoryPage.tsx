import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { SessionSummary } from "../api/types";
import { TrashIcon } from "../components/icons";
import { Card, Chip, ErrorBanner, ScoreBadge, Spinner } from "../components/ui";

const STATUS_TONE = { ready: "neutral", in_progress: "amber", completed: "green" } as const;

export default function HistoryPage() {
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.listSessions().then(setSessions).catch((e) => setError(e.message));
  useEffect(() => {
    void load();
  }, []);

  const remove = async (id: string) => {
    if (!confirm("Delete this session and all its answers? This cannot be undone.")) return;
    try {
      await api.deleteSession(id);
      void load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="page">
      <h1>Interview sessions</h1>
      {error && <ErrorBanner message={error} onClose={() => setError(null)} />}
      <Card>
        {!sessions ? (
          <Spinner label="Loading…" />
        ) : sessions.length === 0 ? (
          <p className="muted">
            No sessions yet. <Link to="/">Start one</Link>.
          </p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Role</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Score</th>
                <th>Created</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id}>
                  <td>
                    <Link to={`/sessions/${s.id}`}>{s.candidate_name}</Link>
                  </td>
                  <td>{s.role_title}</td>
                  <td>
                    <Chip tone={STATUS_TONE[s.status]}>{s.status.replace("_", " ")}</Chip>
                  </td>
                  <td className="small">
                    {s.progress.answered} answered / {s.progress.planned} planned
                  </td>
                  <td>
                    <ScoreBadge score={s.overall_score} />
                  </td>
                  <td className="small muted">{new Date(s.created_at).toLocaleString()}</td>
                  <td className="row end">
                    <Link className="btn btn-small" to={`/sessions/${s.id}`}>
                      {s.status === "completed" ? "Report" : "Resume"}
                    </Link>
                    <button className="btn btn-small btn-ghost" onClick={() => remove(s.id)} aria-label="Delete session">
                      <TrashIcon />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
