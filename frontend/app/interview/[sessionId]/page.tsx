'use client';

import { useState, useEffect, useRef, use } from 'react';
import { useRouter } from 'next/navigation';
import { submitAnswer, getSession, forceComplete } from '../../../lib/api';
import { Question, RetrievalMeta, AnswerEvaluation, ROLE_LABELS } from '../../../lib/types';

interface PageProps {
  params: Promise<{ sessionId: string }>;
}

interface ChatMessage {
  type: 'question' | 'answer';
  text: string;
  questionNumber?: number;
  questionType?: string;
  evaluation?: AnswerEvaluation | null;
}

const TYPE_COLORS: Record<string, string> = {
  conceptual: '#a5b4fc',
  applied: '#6ee7b7',
  'problem-solving': '#fbbf24',
  experiential: '#f9a8d4',
};

const DIFF_COLORS: Record<string, string> = {
  beginner: '#6ee7b7',
  'beginner-to-intermediate': '#7dd3fc',
  intermediate: '#fbbf24',
  advanced: '#fb7185',
};

function scoreColor(s: number | null | undefined): string {
  if (s === null || s === undefined) return 'var(--text-muted)';
  if (s >= 7.5) return '#34d399';
  if (s >= 5) return '#60a5fa';
  if (s >= 3) return '#fbbf24';
  return '#fb7185';
}

export default function InterviewPage({ params }: PageProps) {
  const { sessionId } = use(params);
  const router = useRouter();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [currentMeta, setCurrentMeta] = useState<RetrievalMeta | null>(null);
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [sessionInfo, setSessionInfo] = useState<{ role: string; candidateName: string | null } | null>(null);
  const [questionNumber, setQuestionNumber] = useState(1);
  const [totalQuestions] = useState(7);
  const [isComplete, setIsComplete] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false); // mobile glass-box toggle

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { loadSession(); }, [sessionId]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, submitting]);

  const loadSession = async () => {
    try {
      const session = await getSession(sessionId);
      setSessionInfo({ role: session.role, candidateName: session.candidate_name });

      const msgs: ChatMessage[] = [];
      for (const q of session.questions) {
        msgs.push({ type: 'question', text: q.question_text, questionNumber: q.question_number, questionType: q.question_type || undefined });
        if (q.answer_text) {
          msgs.push({ type: 'answer', text: q.answer_text, evaluation: { score: q.score ?? null, feedback: q.feedback ?? null, detail: q.eval_detail } });
        }
      }

      if (session.status === 'completed') {
        setIsComplete(true);
        setMessages(msgs);
        setLoading(false);
        return;
      }

      const unansweredQ = session.questions.find(q => !q.answer_text);
      if (unansweredQ) {
        setCurrentQuestion(unansweredQ);
        setCurrentMeta(unansweredQ.retrieval_meta || null);
        setQuestionNumber(unansweredQ.question_number);
      }
      setMessages(msgs);
      setLoading(false);
    } catch {
      setError('Could not load session. Please go back and try again.');
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!answer.trim() || submitting || !currentQuestion) return;
    const myAnswer = answer.trim();
    setAnswer('');
    setSubmitting(true);
    setError('');
    setMessages(prev => [...prev, { type: 'answer', text: myAnswer }]);

    try {
      const res = await submitAnswer(sessionId, myAnswer);

      // attach evaluation to the just-sent answer message
      setMessages(prev => {
        const copy = [...prev];
        for (let i = copy.length - 1; i >= 0; i--) {
          if (copy[i].type === 'answer' && !copy[i].evaluation) {
            copy[i] = { ...copy[i], evaluation: res.last_answer_evaluation || null };
            break;
          }
        }
        return copy;
      });

      if (res.is_complete) {
        setIsComplete(true);
        setCurrentQuestion(null);
        setSubmitting(false);
        return;
      }

      if (res.question) {
        setCurrentQuestion(res.question);
        setCurrentMeta(res.question.retrieval_meta || null);
        setQuestionNumber(res.question.question_number);
        setMessages(prev => [...prev, {
          type: 'question',
          text: res.question!.question_text,
          questionNumber: res.question!.question_number,
          questionType: res.question!.question_type || undefined,
        }]);
      }
    } catch {
      setError('Failed to submit. Please try again.');
      setAnswer(myAnswer);
    } finally {
      setSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleSubmit();
  };

  const handleEndInterview = async () => {
    if (!confirm('End the interview now and view your results?')) return;
    try { await forceComplete(sessionId); } catch { /* proceed */ }
    router.push(`/results/${sessionId}`);
  };

  const answeredCount = messages.filter(m => m.type === 'answer').length;
  const progress = Math.min((answeredCount / totalQuestions) * 100, 100);
  const roleLabel = sessionInfo ? (ROLE_LABELS[sessionInfo.role] || sessionInfo.role) : '';
  const initials = (sessionInfo?.candidateName || 'You').slice(0, 2).toUpperCase();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center animate-fade-in">
          <div className="spinner mx-auto mb-5" />
          <p style={{ color: 'var(--text-muted)' }}>Preparing your interview…</p>
        </div>
      </div>
    );
  }

  if (error && messages.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <div className="glass-card p-8 max-w-md text-center animate-scale-in">
          <div className="text-4xl mb-3">😕</div>
          <p className="mb-5" style={{ color: 'var(--text)' }}>{error}</p>
          <button onClick={() => router.push('/')} className="btn-primary">← Go Back</button>
        </div>
      </div>
    );
  }

  if (isComplete) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <div className="glass-card p-10 max-w-md text-center animate-scale-in">
          <div className="w-20 h-20 mx-auto mb-5 rounded-3xl flex items-center justify-center text-4xl avatar-ai avatar-glow">🎉</div>
          <h2 className="font-display text-2xl font-bold mb-2" style={{ color: 'var(--text)' }}>Interview Complete!</h2>
          <p className="mb-7" style={{ color: 'var(--text-muted)' }}>
            Brilliant work. Sage is now analyzing your responses to build your report.
          </p>
          <button onClick={() => router.push(`/results/${sessionId}`)} className="btn-primary w-full">
            View Your Report <span>→</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b"
        style={{ borderColor: 'var(--border)', background: 'rgba(7,8,15,0.7)', backdropFilter: 'blur(16px)' }}>
        <div className="max-w-6xl mx-auto px-5 sm:px-6 py-3.5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center text-sm font-bold avatar-ai flex-shrink-0">S</div>
            <div className="min-w-0">
              <p className="text-sm font-semibold truncate" style={{ color: 'var(--text)' }}>{sessionInfo?.candidateName || 'Candidate'}</p>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{roleLabel}</p>
            </div>
            <div className="ml-auto flex items-center gap-2.5 flex-shrink-0">
              <button onClick={() => setPanelOpen(o => !o)} className="btn-ghost lg:hidden">🔍 Reasoning</button>
              <span className="hidden sm:flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full"
                style={{ background: 'rgba(52,211,153,0.12)', color: 'var(--success)', border: '1px solid rgba(52,211,153,0.25)' }}>
                <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: 'var(--success)' }} /> Live
              </span>
              <button onClick={handleEndInterview} className="btn-ghost">End</button>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="progress-bar flex-1"><div className="progress-fill" style={{ width: `${progress}%` }} /></div>
            <span className="text-xs font-semibold tabular-nums flex-shrink-0" style={{ color: 'var(--text-muted)' }}>{answeredCount}/{totalQuestions}</span>
          </div>
        </div>
      </header>

      {/* Body: chat + glass-box */}
      <div className="flex-1 max-w-6xl mx-auto w-full grid lg:grid-cols-[1fr_360px] gap-0">
        {/* Chat column */}
        <div className="flex flex-col min-h-0">
          <div className="flex-1 px-5 sm:px-6 py-6 overflow-y-auto">
            {messages.map((msg, i) => (
              <div key={i} className="mb-5">
                {msg.type === 'question' ? (
                  <AIMessage text={msg.text} questionNumber={msg.questionNumber || 0} questionType={msg.questionType} />
                ) : (
                  <UserMessage text={msg.text} initials={initials} evaluation={msg.evaluation} />
                )}
              </div>
            ))}
            {submitting && (
              <div className="mb-5 animate-fade-in">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-xl flex items-center justify-center text-xs font-bold avatar-ai flex-shrink-0">S</div>
                  <div className="bubble-ai px-5 py-4">
                    <div className="flex gap-2 items-center">
                      <div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" />
                      <span className="text-xs ml-1.5" style={{ color: 'var(--text-muted)' }}>Grading your answer & adapting the next question…</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="sticky bottom-0 border-t"
            style={{ borderColor: 'var(--border)', background: 'rgba(7,8,15,0.7)', backdropFilter: 'blur(16px)' }}>
            <div className="px-5 sm:px-6 py-4">
              {error && <p className="text-sm mb-2 px-3 py-1.5 rounded-lg" style={{ color: 'var(--danger)', background: 'rgba(251,113,133,0.1)' }}>{error}</p>}
              <div className="flex gap-3 items-end">
                <textarea
                  value={answer}
                  onChange={e => setAnswer(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Type your answer…"
                  rows={3}
                  className="input-field resize-none w-full"
                  style={{ lineHeight: '1.6' }}
                  disabled={submitting}
                />
                <button onClick={handleSubmit} disabled={!answer.trim() || submitting} className="btn-primary flex-shrink-0"
                  style={{ height: '88px', width: '80px', padding: 0 }} aria-label="Submit">
                  {submitting ? <div className="flex gap-1"><div className="typing-dot" /><div className="typing-dot" /></div> : <span className="text-2xl">↑</span>}
                </button>
              </div>
              <p className="text-xs mt-2 flex items-center gap-1.5" style={{ color: 'var(--text-dim)' }}>
                <kbd className="px-1.5 py-0.5 rounded text-[10px]" style={{ background: 'var(--surface2)', border: '1px solid var(--border)' }}>Ctrl</kbd>+
                <kbd className="px-1.5 py-0.5 rounded text-[10px]" style={{ background: 'var(--surface2)', border: '1px solid var(--border)' }}>Enter</kbd> to send
              </p>
            </div>
          </div>
        </div>

        {/* Glass-box panel (desktop) */}
        <aside className="hidden lg:block border-l" style={{ borderColor: 'var(--border)' }}>
          <div className="sticky top-[88px] p-5 max-h-[calc(100vh-88px)] overflow-y-auto">
            <GlassBox meta={currentMeta} qType={currentQuestion?.question_type} />
          </div>
        </aside>
      </div>

      {/* Glass-box panel (mobile overlay) */}
      {panelOpen && (
        <div className="lg:hidden fixed inset-0 z-30 flex items-end" style={{ background: 'rgba(0,0,0,0.5)' }} onClick={() => setPanelOpen(false)}>
          <div className="w-full max-h-[80vh] overflow-y-auto rounded-t-3xl p-5 animate-fade-up"
            style={{ background: 'var(--surface-solid)', borderTop: '1px solid var(--border-strong)' }} onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <span className="font-display font-semibold" style={{ color: 'var(--text)' }}>Interviewer's Reasoning</span>
              <button onClick={() => setPanelOpen(false)} className="btn-ghost">Close</button>
            </div>
            <GlassBox meta={currentMeta} qType={currentQuestion?.question_type} />
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------- Glass-box / Explainable-RAG panel ---------- */
function GlassBox({ meta, qType }: { meta: RetrievalMeta | null; qType?: string | null }) {
  if (!meta) {
    return (
      <div className="glass-card p-5 text-center">
        <div className="text-2xl mb-2">🔍</div>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>The interviewer's reasoning for each question appears here.</p>
      </div>
    );
  }
  const diffColor = meta.difficulty ? (DIFF_COLORS[meta.difficulty] || 'var(--text-muted)') : 'var(--text-muted)';

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center gap-2">
        <span className="text-sm font-display font-bold" style={{ color: 'var(--text)' }}>🔍 Why this question?</span>
      </div>
      <p className="text-xs" style={{ color: 'var(--text-dim)' }}>
        Live look at the RAG pipeline — how Sage chose this question.
      </p>

      {/* chips */}
      <div className="flex flex-wrap gap-2">
        {meta.difficulty && (
          <span className="type-badge" style={{ background: `${diffColor}1a`, color: diffColor, border: `1px solid ${diffColor}40` }}>
            ⚡ {meta.difficulty}
          </span>
        )}
        {qType && (
          <span className="type-badge" style={{ background: 'rgba(124,131,255,0.12)', color: '#a5b4fc', border: '1px solid rgba(124,131,255,0.3)' }}>
            {qType}
          </span>
        )}
      </div>

      {/* adaptive reasoning */}
      {meta.reasoning && (
        <div className="glass-card p-4">
          <p className="text-[11px] font-semibold uppercase tracking-wider mb-1.5" style={{ color: 'var(--text-dim)' }}>Adaptive Decision</p>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text)' }}>{meta.reasoning}</p>
        </div>
      )}

      {/* retrieval query */}
      {meta.query && (
        <div className="glass-card p-4">
          <p className="text-[11px] font-semibold uppercase tracking-wider mb-1.5" style={{ color: 'var(--text-dim)' }}>Retrieval Query</p>
          <code className="text-xs leading-relaxed block" style={{ color: '#a5b4fc' }}>{meta.query}</code>
        </div>
      )}

      {/* sources */}
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-dim)' }}>
          Retrieved from Knowledge Base ({meta.sources.length})
        </p>
        <div className="space-y-2.5">
          {meta.sources.map((s, i) => (
            <div key={i} className="glass-card p-3.5">
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <span className="text-xs font-semibold truncate" style={{ color: '#c4b5fd' }}>📖 {s.book}</span>
                {s.similarity !== null && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full flex-shrink-0 tabular-nums"
                    style={{ background: 'rgba(52,211,153,0.12)', color: 'var(--success)' }}>
                    {Math.round((s.similarity || 0) * 100)}% match
                  </span>
                )}
              </div>
              <p className="text-xs leading-relaxed" style={{ color: 'var(--text-muted)' }}>{s.snippet}…</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AIMessage({ text, questionNumber, questionType }: { text: string; questionNumber: number; questionType?: string }) {
  const typeColor = questionType ? TYPE_COLORS[questionType] || 'var(--text-muted)' : 'var(--text-muted)';
  return (
    <div className="flex items-start gap-3 animate-slide-in">
      <div className="w-9 h-9 rounded-xl flex items-center justify-center text-sm font-bold avatar-ai flex-shrink-0">S</div>
      <div style={{ maxWidth: '88%' }}>
        {questionNumber > 0 && (
          <div className="flex items-center gap-2 mb-1.5 ml-1">
            <span className="text-xs font-semibold" style={{ color: 'var(--text-dim)' }}>Question {questionNumber}</span>
            {questionType && (
              <span className="type-badge" style={{ background: `${typeColor}1a`, color: typeColor, border: `1px solid ${typeColor}33` }}>{questionType}</span>
            )}
          </div>
        )}
        <div className="bubble-ai px-5 py-4"><p className="leading-relaxed" style={{ color: 'var(--text)', fontSize: '15px' }}>{text}</p></div>
      </div>
    </div>
  );
}

function UserMessage({ text, initials, evaluation }: { text: string; initials: string; evaluation?: AnswerEvaluation | null }) {
  const sc = evaluation?.score;
  return (
    <div className="flex items-start gap-3 flex-row-reverse animate-fade-in">
      <div className="w-9 h-9 rounded-xl flex items-center justify-center text-xs font-bold flex-shrink-0"
        style={{ background: 'var(--surface2)', color: 'var(--text-muted)', border: '1px solid var(--border-strong)' }}>{initials}</div>
      <div style={{ maxWidth: '88%' }}>
        <div className="bubble-user px-5 py-4"><p className="leading-relaxed" style={{ color: 'var(--text)', fontSize: '15px' }}>{text}</p></div>
        {evaluation && sc !== null && sc !== undefined && (
          <div className="mt-2 flex items-start gap-2 justify-end animate-fade-in">
            <div className="glass-card px-3 py-2 flex items-center gap-2.5" style={{ maxWidth: '100%' }}>
              <span className="text-xs font-bold tabular-nums flex-shrink-0" style={{ color: scoreColor(sc) }}>{sc.toFixed(1)}/10</span>
              {evaluation.feedback && (
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{evaluation.feedback}</span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
