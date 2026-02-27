// lib/api.ts — typed API client

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  analyzeRepo: (repoUrl: string, branch = "main") =>
    request("/analyze", {
      method: "POST",
      body: JSON.stringify({ repo_url: repoUrl, branch }),
    }),

  listRepos: () => request<Repo[]>("/repos"),
  getRepo: (id: string) => request<Repo>(`/repos/${id}`),
  getReport: (id: string) => request<ReportResponse>(`/repos/${id}/report`),
  getRefactors: (id: string) => request<Refactor[]>(`/repos/${id}/refactors`),
  getStats: () => request<Stats>("/stats"),
  triggerRefactor: (issueId: string) =>
    request("/refactor", { method: "POST", body: JSON.stringify({ issue_id: issueId }) }),
};

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Repo {
  id: string;
  url: string;
  owner: string;
  name: string;
  status: string;
  branch: string;
  created_at: string;
  last_analyzed_at: string | null;
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
