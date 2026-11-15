import type { PlanItem, Profile } from "../api/types";
import { Card, Chip, DifficultyChip } from "./ui";

const SOURCE_LABEL: Record<PlanItem["source"], { label: string; tone: string; hint: string }> = {
  resume: { label: "Resume claim", tone: "blue", hint: "Verifies a skill the resume claims" },
  core: { label: "Core gap", tone: "purple", hint: "Core competency for the role, probing a gap" },
  breadth: { label: "Breadth", tone: "neutral", hint: "Breadth check" },
};

export function ProfileCard({ profile, roleTitle }: { profile: Profile; roleTitle: string }) {
  const evidence = Object.entries(profile.skill_evidence ?? {}).sort((a, b) => b[1].mentions - a[1].mentions);
  return (
    <Card
      title="Extracted candidate profile"
      actions={<Chip tone="neutral">{profile.extraction?.mode === "heuristic" ? "Taxonomy extraction" : "LLM + taxonomy"}</Chip>}
    >
      {profile.headline && <p className="lead">{profile.headline}</p>}
      <dl className="facts">
        <div>
          <dt>Seniority</dt>
          <dd className="cap">{profile.seniority}</dd>
        </div>
        <div>
          <dt>Experience</dt>
          <dd>{profile.years_experience != null ? `${profile.years_experience} yrs` : "—"}</dd>
        </div>
        <div>
          <dt>Target role</dt>
          <dd>{roleTitle}</dd>
        </div>
      </dl>
      <h4>Skills & concepts</h4>
      <div className="chips">
        {profile.skills.length ? profile.skills.map((s) => <Chip key={s} tone="blue">{s}</Chip>) : <span className="muted">None detected</span>}
      </div>
      <h4>Technologies</h4>
      <div className="chips">
        {profile.technologies.length ? profile.technologies.map((s) => <Chip key={s}>{s}</Chip>) : <span className="muted">None detected</span>}
      </div>
      {profile.domains.length > 0 && (
        <>
          <h4>Domain exposure</h4>
          <div className="chips">
            {profile.domains.map((d) => (
              <Chip key={d} tone="green">
                {d}
              </Chip>
            ))}
          </div>
        </>
      )}
      {profile.projects?.length > 0 && (
        <>
          <h4>Projects</h4>
          <ul className="tight">
            {profile.projects.map((p) => (
              <li key={p.name}>
                <strong>{p.name}</strong> — <span className="muted">{p.summary}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {evidence.length > 0 && (
        <details className="details">
          <summary>Skill evidence counts ({evidence.length})</summary>
          <div className="chips">
            {evidence.map(([k, v]) => (
              <Chip key={k} title={v.category}>
                {k} × {v.mentions}
              </Chip>
            ))}
          </div>
        </details>
      )}
    </Card>
  );
}

export function PlanList({ plan, activeIndex }: { plan: PlanItem[]; activeIndex?: number }) {
  return (
    <ol className="plan">
      {plan.map((p) => {
        const src = SOURCE_LABEL[p.source];
        return (
          <li key={p.index} className={activeIndex === p.index ? "active" : activeIndex != null && p.index < activeIndex ? "past" : ""}>
            <div className="plan-head">
              <span className="plan-num">{p.index + 1}</span>
              <strong>{p.topic_name}</strong>
              <Chip tone={src.tone} title={src.hint}>
                {src.label}
              </Chip>
              <DifficultyChip level={p.difficulty} label={p.difficulty_label} />
              <Chip>{p.question_type}</Chip>
            </div>
            <div className="muted small plan-reason">{p.reason}</div>
            <details className="details small">
              <summary>Retrieval queries</summary>
              <ul className="mono tight">
                {p.queries.map((q) => (
                  <li key={q}>{q}</li>
                ))}
              </ul>
            </details>
          </li>
        );
      })}
    </ol>
  );
}
