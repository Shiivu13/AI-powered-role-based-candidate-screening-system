import { useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Role } from "../api/types";
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
  const [mode, setMode] = useState<"file" | "text">("file");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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
  const canSubmit = !!selectedRole?.knowledge_base_ready && hasResume && !submitting;

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
          Upload a resume and pick a role. Every question is generated live from the role's reference textbooks and
          tailored to the candidate's background, with page-level citations for each one.
        </p>
      </div>

      {error && <ErrorBanner message={error} onClose={() => setError(null)} />}

      <form onSubmit={onSubmit} className="setup-grid">
        <Card title="1. Choose the target role">
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
                    onChange={() => setRoleId(r.id)}
                  />
                  <div>
                    <div className="role-title">{r.title}</div>
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
