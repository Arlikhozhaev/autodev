"use client";

import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, Legend,
} from "recharts";
import {
  GitBranch, GitPullRequest, Search, AlertTriangle,
  CheckCircle, XCircle, Clock, Code, Zap,
  TrendingDown, ExternalLink, Loader2, RefreshCw, Plus,
} from "lucide-react";
import { api, type Repo, type Stats, type ReportResponse, type Refactor, type Issue } from "../lib/api";

// ── Colour palette ───────────────────────────────────────────────────────────
const C = {
  bg:       "#0a0e1a",
  panel:    "#0f1525",
  border:   "#1e2a45",
  accent:   "#4f8ef7",
  green:    "#22c55e",
  yellow:   "#f59e0b",
  red:      "#ef4444",
  muted:    "#64748b",
  text:     "#e2e8f0",
  subtext:  "#94a3b8",
};

const SEVERITY_COLOR: Record<string, string> = {
  critical: C.red,
  high:     "#f97316",
  medium:   C.yellow,
  low:      C.green,
};

const SPIN_STYLE = { animation: "spin 1s linear infinite" } as const;
const PULSE_STYLE = { animation: "pulse 2s ease-in-out infinite" } as const;

const STATUS_ICON: Record<string, JSX.Element> = {
  pending:      <Clock    size={14} color={C.yellow} />,
  cloning:      <Loader2  size={14} color={C.accent} style={SPIN_STYLE} />,
  analyzing:    <Search   size={14} color={C.accent} style={PULSE_STYLE} />,
  refactoring:  <Zap      size={14} color="#a855f7" />,
  done:         <CheckCircle size={14} color={C.green} />,
  failed:       <XCircle  size={14} color={C.red} />,
};

// ── Utility ───────────────────────────────────────────────────────────────────
const errorMessage = (e: unknown): string =>
  e instanceof Error ? e.message : "An unexpected error occurred";

const ago = (d: string) => {
  // Append Z if no timezone info — DB stores UTC without Z
  const normalized = d.endsWith("Z") || d.includes("+") ? d : d + "Z";
  const secs = Math.floor((Date.now() - new Date(normalized).getTime()) / 1000);
  if (secs < 0) return "just now";
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
};

// ── Components ────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, icon, color = C.accent }: {
  label: string; value: string | number; sub?: string;
  icon: JSX.Element; color?: string;
}) {
  return (
    <div style={{
      background: C.panel, border: `1px solid ${C.border}`,
      borderRadius: 12, padding: "20px 24px",
      display: "flex", gap: 16, alignItems: "center",
    }}>
      <div style={{
        width: 48, height: 48, borderRadius: 10,
        background: color + "22", display: "flex",
        alignItems: "center", justifyContent: "center",
      }}>
        {icon}
      </div>
      <div>
        <div style={{ fontSize: 26, fontWeight: 700, color: C.text, fontFamily: "monospace" }}>
          {value}
        </div>
        <div style={{ fontSize: 12, color: C.subtext }}>{label}</div>
        {sub && <div style={{ fontSize: 11, color: color, marginTop: 2 }}>{sub}</div>}
      </div>
    </div>
  );
}

function Badge({ text, color }: { text: string; color: string }) {
  return (
    <span style={{
      background: color + "22", color, border: `1px solid ${color}44`,
      borderRadius: 6, padding: "2px 8px", fontSize: 11, fontWeight: 600,
      textTransform: "uppercase", letterSpacing: "0.05em",
    }}>
      {text}
    </span>
  );
}

function IssueRow({ issue, onRefactor }: { issue: Issue; onRefactor: (id: string) => Promise<void> }) {
  const [loading, setLoading] = useState(false);
  const [done, setDone]       = useState(false);
  const color = SEVERITY_COLOR[issue.severity] || C.muted;

  const handleRefactor = async () => {
    setLoading(true);
    try {
      await onRefactor(issue.id);
      setDone(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: "grid", gridTemplateColumns: "1fr 2fr 100px 90px 80px",
      gap: 12, padding: "12px 16px", alignItems: "center",
      borderBottom: `1px solid ${C.border}`,
    }}>
      <div>
        <div style={{ fontSize: 12, color: C.text, fontFamily: "monospace" }}>
          {issue.function_name || "—"}
        </div>
        <div style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>
          {issue.file_path.split("/").slice(-2).join("/")}
          {issue.line_start ? `:${issue.line_start}` : ""}
        </div>
      </div>
      <div style={{ fontSize: 12, color: C.subtext }}>{issue.description}</div>
      <Badge text={issue.issue_type.replace("_", " ")} color={C.accent} />
      <Badge text={issue.severity} color={color} />
      <button
        onClick={handleRefactor}
        disabled={loading || done}
        style={{
          background: done ? C.green + "22" : C.accent + "22",
          border: `1px solid ${done ? C.green : C.accent}44`,
          color: done ? C.green : C.accent,
          borderRadius: 6, padding: "4px 10px",
          fontSize: 11, cursor: loading || done ? "not-allowed" : "pointer",
          display: "flex", alignItems: "center", gap: 4, fontWeight: 600,
          transition: "all 0.2s",
        }}
      >
        {loading ? <Loader2 size={12} style={{animation: "spin 1s linear infinite"}} /> 
         : done   ? <CheckCircle size={12} /> 
                  : <Zap size={12} />}
        {done ? "Queued" : "Fix"}
      </button>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [repoUrl, setRepoUrl]         = useState("");
  const [repos, setRepos]             = useState<Repo[]>([]);
  const [stats, setStats]             = useState<Stats | null>(null);
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null);
  const [report, setReport]           = useState<ReportResponse | null>(null);
  const [refactors, setRefactors]     = useState<Refactor[]>([]);
  const [loading, setLoading]         = useState(false);
  const [submitting, setSubmitting]   = useState(false);
  const [error, setError]             = useState<string | null>(null);
  const [tab, setTab]                 = useState<"issues" | "refactors" | "charts">("issues");

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [r, s] = await Promise.all([api.listRepos(), api.getStats()]);
      setRepos(r);
      setStats(s);
    } catch (e: unknown) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  // Auto-select newest repo once repos load, but only if nothing selected yet
  useEffect(() => {
    if (!selectedRepo && repos.length > 0) {
      loadReport(repos[0].id);
    }
  }, [repos, selectedRepo]);

  // Auto-refresh every 8s when there are active jobs
  useEffect(() => {
    const active = repos.some(r => ["cloning","analyzing","refactoring"].includes(r.status));
    if (!active) return;
    const t = setInterval(fetchAll, 8000);
    return () => clearInterval(t);
  }, [repos]);

  const [reportLoading, setReportLoading] = useState(false);

  const loadReport = async (repoId: string) => {
    setSelectedRepo(repoId);
    setReportLoading(true);
    setReport(null);
    setRefactors([]);
    try {
      const [rpt, rfcs] = await Promise.all([
        api.getReport(repoId),
        api.getRefactors(repoId),
      ]);
      setReport(rpt);
      setRefactors(rfcs);
      setTab("issues");
    } catch (e: unknown) {
      setReport(null);
      setRefactors([]);
      const msg = errorMessage(e);
      if (!msg.includes("404")) {
        setError(`Failed to load report: ${msg}`);
      }
    } finally {
      setReportLoading(false);
    }
  };

  const handleDeleteRepo = async (repoId: string) => {
    if (!confirm("Delete this repository and all its data?")) return;
    try {
      await api.deleteRepo(repoId);
      if (selectedRepo === repoId) {
        setSelectedRepo(null);
        setReport(null);
        setRefactors([]);
      }
      fetchAll();
    } catch (e: unknown) {
      showToast(errorMessage(e), "error");
    }
  };

  const handleAnalyze = async () => {
    if (!repoUrl.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.analyzeRepo(repoUrl.trim());
      setRepoUrl("");
      setTimeout(fetchAll, 500);
    } catch (e: unknown) {
      setError(errorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  const [toast, setToast] = useState<{msg: string; type: "success"|"error"} | null>(null);

  const showToast = (msg: string, type: "success"|"error" = "success") => {
    setToast({msg, type});
    setTimeout(() => setToast(null), 4000);
  };

  const handleRefactor = async (issueId: string) => {
    try {
      await api.triggerRefactor(issueId);
      showToast("Refactor queued — Celery is processing it now.");
      setTab("refactors");
      // Poll refactors tab until the result appears
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        if (selectedRepo) {
          const rfcs = await api.getRefactors(selectedRepo);
          setRefactors(rfcs);
        }
        if (attempts >= 20) clearInterval(poll); // stop after ~40s
      }, 2000);
    } catch (e: unknown) {
      showToast(errorMessage(e), "error");
    }
  };

  // ── Chart data ─────────────────────────────────────────────────────────────
  const complexityChartData = report?.issues
    .filter(i => i.issue_type === "complexity" && i.metric_value)
    .slice(0, 12)
    .map(i => ({
      name: i.function_name || "fn",
      complexity: i.metric_value,
    })) ?? [];

  const issueTypeData = report
    ? Object.entries(
        report.issues.reduce((acc, i) => {
          acc[i.issue_type] = (acc[i.issue_type] || 0) + 1;
          return acc;
        }, {} as Record<string, number>)
      ).map(([type, count]) => ({ type: type.replace("_", " "), count }))
    : [];

  const refactorChart = refactors
    .filter(r => r.complexity_before && r.complexity_after)
    .slice(0, 10)
    .map((r, i) => ({
      name: `#${i + 1}`,
      before: r.complexity_before,
      after: r.complexity_after,
    }));

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={{
      minHeight: "100vh", background: C.bg, color: C.text,
      fontFamily: "'Inter', system-ui, sans-serif",
    }}>
      {/* Header */}
      <div style={{
        borderBottom: `1px solid ${C.border}`, padding: "16px 32px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: C.panel,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 8,
            background: `linear-gradient(135deg, ${C.accent}, #7c3aed)`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Zap size={20} color="white" />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 18, letterSpacing: "-0.02em" }}>AutoDev</div>
            <div style={{ fontSize: 11, color: C.muted }}>Self-Healing Codebase Agent</div>
          </div>
        </div>
        <button
          onClick={fetchAll}
          style={{
            background: "transparent", border: `1px solid ${C.border}`,
            color: C.subtext, borderRadius: 8, padding: "6px 12px",
            cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 13,
          }}
        >
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      <div style={{ padding: "28px 32px" }}>
        {/* Error banner */}
        {error && (
          <div style={{
            background: C.red + "15", border: `1px solid ${C.red}44`,
            borderRadius: 8, padding: "10px 16px", marginBottom: 20,
            color: C.red, fontSize: 13,
          }}>
            ⚠ {error}
          </div>
        )}

        {/* Toast notification */}
        {toast && (
          <div style={{
            position: "fixed", bottom: 24, right: 24, zIndex: 1000,
            background: toast.type === "success" ? C.green + "22" : C.red + "22",
            border: `1px solid ${toast.type === "success" ? C.green : C.red}66`,
            borderRadius: 10, padding: "12px 20px",
            color: toast.type === "success" ? C.green : C.red,
            fontSize: 13, fontWeight: 500,
            boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
            display: "flex", alignItems: "center", gap: 8,
            animation: "slideIn 0.2s ease",
          }}>
            {toast.type === "success" ? <CheckCircle size={16} /> : <XCircle size={16} />}
            {toast.msg}
          </div>
        )}

        {/* Input */}
        <div style={{
          display: "flex", gap: 10, marginBottom: 28,
          background: C.panel, border: `1px solid ${C.border}`,
          borderRadius: 12, padding: 16,
        }}>
          <input
            value={repoUrl}
            onChange={e => setRepoUrl(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleAnalyze()}
            placeholder="https://github.com/owner/repo"
            style={{
              flex: 1, background: C.bg, border: `1px solid ${C.border}`,
              borderRadius: 8, padding: "10px 14px", color: C.text,
              fontSize: 14, outline: "none", fontFamily: "monospace",
            }}
          />
          <button
            onClick={handleAnalyze}
            disabled={submitting || !repoUrl.trim()}
            style={{
              background: submitting ? C.muted : C.accent,
              border: "none", borderRadius: 8, padding: "10px 20px",
              color: "white", fontWeight: 600, fontSize: 14,
              cursor: submitting ? "not-allowed" : "pointer",
              display: "flex", alignItems: "center", gap: 8,
              transition: "background 0.2s",
            }}
          >
            {submitting ? <Loader2 size={16} style={SPIN_STYLE} /> : <Plus size={16} />}
            Analyze Repo
          </button>
        </div>

        {/* Stats row */}
        {stats && (
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: 12, marginBottom: 28,
          }}>
            <StatCard label="Repositories" value={stats.total_repos} icon={<GitBranch size={22} color={C.accent} />} />
            <StatCard label="Issues Found" value={stats.total_issues} icon={<AlertTriangle size={22} color={C.yellow} />} color={C.yellow} />
            <StatCard label="PRs Opened" value={stats.prs_opened} icon={<GitPullRequest size={22} color={C.green} />} color={C.green} />
            <StatCard label="Avg Complexity" value={stats.avg_complexity_before?.toFixed(1)} sub="before refactor" icon={<Code size={22} color="#f97316" />} color="#f97316" />
            <StatCard
              label="Complexity Reduction"
              value={`${stats.complexity_reduction_pct}%`}
              sub="avg across refactors"
              icon={<TrendingDown size={22} color={C.green} />}
              color={C.green}
            />
          </div>
        )}

        {/* Main layout */}
        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 16 }}>
          {/* Repo list */}
          <div style={{
            background: C.panel, border: `1px solid ${C.border}`,
            borderRadius: 12, overflow: "hidden",
          }}>
            <div style={{
              padding: "14px 16px", borderBottom: `1px solid ${C.border}`,
              fontSize: 12, fontWeight: 600, color: C.subtext,
              textTransform: "uppercase", letterSpacing: "0.08em",
            }}>
              Repositories ({repos.length})
            </div>
            <div style={{ maxHeight: 520, overflowY: "auto" }}>
              {loading && repos.length === 0 ? (
                <div style={{ padding: 20, color: C.muted, fontSize: 13, textAlign: "center" }}>
                  <Loader2 size={20} style={{ ...SPIN_STYLE, marginBottom: 8 }} />
                  <div>Loading...</div>
                </div>
              ) : repos.length === 0 ? (
                <div style={{ padding: 24, color: C.muted, fontSize: 13, textAlign: "center" }}>
                  No repositories yet.
                  <br />Paste a GitHub URL above ↑
                </div>
              ) : (
                repos.map(repo => (
                  <div
                    key={repo.id}
                    onClick={() => loadReport(repo.id)}
                    style={{
                      padding: "12px 16px", cursor: "pointer",
                      borderBottom: `1px solid ${C.border}`,
                      background: selectedRepo === repo.id ? C.accent + "15" : "transparent",
                      borderLeft: selectedRepo === repo.id ? `3px solid ${C.accent}` : "3px solid transparent",
                      transition: "background 0.15s",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                      <div style={{ fontWeight: 600, fontSize: 13, color: C.text }}>
                        {repo.name}
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        {STATUS_ICON[repo.status] || <Clock size={14} />}
                        <button
                          onClick={e => { e.stopPropagation(); handleDeleteRepo(repo.id); }}
                          style={{
                            background: "transparent", border: "none",
                            color: C.muted, cursor: "pointer", padding: 2,
                            borderRadius: 4, display: "flex", alignItems: "center",
                            transition: "color 0.15s",
                          }}
                          onMouseEnter={e => (e.currentTarget.style.color = C.red)}
                          onMouseLeave={e => (e.currentTarget.style.color = C.muted)}
                          title="Delete repo"
                        >
                          <XCircle size={13} />
                        </button>
                      </div>
                    </div>
                    <div style={{ fontSize: 11, color: C.muted }}>
                      {repo.owner} · {repo.branch}
                    </div>
                    <div style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>
                      {ago(repo.created_at)}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Right panel */}
          <div style={{
            background: C.panel, border: `1px solid ${C.border}`,
            borderRadius: 12, overflow: "hidden",
          }}>
            {!selectedRepo ? (
              <div style={{
                display: "flex", flexDirection: "column",
                alignItems: "center", justifyContent: "center",
                height: 400, color: C.muted, gap: 12,
              }}>
                <Code size={40} color={C.border} />
                <div style={{ fontSize: 14 }}>Select a repository to view analysis</div>
              </div>
            ) : reportLoading ? (
              <div style={{
                display: "flex", flexDirection: "column",
                alignItems: "center", justifyContent: "center",
                height: 400, color: C.muted, gap: 12,
              }}>
                <Loader2 size={32} color={C.accent} style={{ animation: "spin 1s linear infinite" }} />
                <div style={{ fontSize: 14 }}>Loading analysis...</div>
              </div>
            ) : !report && selectedRepo ? (
              <div style={{
                display: "flex", flexDirection: "column",
                alignItems: "center", justifyContent: "center",
                height: 400, color: C.muted, gap: 12,
              }}>
                <Clock size={40} color={C.border} />
                <div style={{ fontSize: 14 }}>Analysis in progress — refresh in a moment</div>
                <button
                  onClick={() => loadReport(selectedRepo)}
                  style={{
                    background: C.accent + "22", border: `1px solid ${C.accent}44`,
                    color: C.accent, borderRadius: 8, padding: "6px 16px",
                    cursor: "pointer", fontSize: 13,
                  }}
                >
                  Check again
                </button>
              </div>
            ) : (
              <>
                {/* Tabs */}
                <div style={{
                  display: "flex", borderBottom: `1px solid ${C.border}`,
                  padding: "0 16px",
                }}>
                  {(["issues", "refactors", "charts"] as const).map(t => (
                    <button
                      key={t}
                      onClick={() => setTab(t)}
                      style={{
                        background: "transparent", border: "none",
                        borderBottom: tab === t ? `2px solid ${C.accent}` : "2px solid transparent",
                        color: tab === t ? C.accent : C.muted,
                        padding: "12px 16px", cursor: "pointer",
                        fontSize: 13, fontWeight: 600, textTransform: "capitalize",
                        transition: "color 0.15s",
                      }}
                    >
                      {t === "issues" && `Issues ${report ? `(${report.issues.length})` : ""}`}
                      {t === "refactors" && `Refactors ${refactors.length > 0 ? `(${refactors.length})` : ""}`}
                      {t === "charts" && "Charts"}
                    </button>
                  ))}
                </div>

                {/* Report summary strip */}
                {report && tab === "issues" && (
                  <div style={{
                    display: "flex", gap: 24, padding: "12px 16px",
                    borderBottom: `1px solid ${C.border}`,
                    background: C.bg + "88",
                  }}>
                    {[
                      { label: "Files", value: report.report.total_files },
                      { label: "Issues", value: report.report.total_issues },
                      { label: "Max Complexity", value: report.report.max_complexity },
                      { label: "Security", value: report.report.security_issues },
                      { label: "Lint", value: report.report.lint_errors },
                    ].map(s => (
                      <div key={s.label}>
                        <div style={{ fontSize: 18, fontWeight: 700, color: C.text, fontFamily: "monospace" }}>{s.value}</div>
                        <div style={{ fontSize: 10, color: C.muted }}>{s.label}</div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Issues tab */}
                {tab === "issues" && report && (
                  <div style={{ maxHeight: 460, overflowY: "auto" }}>
                    {/* Table header */}
                    <div style={{
                      display: "grid", gridTemplateColumns: "1fr 2fr 100px 90px 80px",
                      gap: 12, padding: "8px 16px",
                      borderBottom: `1px solid ${C.border}`,
                      fontSize: 10, fontWeight: 700, color: C.muted,
                      textTransform: "uppercase", letterSpacing: "0.08em",
                    }}>
                      <div>Function</div><div>Description</div>
                      <div>Type</div><div>Severity</div><div>Action</div>
                    </div>
                    {report.issues.map(issue => (
                      <IssueRow key={issue.id} issue={issue} onRefactor={handleRefactor} />
                    ))}
                    {report.issues.length === 0 && (
                      <div style={{ padding: 32, textAlign: "center", color: C.muted, fontSize: 13 }}>
                        <CheckCircle size={32} color={C.green} style={{ marginBottom: 8 }} />
                        <div>No issues found — clean codebase!</div>
                      </div>
                    )}
                  </div>
                )}

                {/* Refactors tab */}
                {tab === "refactors" && (
                  <div style={{ maxHeight: 460, overflowY: "auto" }}>
                    {refactors.length === 0 ? (
                      <div style={{ padding: 32, textAlign: "center", color: C.muted, fontSize: 13 }}>
                        No refactors generated yet.
                      </div>
                    ) : (
                      refactors.map(r => (
                        <div key={r.id} style={{
                          padding: "14px 16px",
                          borderBottom: `1px solid ${C.border}`,
                          display: "grid", gridTemplateColumns: "1fr 1fr 1fr 100px 80px",
                          gap: 12, alignItems: "center",
                        }}>
                          <div>
                            <Badge
                              text={r.status}
                              color={
                                r.status === "pr_opened" ? C.green :
                                r.status === "validated" ? C.accent :
                                r.status === "failed" ? C.red : C.yellow
                              }
                            />
                          </div>
                          <div style={{ fontSize: 12, color: C.subtext, fontFamily: "monospace" }}>
                            {r.complexity_before != null ? `CC ${r.complexity_before} → ${r.complexity_after}` : "—"}
                          </div>
                          <div style={{ fontSize: 12, color: C.subtext }}>
                            {r.lines_before != null ? `${r.lines_before} → ${r.lines_after} lines` : "—"}
                          </div>
                          <div style={{ fontSize: 11, color: C.muted }}>
                            {r.tokens_used > 0 ? `${r.tokens_used} tokens` : "—"}
                          </div>
                          {r.pr_url ? (
                            <a href={r.pr_url} target="_blank" rel="noopener" style={{
                              color: C.accent, fontSize: 11, display: "flex",
                              alignItems: "center", gap: 4, textDecoration: "none",
                            }}>
                              PR #{r.pr_number} <ExternalLink size={11} />
                            </a>
                          ) : <div />}
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* Charts tab */}
                {tab === "charts" && report && (
                  <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 24 }}>
                    {complexityChartData.length > 0 && (
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: C.subtext, marginBottom: 12 }}>
                          FUNCTION COMPLEXITY SCORES
                        </div>
                        <ResponsiveContainer width="100%" height={180}>
                          <BarChart data={complexityChartData}>
                            <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                            <XAxis dataKey="name" tick={{ fill: C.muted, fontSize: 10 }} />
                            <YAxis tick={{ fill: C.muted, fontSize: 10 }} />
                            <Tooltip
                              contentStyle={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 8 }}
                              labelStyle={{ color: C.text }}
                            />
                            <Bar dataKey="complexity" fill={C.accent} radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                    {issueTypeData.length > 0 && (
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: C.subtext, marginBottom: 12 }}>
                          ISSUES BY TYPE
                        </div>
                        <ResponsiveContainer width="100%" height={180}>
                          <BarChart data={issueTypeData} layout="vertical">
                            <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                            <XAxis type="number" tick={{ fill: C.muted, fontSize: 10 }} />
                            <YAxis dataKey="type" type="category" tick={{ fill: C.muted, fontSize: 10 }} width={100} />
                            <Tooltip
                              contentStyle={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 8 }}
                            />
                            <Bar dataKey="count" fill="#a855f7" radius={[0, 4, 4, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                    {refactorChart.length > 0 && (
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: C.subtext, marginBottom: 12 }}>
                          COMPLEXITY BEFORE vs AFTER REFACTOR
                        </div>
                        <ResponsiveContainer width="100%" height={180}>
                          <LineChart data={refactorChart}>
                            <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                            <XAxis dataKey="name" tick={{ fill: C.muted, fontSize: 10 }} />
                            <YAxis tick={{ fill: C.muted, fontSize: 10 }} />
                            <Tooltip
                              contentStyle={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 8 }}
                            />
                            <Legend wrapperStyle={{ color: C.muted, fontSize: 11 }} />
                            <Line type="monotone" dataKey="before" stroke={C.red} strokeWidth={2} dot={{ r: 3 }} />
                            <Line type="monotone" dataKey="after" stroke={C.green} strokeWidth={2} dot={{ r: 3 }} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
