'use client';

import { useState, useEffect, use } from 'react';
import { useRouter } from 'next/navigation';
import { getSessionSummary } from '../../../lib/api';
import { SessionSummary, ROLE_LABELS } from '../../../lib/types';

interface PageProps {
  params: Promise<{ sessionId: string }>;
}

export default function ResultsPage({ params }: PageProps) {
  const { sessionId } = use(params);
  const router = useRouter();
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedQ, setExpandedQ] = useState<number | null>(null);

  useEffect(() => {
    loadSummary();
  }, [sessionId]);

  const loadSummary = async () => {
    try {
      const data = await getSessionSummary(sessionId);
      setSummary(data);
    } catch {
      setError('Could not load results. The session may still be processing.');
    } finally {
      setLoading(false);
    }
  };

  const getRecClass = (rec: string | null) => {
    if (!rec) return 'rec-maybe';
    const r = rec.toLowerCase();
    if (r.includes('strong')) return 'rec-strong-hire';
    if (r === 'hire') return 'rec-hire';
    if (r === 'maybe') return 'rec-maybe';
    return 'rec-no-hire';
  };

  const getScoreColor = (score: number | null) => {
    if (score === null) return 'var(--text-muted)';
    if (score >= 8) return '#34d399';
    if (score >= 6) return '#60a5fa';
    if (score >= 4) return '#fbbf24';
    return '#fb7185';
  };

  const exportSession = () => {
    if (!summary) return;
    const blob = new Blob([JSON.stringify(summary, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `interview_${sessionId.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-6">
        <div className="spinner mb-5" />
        <p className="font-display text-lg" style={{ color: 'var(--text)' }}>Analyzing your interview…</p>
        <p className="text-sm mt-1.5" style={{ color: 'var(--text-muted)' }}>Sage is grading your responses · up to 30s</p>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <div className="glass-card p-8 max-w-md text-center animate-scale-in">
          <div className="text-4xl mb-3">📭</div>
          <p className="mb-5" style={{ color: 'var(--text)' }}>{error || 'No results found.'}</p>
          <button onClick={() => router.push('/')} className="btn-primary">← New Interview</button>
        </div>
      </div>
    );
  }

  const roleLabel = ROLE_LABELS[summary.role] || summary.role;
  const score = summary.technical_score;
  const scoreColor = getScoreColor(score);
  const scorePct = score !== null ? (score / 10) * 100 : 0;
  const circumference = 2 * Math.PI * 52;

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b"
        style={{ borderColor: 'var(--border)', background: 'rgba(7,8,15,0.7)', backdropFilter: 'blur(16px)' }}>
        <div className="max-w-4xl mx-auto px-5 sm:px-6 py-3.5 flex items-center gap-3">
          <button onClick={() => router.push('/')} className="btn-ghost">← New</button>
          <span className="font-display font-semibold" style={{ color: 'var(--text)' }}>Interview Report</span>
          <button onClick={exportSession} className="btn-ghost ml-auto">↓ Export JSON</button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-5 sm:px-6 py-8">
        {/* Hero / Score card */}
        <div className="glass-card p-7 sm:p-9 mb-5 animate-scale-in">
          <div className="flex flex-col sm:flex-row items-center gap-8">
            {/* Score ring */}
            <div className="relative flex-shrink-0">
              <svg width="128" height="128" className="score-ring -rotate-90">
                <circle cx="64" cy="64" r="52" fill="none" stroke="rgba(124,131,255,0.12)" strokeWidth="10" />
                <circle
                  cx="64" cy="64" r="52" fill="none" stroke={scoreColor} strokeWidth="10" strokeLinecap="round"
                  strokeDasharray={circumference}
                  strokeDashoffset={circumference - (scorePct / 100) * circumference}
                  style={{ transition: 'stroke-dashoffset 1.2s cubic-bezier(0.16,1,0.3,1)' }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="font-display text-3xl font-extrabold" style={{ color: scoreColor }}>
                  {score !== null ? score.toFixed(1) : '—'}
                </span>
                <span className="text-xs" style={{ color: 'var(--text-dim)' }}>out of 10</span>
              </div>
            </div>

            {/* Info */}
            <div className="flex-1 text-center sm:text-left">
              <p className="text-sm mb-1" style={{ color: 'var(--text-dim)' }}>Candidate</p>
              <h1 className="font-display text-2xl font-bold mb-2" style={{ color: 'var(--text)' }}>
                {summary.candidate_name || 'Anonymous Candidate'}
              </h1>
              <div className="flex items-center justify-center sm:justify-start gap-3 flex-wrap">
                <span className="text-sm px-3 py-1 rounded-full"
                  style={{ background: 'var(--surface2)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
                  {roleLabel}
                </span>
                <span className="text-sm px-3 py-1 rounded-full"
                  style={{ background: 'var(--surface2)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
                  {summary.total_questions} questions
                </span>
                {summary.recommendation && (
                  <span className={`text-sm font-semibold px-3 py-1 rounded-full ${getRecClass(summary.recommendation)}`}>
                    {summary.recommendation}
                  </span>
                )}
              </div>
            </div>
          </div>

          {summary.overall_assessment && (
            <div style={{ marginTop: '28px', paddingTop: '28px', borderTop: '1px solid rgba(124,131,255,0.18)' }}>
              <p className="text-xs font-semibold uppercase tracking-wider mb-2.5" style={{ color: 'var(--text-dim)', letterSpacing: '0.08em' }}>
                Overall Assessment
              </p>
              <p className="leading-relaxed" style={{ color: 'var(--text)' }}>{summary.overall_assessment}</p>
            </div>
          )}
        </div>

        {/* 3-col stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '20px' }}>
          <StatCard title="Strengths" icon="💪" iconColor="rgba(52,211,153,0.15)">
            {summary.strengths.length > 0 ? (
              <ul style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {summary.strengths.map((s, i) => (
                  <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '14px' }}>
                    <span style={{ color: 'var(--success)', marginTop: '2px' }}>✓</span>
                    <span style={{ color: 'var(--text)' }}>{s}</span>
                  </li>
                ))}
              </ul>
            ) : <Empty />}
          </StatCard>

          <StatCard title="Areas to Improve" icon="🎯" iconColor="rgba(251,191,36,0.15)">
            {summary.improvements.length > 0 ? (
              <ul style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {summary.improvements.map((s, i) => (
                  <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '14px' }}>
                    <span style={{ color: 'var(--warning)', marginTop: '2px' }}>→</span>
                    <span style={{ color: 'var(--text)' }}>{s}</span>
                  </li>
                ))}
              </ul>
            ) : <Empty />}
          </StatCard>

          <StatCard title="Topics Covered" icon="📚" iconColor="rgba(124,131,255,0.15)">
            {summary.topics_covered.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {summary.topics_covered.map((t, i) => (
                  <span key={i} style={{
                    fontSize: '12px', padding: '4px 10px', borderRadius: '99px',
                    background: 'rgba(124,131,255,0.12)', color: '#a5b4fc',
                    border: '1px solid rgba(124,131,255,0.22)'
                  }}>
                    {t}
                  </span>
                ))}
              </div>
            ) : <Empty />}
          </StatCard>
        </div>

        {/* Knowledge-Gap Radar */}
        {summary.topic_mastery && summary.topic_mastery.length >= 3 && (
          <div className="glass-card p-7 mb-5 animate-fade-up">
            <div className="flex items-center gap-2.5 mb-1">
              <span className="font-display text-lg font-bold" style={{ color: 'var(--text)' }}>🧭 Knowledge-Gap Map</span>
            </div>
            <p className="text-sm mb-4" style={{ color: 'var(--text-muted)' }}>
              Per-topic mastery scored live against the reference books — bigger area means stronger command.
            </p>
            <div className="flex flex-col md:flex-row items-center gap-6">
              <RadarChart data={summary.topic_mastery} />
              <div className="flex-1 w-full space-y-2">
                {summary.topic_mastery.map((t, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <span className="text-sm flex-1 truncate" style={{ color: 'var(--text)' }}>{t.topic}</span>
                    <div className="w-28 h-2 rounded-full overflow-hidden flex-shrink-0" style={{ background: 'rgba(124,131,255,0.12)' }}>
                      <div style={{ width: `${(t.score / 10) * 100}%`, height: '100%', background: barColor(t.score), borderRadius: '99px' }} />
                    </div>
                    <span className="text-xs font-bold tabular-nums w-10 text-right flex-shrink-0" style={{ color: barColor(t.score) }}>
                      {t.score.toFixed(1)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Full analysis */}
        {summary.full_analysis && (
          <div className="glass-card p-7 mb-5 animate-fade-up">
            <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-dim)' }}>
              Detailed Analysis
            </p>
            <p className="leading-relaxed" style={{ color: 'var(--text)', fontSize: '15px' }}>{summary.full_analysis}</p>
          </div>
        )}

        {/* Q&A Transcript */}
        <div className="animate-fade-up">
          <h2 className="font-display text-lg font-bold mb-4 flex items-center gap-2" style={{ color: 'var(--text)' }}>
            <span>💬</span> Interview Transcript
          </h2>
          <div className="space-y-3">
            {summary.questions.map((q, i) => (
              <div key={q.id} className="glass-card overflow-hidden">
                <button
                  onClick={() => setExpandedQ(expandedQ === i ? null : i)}
                  className="w-full px-5 sm:px-6 py-4 flex items-center gap-3 text-left transition-all"
                  style={{ background: expandedQ === i ? 'rgba(124,131,255,0.06)' : 'transparent' }}
                >
                  <span className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0"
                    style={{ background: 'rgba(124,131,255,0.15)', color: '#a5b4fc' }}>
                    {q.question_number}
                  </span>
                  <p className="flex-1 text-sm font-medium truncate" style={{ color: 'var(--text)' }}>
                    {q.question_text}
                  </p>
                  {q.score !== null && q.score !== undefined && (
                    <span className="text-xs font-bold tabular-nums px-2 py-0.5 rounded-full flex-shrink-0"
                      style={{ background: `${barColor(q.score)}1a`, color: barColor(q.score) }}>
                      {q.score.toFixed(1)}
                    </span>
                  )}
                  {q.question_type && (
                    <span className="type-badge hidden sm:block"
                      style={{ background: 'rgba(124,131,255,0.1)', color: '#a5b4fc' }}>
                      {q.question_type}
                    </span>
                  )}
                  <span className="flex-shrink-0 transition-transform" style={{
                    color: 'var(--text-dim)',
                    transform: expandedQ === i ? 'rotate(180deg)' : 'rotate(0)',
                  }}>▾</span>
                </button>

                {expandedQ === i && (
                  <div className="px-5 sm:px-6 pb-5 animate-fade-in">
                    <div className="divider mb-4" />
                    <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-dim)' }}>Question</p>
                    <p className="text-sm leading-relaxed mb-4" style={{ color: 'var(--text)' }}>{q.question_text}</p>
                    <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-dim)' }}>Your Answer</p>
                    <div className="bubble-user rounded-2xl px-4 py-3.5">
                      <p className="text-sm leading-relaxed" style={{ color: 'var(--text)' }}>
                        {q.answer_text || <em style={{ color: 'var(--text-dim)' }}>No answer provided</em>}
                      </p>
                    </div>
                    {q.feedback && (
                      <div className="mt-3 flex items-start gap-2.5">
                        <span className="text-xs font-bold tabular-nums px-2 py-1 rounded-lg flex-shrink-0"
                          style={{ background: `${barColor(q.score ?? 0)}1a`, color: barColor(q.score ?? 0) }}>
                          {(q.score ?? 0).toFixed(1)}/10
                        </span>
                        <p className="text-sm leading-relaxed" style={{ color: 'var(--text-muted)' }}>
                          <span style={{ color: 'var(--text-dim)' }}>AI feedback: </span>{q.feedback}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="mt-9 text-center">
          <button onClick={() => router.push('/')} className="btn-primary">
            Start New Interview <span>→</span>
          </button>
        </div>
      </main>

      <footer className="text-center py-6 text-xs" style={{ color: 'var(--text-dim)' }}>
        Built for PGAGI · FastAPI + Next.js + ChromaDB + Gemini
      </footer>
    </div>
  );
}

function StatCard({ title, icon, iconColor, children }: { title: string; icon: string; iconColor: string; children: React.ReactNode }) {
  return (
    <div className="glass-card glass-card-hover p-5">
      <div className="flex items-center gap-2.5 mb-4">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-base flex-shrink-0" style={{ background: iconColor }}>
          {icon}
        </div>
        <p className="text-sm font-semibold" style={{ color: 'var(--text)' }}>{title}</p>
      </div>
      {children}
    </div>
  );
}

function Empty() {
  return <p className="text-sm" style={{ color: 'var(--text-dim)' }}>—</p>;
}

function barColor(score: number): string {
  if (score >= 7.5) return '#34d399';
  if (score >= 5) return '#60a5fa';
  if (score >= 3) return '#fbbf24';
  return '#fb7185';
}

function RadarChart({ data }: { data: { topic: string; score: number }[] }) {
  const size = 260;
  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - 50;
  const n = data.length;
  const levels = 5;

  const angleFor = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2;
  const point = (i: number, r: number) => ({
    x: cx + r * Math.cos(angleFor(i)),
    y: cy + r * Math.sin(angleFor(i)),
  });

  // grid rings
  const rings = Array.from({ length: levels }, (_, l) => {
    const r = (radius * (l + 1)) / levels;
    const pts = data.map((_, i) => point(i, r));
    return pts.map(p => `${p.x},${p.y}`).join(' ');
  });

  // data polygon
  const dataPts = data.map((d, i) => point(i, (Math.max(0, Math.min(10, d.score)) / 10) * radius));
  const dataPath = dataPts.map(p => `${p.x},${p.y}`).join(' ');

  return (
    <svg width={size} height={size} className="flex-shrink-0" style={{ overflow: 'visible' }}>
      <defs>
        <radialGradient id="radarFill" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#7c83ff" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#b061ff" stopOpacity="0.2" />
        </radialGradient>
      </defs>

      {/* grid rings */}
      {rings.map((pts, l) => (
        <polygon key={l} points={pts} fill="none" stroke="rgba(124,131,255,0.12)" strokeWidth="1" />
      ))}

      {/* spokes + labels */}
      {data.map((d, i) => {
        const outer = point(i, radius);
        const labelPt = point(i, radius + 22);
        const anchor = Math.abs(labelPt.x - cx) < 10 ? 'middle' : labelPt.x > cx ? 'start' : 'end';
        return (
          <g key={i}>
            <line x1={cx} y1={cy} x2={outer.x} y2={outer.y} stroke="rgba(124,131,255,0.1)" strokeWidth="1" />
            <text x={labelPt.x} y={labelPt.y} fontSize="9" fill="var(--text-muted)" textAnchor={anchor} dominantBaseline="middle">
              {d.topic.length > 14 ? d.topic.slice(0, 13) + '…' : d.topic}
            </text>
          </g>
        );
      })}

      {/* data area */}
      <polygon points={dataPath} fill="url(#radarFill)" stroke="#a5b4fc" strokeWidth="2" className="score-ring" />
      {dataPts.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="3" fill="#c4b5fd" />
      ))}
    </svg>
  );
}
