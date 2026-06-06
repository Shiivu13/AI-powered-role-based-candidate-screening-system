'use client';

import { useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { createSession } from '../lib/api';
import { ROLE_LABELS, ROLE_DESCRIPTIONS, Role } from '../lib/types';

const ROLES: Role[] = ['ai_ml', 'data_science', 'backend'];

const ROLE_ICONS: Record<string, string> = {
  ai_ml: '🧠',
  data_science: '📊',
  backend: '⚙️',
};

const ROLE_GRADIENTS: Record<string, string> = {
  ai_ml: 'linear-gradient(135deg, #7c83ff, #b061ff)',
  data_science: 'linear-gradient(135deg, #34d399, #06b6d4)',
  backend: 'linear-gradient(135deg, #fb7185, #f59e0b)',
};

export default function HomePage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<'upload' | 'role'>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [candidateName, setCandidateName] = useState('');
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);

  const handleFile = (f: File) => {
    if (!f.name.match(/\.(pdf|txt)$/i)) {
      setError('Please upload a PDF or TXT file.');
      return;
    }
    if (f.size > 5 * 1024 * 1024) {
      setError('File must be under 5MB.');
      return;
    }
    setFile(f);
    setError('');
    setStep('role');
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const handleStart = async () => {
    if (!file || !selectedRole) return;
    setLoading(true);
    setError('');
    try {
      const session = await createSession(file, selectedRole, candidateName);
      router.push(`/interview/${session.session_id}`);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })
        ?.response?.data?.detail || 'Failed to start interview. Make sure the backend is running.';
      setError(msg);
      setLoading(false);
    }
  };

  const steps = ['Upload', 'Role', 'Interview'];
  const activeStep = step === 'upload' ? 0 : 1;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center text-base font-bold avatar-ai">
            S
          </div>
          <div>
            <span className="font-display font-bold text-lg" style={{ color: 'var(--text)' }}>Sage</span>
            <span className="text-xs ml-2" style={{ color: 'var(--text-dim)' }}>AI Interviewer</span>
          </div>
          <div className="ml-auto flex items-center gap-2 text-xs px-3 py-1.5 rounded-full"
            style={{ background: 'var(--surface2)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--success)' }} />
            Powered by RAG
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-2xl mx-auto w-full px-6 py-10 sm:py-14">
        {/* Hero */}
        <div className="text-center mb-10 animate-fade-up">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full mb-6 text-xs font-medium"
            style={{ background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
            <span>✨</span> Dynamic questions from technical reference books
          </div>
          <h1 className="font-display text-4xl sm:text-5xl font-extrabold mb-4 leading-tight">
            <span className="gradient-text-animated">Ace your technical</span>
            <br />
            <span style={{ color: 'var(--text)' }}>interview with AI</span>
          </h1>
          <p className="text-base max-w-md mx-auto" style={{ color: 'var(--text-muted)' }}>
            Upload your resume, pick a role, and get a personalized interview where every
            question is grounded in your experience.
          </p>
        </div>

        {/* Steps indicator */}
        <div className="flex items-center justify-center gap-3 mb-10 animate-fade-in">
          {steps.map((s, i) => (
            <div key={s} className="flex items-center gap-3">
              <div className="flex items-center gap-2.5">
                <div className={`step-dot ${i === activeStep ? 'active' : i < activeStep ? 'done' : 'idle'}`}>
                  {i < activeStep ? '✓' : i + 1}
                </div>
                <span className="text-sm font-medium hidden sm:block"
                  style={{ color: i === activeStep ? 'var(--text)' : 'var(--text-dim)' }}>{s}</span>
              </div>
              {i < steps.length - 1 && (
                <div className="w-8 sm:w-12 h-px" style={{
                  background: i < activeStep ? 'var(--accent)' : 'var(--border)'
                }} />
              )}
            </div>
          ))}
        </div>

        {/* Step 1: Upload */}
        {step === 'upload' && (
          <div className="glass-card p-7 sm:p-8 animate-scale-in">
            <div className="mb-6">
              <label className="block text-sm font-semibold mb-2.5" style={{ color: 'var(--text)' }}>
                Your name <span style={{ color: 'var(--text-dim)' }}>(optional)</span>
              </label>
              <input
                type="text"
                value={candidateName}
                onChange={e => setCandidateName(e.target.value)}
                placeholder="e.g. Aditya Sharma"
                className="input-field"
              />
            </div>

            <label className="block text-sm font-semibold mb-2.5" style={{ color: 'var(--text)' }}>
              Resume <span style={{ color: 'var(--accent)' }}>*</span>
            </label>
            <div
              className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
            >
              <div className="relative z-10">
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center text-3xl avatar-ai">
                  📄
                </div>
                <p className="font-semibold mb-1" style={{ color: 'var(--text)' }}>
                  Drop your resume here
                </p>
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                  or <span style={{ color: 'var(--accent)' }}>click to browse</span> · PDF or TXT · max 5MB
                </p>
              </div>
              <input ref={fileInputRef} type="file" accept=".pdf,.txt" className="hidden"
                onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
            </div>

            {error && (
              <p className="mt-4 text-sm text-center px-4 py-2 rounded-lg"
                style={{ color: 'var(--danger)', background: 'rgba(251,113,133,0.1)' }}>{error}</p>
            )}
          </div>
        )}

        {/* Step 2: Role Selection */}
        {step === 'role' && (
          <div className="animate-scale-in">
            {/* File confirmed */}
            <div className="glass-card p-4 mb-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center text-lg flex-shrink-0"
                style={{ background: 'rgba(52,211,153,0.15)', border: '1px solid rgba(52,211,153,0.3)' }}>
                ✓
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold truncate" style={{ color: 'var(--text)' }}>{file?.name}</p>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {((file?.size || 0) / 1024).toFixed(1)} KB · ready to analyze
                </p>
              </div>
              <button onClick={() => { setFile(null); setStep('upload'); }} className="btn-ghost flex-shrink-0">
                Change
              </button>
            </div>

            <div className="glass-card p-7 sm:p-8">
              <h2 className="font-display text-xl font-bold mb-1.5" style={{ color: 'var(--text)' }}>
                Choose your target role
              </h2>
              <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>
                Questions are tailored to this role using a domain-specific knowledge base.
              </p>

              <div className="grid gap-3 mb-7 stagger">
                {ROLES.map(role => (
                  <div key={role} className={`role-card ${selectedRole === role ? 'selected' : ''}`}
                    onClick={() => setSelectedRole(role)}>
                    <div className="flex items-center gap-4 relative z-10">
                      <div className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl flex-shrink-0"
                        style={{ background: ROLE_GRADIENTS[role], boxShadow: '0 8px 20px -8px rgba(0,0,0,0.5)' }}>
                        {ROLE_ICONS[role]}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-display font-semibold" style={{ color: 'var(--text)' }}>{ROLE_LABELS[role]}</p>
                        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>{ROLE_DESCRIPTIONS[role]}</p>
                      </div>
                      <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs flex-shrink-0 transition-all`}
                        style={{
                          background: selectedRole === role ? 'var(--accent)' : 'transparent',
                          border: selectedRole === role ? 'none' : '2px solid var(--border-strong)',
                          color: 'white',
                        }}>
                        {selectedRole === role && '✓'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {error && (
                <p className="mb-4 text-sm text-center px-4 py-2 rounded-lg"
                  style={{ color: 'var(--danger)', background: 'rgba(251,113,133,0.1)' }}>{error}</p>
              )}

              <button className="btn-primary w-full" disabled={!selectedRole || loading} onClick={handleStart}>
                {loading ? (
                  <>
                    <div className="flex gap-1.5">
                      <div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" />
                    </div>
                    Analyzing resume & generating questions…
                  </>
                ) : (
                  <>Start Interview <span>→</span></>
                )}
              </button>

              <div className="flex items-center justify-center gap-4 mt-4 text-xs" style={{ color: 'var(--text-dim)' }}>
                <span className="flex items-center gap-1.5">⏱ ~10 min</span>
                <span className="flex items-center gap-1.5">💬 7 questions</span>
                <span className="flex items-center gap-1.5">🎯 Adaptive</span>
              </div>
            </div>
          </div>
        )}

        {/* Feature row */}
        <div className="grid grid-cols-3 gap-3 mt-8 stagger">
          {[
            { icon: '🔍', title: 'RAG-Powered', desc: 'Grounded in textbooks' },
            { icon: '🎯', title: 'Personalized', desc: 'Based on your resume' },
            { icon: '📈', title: 'Scored', desc: 'Detailed analysis' },
          ].map(f => (
            <div key={f.title} className="glass-card glass-card-hover p-4 text-center">
              <div className="text-2xl mb-2">{f.icon}</div>
              <p className="text-sm font-semibold" style={{ color: 'var(--text)' }}>{f.title}</p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </main>

      <footer className="text-center py-6 text-xs" style={{ color: 'var(--text-dim)' }}>
        Built for PGAGI · FastAPI + Next.js + ChromaDB + Gemini
      </footer>
    </div>
  );
}
