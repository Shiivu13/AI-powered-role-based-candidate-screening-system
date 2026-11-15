import { useEffect, useState, type ReactNode } from "react";

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="spinner-wrap" role="status">
      <span className="spinner" aria-hidden />
      {label && <span>{label}</span>}
    </span>
  );
}

export function ErrorBanner({ message, onClose }: { message: string; onClose?: () => void }) {
  return (
    <div className="banner banner-error" role="alert">
      <span>{message}</span>
      {onClose && (
        <button className="link" onClick={onClose} aria-label="Dismiss">
          ✕
        </button>
      )}
    </div>
  );
}

export function Chip({ children, tone = "neutral", title }: { children: ReactNode; tone?: string; title?: string }) {
  return (
    <span className={`chip chip-${tone}`} title={title}>
      {children}
    </span>
  );
}

export function Card({ title, actions, children, className = "" }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          {title && <h3>{title}</h3>}
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export const DIFFICULTY_TONE: Record<number, string> = { 1: "green", 2: "amber", 3: "red" };

export function DifficultyChip({ level, label }: { level: number; label: string }) {
  return (
    <Chip tone={DIFFICULTY_TONE[level] ?? "neutral"} title="Question difficulty">
      {"●".repeat(level)}
      {"○".repeat(3 - level)} {label}
    </Chip>
  );
}

export function scoreTone(score: number | null | undefined): string {
  if (score == null) return "neutral";
  if (score >= 7) return "green";
  if (score >= 4.5) return "amber";
  return "red";
}

export function ScoreBadge({ score }: { score: number | null | undefined }) {
  return <span className={`score score-${scoreTone(score)}`}>{score == null ? "—" : score.toFixed(1)}</span>;
}

export function ScoreBar({ score, max = 10 }: { score: number; max?: number }) {
  return (
    <div className="bar" aria-label={`${score} of ${max}`}>
      <div className={`bar-fill fill-${scoreTone(score)}`} style={{ width: `${Math.max(2, (score / max) * 100)}%` }} />
    </div>
  );
}

export function ScoreRing({ score }: { score: number }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  return (
    <svg className={`ring ring-${scoreTone(score)}`} viewBox="0 0 120 120" width="132" height="132" role="img" aria-label={`Score ${score} of 10`}>
      <circle cx="60" cy="60" r={r} className="ring-track" />
      <circle cx="60" cy="60" r={r} className="ring-value" strokeDasharray={`${(score / 10) * c} ${c}`} transform="rotate(-90 60 60)" />
      <text x="60" y="58" textAnchor="middle" className="ring-text">
        {score.toFixed(1)}
      </text>
      <text x="60" y="78" textAnchor="middle" className="ring-sub">
        / 10
      </text>
    </svg>
  );
}

export function Elapsed({ since }: { since: string }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const start = new Date(since.endsWith("Z") || since.includes("+") ? since : `${since}Z`).getTime();
  const secs = Math.max(0, Math.floor((now - start) / 1000));
  return (
    <span className="muted mono">
      ⏱ {Math.floor(secs / 60)}:{String(secs % 60).padStart(2, "0")}
    </span>
  );
}

const STAGES = ["Setup", "Profile & plan", "Interview", "Report"];

export function Stepper({ active }: { active: number }) {
  return (
    <ol className="stepper">
      {STAGES.map((s, i) => (
        <li key={s} className={i < active ? "done" : i === active ? "active" : ""}>
          <span className="step-dot">{i < active ? "✓" : i + 1}</span>
          {s}
        </li>
      ))}
    </ol>
  );
}
