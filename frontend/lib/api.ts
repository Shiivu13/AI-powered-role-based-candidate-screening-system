import axios from 'axios';
import { SessionCreateResponse, NextQuestionResponse, SessionSummary, SessionDetails } from './types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 60000,
});

export async function createSession(
  resume: File,
  role: string,
  candidateName: string
): Promise<SessionCreateResponse> {
  const formData = new FormData();
  formData.append('resume', resume);
  formData.append('role', role);
  formData.append('candidate_name', candidateName);

  const res = await api.post<SessionCreateResponse>('/api/sessions', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function submitAnswer(
  sessionId: string,
  answer: string
): Promise<NextQuestionResponse> {
  const res = await api.post<NextQuestionResponse>(`/api/interview/${sessionId}/answer`, { answer });
  return res.data;
}

export async function getSessionSummary(sessionId: string): Promise<SessionSummary> {
  const res = await api.get<SessionSummary>(`/api/interview/${sessionId}/summary`);
  return res.data;
}

export async function getSession(sessionId: string): Promise<SessionDetails> {
  const res = await api.get<SessionDetails>(`/api/sessions/${sessionId}`);
  return res.data;
}

export async function forceComplete(sessionId: string): Promise<void> {
  await api.post(`/api/interview/${sessionId}/complete`);
}
