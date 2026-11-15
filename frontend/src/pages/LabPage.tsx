import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { Benchmark, MetricRow, RetrievalMode, Role, SearchResponse } from "../api/types";
import { LayersIcon } from "../components/icons";
import { Card, Chip, ErrorBanner, Spinner } from "../components/ui";

const MODES: { mode: RetrievalMode; label: string; hint: string }[] = [
  { mode: "dense", label: "Dense (LSA vectors)", hint: "Topical similarity in the learned embedding space" },
  { mode: "bm25", label: "Sparse (BM25)", hint: "Exact term matching, strong on jargon" },
  { mode: "hybrid", label: "Hybrid (RRF + MMR)", hint: "What the interview actually uses" },
];

const SUGGESTIONS = [
  "information gain entropy",
  "why does the EM algorithm converge",
  "one-hot encoding of categorical features",
  "vanishing gradient in deep networks",
  "bias variance tradeoff regularization",
];

const METRICS = ["hit@4", "precision@4", "mrr@10", "ndcg@10", "redundancy@4"];

function BenchmarkTable({ title, rows }: { title: string; rows: Record<string, MetricRow> }) {
  const best: Record<string, number> = {};
  for (const m of METRICS) {
    const values = Object.values(rows).map((r) => r[m]);
    best[m] = m === "redundancy@4" ? Math.min(...values) : Math.max(...values);
  }
  return (
    <div>
      <h4>{title}</h4>
      <table className="table">
        <thead>
          <tr>
            <th>Strategy</th>
            {METRICS.map((m) => (
              <th key={m}>{m}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Object.entries(rows).map(([name, r]) => (
            <tr key={name}>
              <td>{name}</td>
              {METRICS.map((m) => (
                <td key={m} className={r[m] === best[m] ? "best" : ""}>
                  {r[m]?.toFixed(3)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function LabPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [roleId, setRoleId] = useState("ai_ml_engineer");
  const [query, setQuery] = useState(SUGGESTIONS[0]);
  const [results, setResults] = useState<Partial<Record<RetrievalMode, SearchResponse>>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bench, setBench] = useState<Benchmark | null>(null);

  useEffect(() => {
    api.roles().then(setRoles).catch((e) => setError(e.message));
    api.benchmark().then(setBench).catch(() => setBench(null));
  }, []);

  const run = async (q = query) => {
    if (q.trim().length < 2) return;
    setBusy(true);
    setError(null);
    try {
      const all = await Promise.all(MODES.map((m) => api.search(roleId, q, m.mode, 5)));
      setResults(Object.fromEntries(all.map((r) => [r.mode, r])));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void run();
  };

  const idsIn = (mode: RetrievalMode) => new Set(results[mode]?.chunks.map((c) => c.chunk_id) ?? []);
  const hybridIds = idsIn("hybrid");

  return (
    <div className="page">
      <h1 className="row">
        <LayersIcon size={22} /> Retrieval lab
      </h1>
      <p className="muted">
        Compare what each retriever pulls from a role's knowledge base for the same query. Results that also appear in the hybrid
        top-5 are marked; that is the context the question generator would see.
      </p>
      {error && <ErrorBanner message={error} onClose={() => setError(null)} />}

      <Card>
        <form className="lab-form" onSubmit={onSubmit}>
          <label className="field">
            <span>Knowledge base</span>
            <select value={roleId} onChange={(e) => setRoleId(e.target.value)}>
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Query</span>
            <input value={query} onChange={(e) => setQuery(e.target.value)} maxLength={500} />
          </label>
          <button className="btn btn-primary" disabled={busy} style={{ marginBottom: "0.9rem" }}>
            {busy ? <Spinner label="Searching…" /> : "Compare retrievers"}
          </button>
        </form>
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              className="chip"
              onClick={() => {
                setQuery(s);
                void run(s);
              }}
            >
              {s}
            </button>
          ))}
        </div>
      </Card>

      {Object.keys(results).length > 0 && (
        <div className="lab-cols">
          {MODES.map(({ mode, label, hint }) => (
            <div key={mode}>
              <h3>
                {label}
                <Chip>{String(results[mode]?.diagnostics.status ?? "")}</Chip>
              </h3>
              <p className="small muted">{hint}</p>
              {results[mode]?.chunks.map((c, i) => (
                <div key={c.chunk_id} className={`lab-hit ${mode !== "hybrid" && hybridIds.has(c.chunk_id) ? "shared" : ""}`}>
                  <div className="small">
                    <strong>#{i + 1}</strong> {c.citation}
                  </div>
                  <div className="small muted mono">
                    dense #{c.dense_rank ?? "—"} · bm25 #{c.bm25_rank ?? "—"}
                    {c.dense_score != null && ` · cos ${c.dense_score}`}
                  </div>
                  <p className="snippet">{c.snippet.slice(0, 260)}…</p>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      <Card title="Offline benchmark" className="lab-bench">
        {!bench ? (
          <p className="muted small">
            No benchmark results yet. Run <code>python -m scripts.benchmark_retrieval</code> from <code>backend/</code>.
          </p>
        ) : (
          <>
            <p className="small muted">
              Queries are numbered section titles from the books; the relevant chunks are that section's chunks; the index is
              rebuilt from chunk text only so titles cannot be matched through headers. Best value per column in green (lowest for
              redundancy). Run on {bench.generated_at}.
            </p>
            {Object.entries(bench.roles).map(([role, r]) => (
              <BenchmarkTable
                key={role}
                title={`${roles.find((x) => x.id === role)?.title ?? role}: ${r.queries} queries, ${r.chunks} chunks`}
                rows={r.results}
              />
            ))}
            {bench.chunk_size_ablation.results && (
              <div>
                <h4>Chunk size ablation ({bench.chunk_size_ablation.role})</h4>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Chunk size</th>
                      <th>chunks</th>
                      <th>hit@4</th>
                      <th>precision@4</th>
                      <th>mrr@10</th>
                      <th>ndcg@10</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(bench.chunk_size_ablation.results).map(([size, r]) => (
                      <tr key={size}>
                        <td>{size} chars</td>
                        <td>{r.chunks}</td>
                        <td>{r["hit@4"]}</td>
                        <td>{r["precision@4"]}</td>
                        <td>{r["mrr@10"]}</td>
                        <td>{r["ndcg@10"]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
