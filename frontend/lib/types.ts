export interface SessionCreateResponse {
  session_id: string;
  status: string;
  role: string;
  candidate_name: string | null;
  first_question: Question;
  total_questions: number;
}

export interface RetrievalSource {
  book: string;
  snippet: string;
  similarity: number | null;
}

export interface RetrievalMeta {
  query?: string | null;
  topic?: string | null;
  difficulty?: string | null;
  reasoning?: string | null;
  sources: RetrievalSource[];
}

export interface AnswerEvaluation {
  score: number | null;
  feedback: string | null;
  detail?: Record<string, number> | null;
}

export interface Question {
  id: string;
  question_number: number;
  question_text: string;
  question_type: string | null;
  difficulty?: string | null;
  topic?: string | null;
  retrieval_meta?: RetrievalMeta | null;
  created_at?: string;
  answer_text?: string | null;
  score?: number | null;
  feedback?: string | null;
  eval_detail?: Record<string, number> | null;
}

export interface NextQuestionResponse {
  question: Question | null;
  is_complete: boolean;
  question_number: number;
  total_questions: number;
  last_answer_evaluation?: AnswerEvaluation | null;
}

export interface TopicMastery {
  topic: string;
  score: number;
  count: number;
}

export interface SessionSummary {
  session_id: string;
  candidate_name: string | null;
  role: string;
  total_questions: number;
  topics_covered: string[];
  overall_assessment: string | null;
  strengths: string[];
  improvements: string[];
  technical_score: number | null;
  recommendation: string | null;
  full_analysis: string | null;
  topic_mastery: TopicMastery[];
  average_score: number | null;
  questions: Question[];
  created_at: string;
}

export interface SessionDetails {
  id: string;
  candidate_name: string | null;
  role: string;
  status: string;
  resume_skills: Record<string, unknown> | null;
  current_question_index: number;
  created_at: string;
  completed_at: string | null;
  questions: Question[];
}

export type Role = 'ai_ml' | 'data_science' | 'backend';

export const ROLE_LABELS: Record<string, string> = {
  ai_ml: 'AI / ML Engineer',
  data_science: 'Data Scientist',
  backend: 'Backend Engineer',
};

export const ROLE_DESCRIPTIONS: Record<string, string> = {
  ai_ml: 'Machine learning, deep learning, model training & deployment',
  data_science: 'Data analysis, feature engineering, applied ML',
  backend: 'APIs, databases, system design, distributed systems',
};
