// lib/api.ts — typed API client
// Browser requests go through Next.js /api/v1 proxy (server adds API key).

const BASE = "/api/v1";

function authHeaders(): Record<string, string> {
  return { "Content-Type": "application/json" };
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { ...authHeaders(), ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const message =
      (err as { error?: { message?: string } }).error?.message ||
      (err as { detail?: string }).detail ||
      `HTTP ${res.status}`;
    throw new Error(message);
  }
  return res.json();
}

export const api = {
  analyzeRepo: (repoUrl: string, branch = "main") =>
    request<AnalyzeResponse>("/analyze", {
      method: "POST",
      body: JSON.stringify({ repo_url: repoUrl, branch }),
    }),

  listRepos: () => request<Repo[]>("/repos"),
  getRepo: (id: string) => request<Repo>(`/repos/${id}`),
  getReport: (id: string) => request<ReportResponse>(`/repos/${id}/report`),
  getRefactors: (id: string) => request<Refactor[]>(`/repos/${id}/refactors`),
  getStats: () => request<Stats>("/stats"),
  getTaskStatus: (taskId: string) => request<TaskStatus>(`/tasks/${taskId}`),
  triggerRefactor: (issueId: string) =>
    request<RefactorQueuedResponse>("/refactor", {
      method: "POST",
      body: JSON.stringify({ issue_id: issueId }),
    }),

  deleteRepo: (id: string) =>
    request<DeleteResponse>(`/repos/${id}`, { method: "DELETE" }),
};

// ── Types ─────────────────────────────────────────────────────────────────────

export interface AnalyzeResponse {
  repo_id: string;
  task_id: string;
  status: string;
  message: string;
}

export interface RefactorQueuedResponse {
  task_id: string;
  message: string;
}

export interface DeleteResponse {
  deleted: string;
}

export interface TaskStatus {
  task_id: string;
  status: string;
  ready: boolean;
  successful: boolean | null;
  result: unknown;
  error: string | null;
  repo_id: string | null;
}

export interface Repo {
  id: string;
  url: string;
  owner: string;
  name: string;
  status: string;
  branch: string;
  created_at: string;
  last_analyzed_at: string | null;
  task_id?: string | null;
  error_message?: string | null;
}

export interface Issue {
  id: string;
  file_path: string;
  function_name: string | null;
  issue_type: string;
  severity: string;
  description: string;
  metric_value: number | null;
  line_start: number | null;
  line_end: number | null;
  original_code?: string | null;
}

export interface Report {
  id: string;
  created_at: string;
  total_files: number;
  total_issues: number;
  avg_complexity: number;
  max_complexity: number;
  security_issues: number;
  lint_errors: number;
}

export interface ReportResponse {
  report: Report;
  issues: Issue[];
}

export interface Refactor {
  id: string;
  issue_id: string;
  status: string;
  complexity_before: number | null;
  complexity_after: number | null;
  lines_before: number | null;
  lines_after: number | null;
  validation_passed: boolean | null;
  pr_url: string | null;
  pr_number: number | null;
  tokens_used: number;
  created_at: string;
  explanation?: string | null;
  validation_notes?: string | null;
  refactored_code?: string | null;
  original_code?: string | null;
  function_name?: string | null;
  file_path?: string | null;
  branch_name?: string | null;
}

export interface Stats {
  total_repos: number;
  total_issues: number;
  prs_opened: number;
  validated_refactors: number;
  avg_complexity_before: number;
  avg_complexity_after: number;
  complexity_reduction_pct: number;
}
