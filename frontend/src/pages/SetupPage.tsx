import { useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { JobRolePreview, Role, RoleFit } from "../api/types";
import { BookIcon, FileIcon, UploadIcon } from "../components/icons";
import { Card, Chip, ErrorBanner, Spinner, Stepper } from "../components/ui";

const PROCESSING_STEPS = [
  "Uploading resume",
  "Extracting skills, technologies and domains",
  "Matching your background against the role's topics",
  "Building a personalised interview plan",
];

export default function SetupPage() {
  const navigate = useNavigate();
  const [roles, setRoles] = useState<Role[] | null>(null);
  const [roleId, setRoleId] = useState<string>("");
  const [name, setName] = useState("");
  const [numQuestions, setNumQuestions] = useState(6);
  const [interviewMode, setInterviewMode] = useState<"practice" | "assessment">("practice");
  const [mode, setMode] = useState<"file" | "text">("file");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [fits, setFits] = useState<Record<string, RoleFit>>({});
  const [analyzing, setAnalyzing] = useState(false);
  const [roleTouched, setRoleTouched] = useState(false);
  const [jd, setJd] = useState("");
  const [jdPreview, setJdPreview] = useState<JobRolePreview | null>(null);
  const [jdBusy, setJdBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const isCustom = roleId === "custom";

  // Score the resume against every role as soon as it is provided, and
  // pre-select the best fit unless the user already picked a role.
  useEffect(() => {
    const source = mode === "file" ? file : text.trim().length >= 80 ? text : null;
    if (!source) {
      setFits({});
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      setAnalyzing(true);
      try {
        const res = await api.analyzeResume(mode === "file" ? file : null, mode === "text" ? text : undefined);
        if (cancelled) return;
        setFits(Object.fromEntries(res.role_fit.map((f) => [f.role_id, f])));
        const best = res.role_fit.find((f) => f.recommended);
        if (best && !roleTouched) setRoleId(best.role_id);
      } catch {
        /* the fit is a convenience; creating the session reports real errors */
      } finally {
        if (!cancelled) setAnalyzing(false);
      }
    }, mode === "file" ? 0 : 800);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [file, text, mode, roleTouched]);

  const jdWords = jd.trim() ? jd.trim().split(/\s+/).length : 0;
  const previewJd = async () => {
    setJdBusy(true);
    setError(null);
    try {
      setJdPreview(await api.roleFromJobDescription(jd));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setJdBusy(false);
    }
  };

  useEffect(() => {
    api
      .roles()
      .then((r) => {
        setRoles(r);
        setRoleId((r.find((x) => x.knowledge_base_ready) ?? r[0])?.id ?? "");
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!submitting) return;
    const t = setInterval(() => setStep((s) => Math.min(s + 1, PROCESSING_STEPS.length - 1)), 900);
    return () => clearInterval(t);
  }, [submitting]);

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) pickFile(f);
  };

  const pickFile = (f: File) => {
    const ok = /\.(pdf|txt|md)$/i.test(f.name);
    if (!ok) return setError("Please upload a PDF, TXT or MD file.");
    if (f.size > 5 * 1024 * 1024) return setError("File is larger than 5 MB.");
    setError(null);
    setFile(f);
  };

  const selectedRole = roles?.find((r) => r.id === roleId);
  const hasResume = mode === "file" ? !!file : text.trim().length >= 80;
  const roleOk = isCustom ? jdWords >= 25 : !!selectedRole?.knowledge_base_ready;
  const canSubmit = roleOk && hasResume && !submitting;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setStep(0);
    setError(null);
    try {
      const session = await api.createSession({
        roleId,
        candidateName: name,
        numQuestions,
        mode: interviewMode,
        jobDescription: isCustom ? jd : undefined,
        resumeFile: mode === "file" ? file : null,
        resumeText: mode === "text" ? text : undefined,
      });
      navigate(`/sessions/${session.id}`);
    } catch (err) {
      setError((err as Error).message);
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <Stepper active={0} />
      <div className="hero">
        <h1>Role-based technical screening</h1>
        <p className="muted">
          Upload a resume and pick a role, or paste any job description. The resume is scored against every role, and
          every question is generated live from the reference textbooks, tailored to the candidate, with page-level
          citations.
        </p>
      </div>

      {error && <ErrorBanner message={error} onClose={() => setError(null)} />}

      <form onSubmit={onSubmit} className="setup-grid">
        <Card title="1. Choose the target role" actions={analyzing ? <Spinner label="Matching resume…" /> : undefined}>
          {!roles ? (
            <Spinner label="Loading roles…" />
          ) : (
            <div className="role-list" role="radiogroup">
              {roles.map((r) => (
                <label key={r.id} className={`role-card ${roleId === r.id ? "selected" : ""} ${!r.knowledge_base_ready ? "disabled" : ""}`}>
                  <input
                    type="radio"
                    name="role"
                    value={r.id}
                    checked={roleId === r.id}
                    disabled={!r.knowledge_base_ready}
                    onChange={() => {
                      setRoleTouched(true);
                      setRoleId(r.id);
                    }}
                  />
                  <div className="grow">
                    <div className="row between">
                      <div className="role-title">{r.title}</div>
                      {fits[r.id] && (
                        <Chip tone={fits[r.id].recommended ? "green" : "neutral"} title="How well the resume covers this role's topics">
                          {fits[r.id].recommended ? "Best fit · " : ""}
                          {fits[r.id].fit}% match
                        </Chip>
                      )}
                    </div>
                    {fits[r.id] && (
                      <div className="fit">
                        <div className="bar">
                          <div className={`bar-fill fill-${fits[r.id].fit >= 50 ? "green" : fits[r.id].fit >= 30 ? "amber" : "red"}`} style={{ width: `${Math.max(3, fits[r.id].fit)}%` }} />
                        </div>
                        <div className="small muted">
                          {fits[r.id].matched_topics.length
                            ? `Resume covers: ${fits[r.id].matched_topics.slice(0, 4).map((m) => m.topic).join(", ")}`
                            : "No topics of this role found on the resume"}
                          {fits[r.id].missing_core_topics.length > 0 && ` · gaps: ${fits[r.id].missing_core_topics.slice(0, 2).join(", ")}`}
                        </div>
                      </div>
                    )}
                    <div className="muted small">{r.description}</div>
                    <div className="book-list">
                      {r.books.map((b) => (
                        <Chip key={b.id} tone={b.chunks ? "blue" : "neutral"} title={b.chunks ? `${b.chunks} chunks indexed` : "Not ingested"}>
                          <BookIcon size={12} /> {b.title}
                          {!b.chunks && " (missing)"}
                        </Chip>
                      ))}
                    </div>
                    <div className="muted small">
                      {r.knowledge_base_ready
                        ? `${r.knowledge_base_chunks.toLocaleString()} knowledge chunks · ${r.topics.length} topics`
                        : "Knowledge base not ingested — run scripts/ingest_kb.py"}
                    </div>
                  </div>
                </label>
              ))}
              <label className={`role-card ${isCustom ? "selected" : ""}`}>
                <input
                  type="radio"
                  name="role"
                  value="custom"
                  checked={isCustom}
                  onChange={() => {
                    setRoleTouched(true);
                    setRoleId("custom");
                  }}
                />
                <div className="grow">
                  <div className="role-title">Custom role from a job description</div>
                  <div className="muted small">
                    Paste any JD. The topics it asks for are extracted and the interview is grounded in every knowledge base that
                    covers them.
                  </div>
                  {isCustom && (
                    <div className="jd">
                      <textarea
                        rows={6}
                        placeholder="Paste the job description (at least 25 words)…"
                        value={jd}
                        onChange={(e) => {
                          setJd(e.target.value);
                          setJdPreview(null);
                        }}
                      />
                      <div className="row between">
                        <span className="small muted">{jdWords} words</span>
                        <button type="button" className="btn btn-small" onClick={previewJd} disabled={jdWords < 25 || jdBusy}>
                          {jdBusy ? <Spinner label="Reading JD…" /> : "Preview role"}
                        </button>
                      </div>
                      {jdPreview && (
                        <div className="jd-preview">
                          <strong>{jdPreview.title}</strong>
                          <div className="chips">
                            {jdPreview.topics.map((t) => (
                              <Chip key={t.id} tone="blue" title={t.evidence.join(", ")}>
                                {t.name}
                              </Chip>
                            ))}
                          </div>
                          <div className="small muted">
                            Knowledge bases: {jdPreview.knowledge_bases.map((k) => k.title).join(" + ")}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </label>
            </div>
          )}
        </Card>

        <div className="stack">
          <Card
            title="2. Candidate resume"
            actions={
              <div className="segmented">
                <button type="button" className={mode === "file" ? "on" : ""} onClick={() => setMode("file")}>
                  Upload
                </button>
                <button type="button" className={mode === "text" ? "on" : ""} onClick={() => setMode("text")}>
                  Paste text
                </button>
              </div>
            }
          >
            {mode === "file" ? (
              <div
                className={`dropzone ${dragging ? "dragging" : ""} ${file ? "has-file" : ""}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                onClick={() => inputRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
              >
                <input
                  ref={inputRef}
                  type="file"
                  accept=".pdf,.txt,.md"
                  hidden
                  onChange={(e) => e.target.files?.[0] && pickFile(e.target.files[0])}
                />
                {file ? (
                  <>
                    <FileIcon size={30} className="drop-icon" />
                    <strong>{file.name}</strong>
                    <span className="muted small">{(file.size / 1024).toFixed(0)} KB · click to replace</span>
                  </>
                ) : (
                  <>
                    <UploadIcon size={30} className="drop-icon" />
                    <strong>Drop a resume here or click to browse</strong>
                    <span className="muted small">PDF, TXT or MD · max 5 MB</span>
                  </>
                )}
              </div>
            ) : (
              <textarea
                className="resume-text"
                placeholder="Paste the resume text here (at least 80 characters)…"
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={10}
              />
            )}
          </Card>

          <Card title="3. Interview settings">
            <div className="mode-pick" role="radiogroup" aria-label="Interview mode">
              <label className={interviewMode === "practice" ? "on" : ""}>
                <input type="radio" name="mode" checked={interviewMode === "practice"} onChange={() => setInterviewMode("practice")} />
                <strong>Practice</strong>
                <div className="muted small">Score, feedback and sources after every answer.</div>
              </label>
              <label className={interviewMode === "assessment" ? "on" : ""}>
                <input type="radio" name="mode" checked={interviewMode === "assessment"} onChange={() => setInterviewMode("assessment")} />
                <strong>Assessment</strong>
                <div className="muted small">Results stay hidden (server-side) until the final report.</div>
              </label>
            </div>
            <label className="field">
              <span>Candidate name (optional — read from the resume if empty)</span>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Priya Sharma" maxLength={200} />
            </label>
            <label className="field">
              <span>
                Planned questions: <strong>{numQuestions}</strong>{" "}
                <span className="muted small">(+ up to 2 adaptive follow-ups)</span>
              </span>
              <input type="range" min={3} max={10} value={numQuestions} onChange={(e) => setNumQuestions(Number(e.target.value))} />
            </label>
            <button className="btn btn-primary btn-block" disabled={!canSubmit}>
              {submitting ? <Spinner label={PROCESSING_STEPS[step]} /> : "Analyse resume & build interview →"}
            </button>
          </Card>
        </div>
      </form>
    </div>
  );
}
