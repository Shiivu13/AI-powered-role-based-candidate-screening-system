// Mirrors backend/app/schemas.py

/** Signed copy of a session's server state, kept by the browser (see backend services/snapshot.py). */
export interface Snapshot {
  session_id: string;
  version: number;
  body: string; // encrypted, opaque to the browser
  summary?: SnapshotSummary | null;
}

export interface SnapshotSummary {
  id: string;
  candidate_name: string;
  role_id: string;
  role_title?: string | null;
  status: "ready" | "in_progress" | "completed";
  mode: "practice" | "assessment";
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  planned: number;
  primary_asked: number;
  asked: number;
  answered: number;
  skipped: number;
  follow_ups: number;
  difficulty_offset: number;
  overall_score: number | null;
}

export type Rubric = { correctness: number; depth: number; application: number; communication: number };

export interface HintResponse {
  question_id: string;
  hint: string;
  penalty: number;
  mode: string;
  snapshot?: Snapshot | null;
}

export interface Book {
  id: string;
  title: string;
  author: string;
  available: boolean;
  chunks: number;
}

export interface Topic {
  id: string;
  name: string;
  description: string;
}

export interface Role {
  id: string;
  title: string;
  description: string;
  books: Book[];
  topics: Topic[];
  knowledge_base_ready: boolean;
  knowledge_base_chunks: number;
}

export interface PlanItem {
  index: number;
  topic_id: string;
  topic_name: string;
  topic_description: string;
  source: "resume" | "core" | "breadth";
  reason: string;
  evidence: string[];
  affinity: number;
  difficulty: number;
  difficulty_label: string;
  question_type: string;
  queries: string[];
  focus_terms: string[];
}

export interface Answer {
  text: string;
  score: number | null;
  verdict: string | null;
  feedback: string | null;
  covered_points: string[];
  missing_points: string[];
  misconceptions: string[];
  evaluation_mode: string | null;
  rubric?: Rubric | null;
  hint_penalty?: number | null;
  hidden?: boolean;
  integrity: Integrity | null;
  response_seconds: number | null;
  answered_at: string;
}

export interface IntegrityFlag {
  code: "pasted_answer" | "copied_from_source" | "implausible_speed" | "left_the_tab" | string;
  detail: string;
}

export interface Integrity {
  level: "none" | "review" | "high";
  flags: IntegrityFlag[];
  signals: {
    paste_ratio: number;
    voice_ratio: number;
    verbatim_source_overlap: number;
    focus_losses: number;
    words_per_minute: number | null;
  };
}

export interface TraceChunk {
  chunk_id: string;
  book_id: string;
  book_title: string;
  section: string;
  page_start: number;
  page_end: number;
  citation: string;
  rrf_score: number;
  dense_score: number | null;
  dense_rank: number | null;
  bm25_rank: number | null;
  matched_queries: number[];
  snippet: string;
  used_by_question?: boolean;
}

export interface QuestionTrace {
  plan_item: PlanItem;
  effective_difficulty: number;
  adaptive_note: string;
  retrieval: {
    queries: string[];
    diagnostics: Record<string, unknown>;
    chunks: TraceChunk[];
  };
  generation: { mode?: string; model?: string; prompt_version?: string; fallback_reason?: string };
}

export interface Question {
  id: string;
  position: number;
  plan_index: number;
  kind: "primary" | "follow_up";
  parent_question_id: string | null;
  topic_id: string;
  topic_name: string;
  question_type: string;
  difficulty: number;
  difficulty_label: string;
  text: string;
  rationale: string;
  status: "asked" | "answered" | "skipped";
  asked_at: string;
  expected_points: string[] | null;
  hint?: string | null;
  answer: Answer | null;
  trace: QuestionTrace | null;
}

export interface Progress {
  planned: number;
  primary_asked: number;
  asked: number;
  answered: number;
  skipped: number;
  follow_ups: number;
  current_difficulty_offset: number;
}

export interface SessionSummary {
  id: string;
  candidate_name: string;
  role_id: string;
  role_title: string;
  status: "ready" | "in_progress" | "completed";
  mode?: "practice" | "assessment";
  custom_role?: boolean;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  progress: Progress;
  overall_score: number | null;
}

export interface Profile {
  name: string | null;
  headline: string | null;
  skills: string[];
  technologies: string[];
  domains: string[];
  years_experience: number | null;
  seniority: string;
  education: string[];
  projects: { name: string; summary: string; technologies: string[] }[];
  strength_signals: string[];
  skill_evidence: Record<string, { category: string; mentions: number }>;
  extraction: { mode: string; model?: string; note?: string };
}

export interface SessionDetail extends SessionSummary {
  resume_filename: string | null;
  profile: Profile;
  plan: PlanItem[];
  questions: Question[];
  current_question_id: string | null;
  report_available: boolean;
  snapshot?: Snapshot | null;
}

export interface NextQuestionResponse {
  done: boolean;
  question: Question | null;
  progress: Progress;
  snapshot?: Snapshot | null;
}

export interface AnswerResponse {
  question: Question;
  progress: Progress;
  next_action: "next_question" | "complete";
  snapshot?: Snapshot | null;
}

export interface Report {
  candidate_name: string;
  role_id: string;
  role_title: string;
  overall_score: number;
  competencies?: Partial<Rubric>;
  recommendation: { code: "strong_yes" | "yes" | "borderline" | "no"; label: string };
  topic_breakdown: {
    topic_id: string;
    topic_name: string;
    source: string;
    score: number;
    questions: number;
    max_difficulty: number;
  }[];
  resume_claims: { topic_name: string; evidence: string[]; score: number; status: string }[];
  gap_probes: { topic_name: string; score: number }[];
  insights: {
    questions_asked: number;
    answered: number;
    skipped: number;
    follow_ups: number;
    avg_response_seconds: number | null;
    avg_answer_words: number;
    difficulty_progression: { position: number; difficulty: number; score: number | null }[];
    score_trend: string;
    hints_used?: number;
    grounding: { books_used: string[]; llm_generated: number };
    integrity?: {
      level: "none" | "review" | "high";
      flagged_answers: { position: number; topic_name: string; flags: IntegrityFlag[] }[];
      note: string;
    };
  };
  narrative: {
    summary: string;
    strengths: string[];
    improvement_areas: string[];
    resume_alignment: string;
    suggested_next_steps: string[];
    mode: string;
  };
}

export interface ReportResponse {
  session_id: string;
  created_at: string;
  report: Report;
  snapshot?: Snapshot | null;
}

export interface Health {
  status: string;
  llm_provider: string;
  llm_model: string;
  embedding_provider: string;
  database: string;
  knowledge_base: Record<string, number>;
}

export type RetrievalMode = "hybrid" | "dense" | "bm25";

export interface SearchResponse {
  role_id: string;
  mode: RetrievalMode;
  queries: string[];
  diagnostics: Record<string, unknown>;
  chunks: TraceChunk[];
}

export type MetricRow = Record<string, number>;

export interface Benchmark {
  generated_at: string;
  roles: Record<string, { queries: number; chunks: number; results: Record<string, MetricRow> }>;
  chunk_size_ablation: { role?: string; results?: Record<string, MetricRow> };
}

export interface RoleFit {
  role_id: string;
  title: string;
  fit: number;
  matched_topics: { topic: string; evidence: string[] }[];
  missing_core_topics: string[];
  recommended?: boolean;
}

export interface ResumeAnalysis {
  profile: { name: string | null; headline: string | null; seniority: string; years_experience: number | null; skills: string[]; technologies: string[]; domains: string[] };
  role_fit: RoleFit[];
}

export interface JobRolePreview {
  role_id: string;
  title: string;
  topics: { id: string; name: string; evidence: string[] }[];
  knowledge_bases: { role_id: string; title: string }[];
  required_skills: string[];
  extraction: string;
}
