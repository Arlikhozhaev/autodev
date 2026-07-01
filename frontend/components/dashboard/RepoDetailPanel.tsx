"use client";

import { Clock, Code, Loader2 } from "lucide-react";
import { PipelineStepper } from "@/components/dashboard/PipelineStepper";
import { IssueTable } from "@/components/dashboard/IssueTable";
import { RefactorList } from "@/components/dashboard/RefactorList";
import { ChartsPanel } from "@/components/dashboard/ChartsPanel";
import { C, SPIN_STYLE, type TabId } from "@/lib/theme";
import type { ReportResponse, Refactor, Repo, TaskStatus } from "@/lib/api";

export function RepoDetailPanel({
  repo,
  report,
  refactors,
  loading,
  tab,
  taskStatus,
  onTabChange,
  onRetry,
  onRefactor,
}: {
  repo: Repo | null;
  report: ReportResponse | null;
  refactors: Refactor[];
  loading: boolean;
  tab: TabId;
  taskStatus: TaskStatus | null;
  onTabChange: (tab: TabId) => void;
  onRetry: () => void;
  onRefactor: (issueId: string) => Promise<void>;
}) {
  if (!repo) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: 400,
          color: C.muted,
          gap: 12,
        }}
      >
        <Code size={40} color={C.border} />
        <div style={{ fontSize: 14 }}>Select a repository to view analysis</div>
      </div>
    );
  }

  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: 400,
          color: C.muted,
          gap: 12,
        }}
      >
        <Loader2 size={32} color={C.accent} style={SPIN_STYLE} />
        <div style={{ fontSize: 14 }}>Loading analysis...</div>
      </div>
    );
  }

  if (!report) {
    return (
      <div>
        <PipelineStepper status={repo.status} />
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: 340,
            color: C.muted,
            gap: 12,
          }}
        >
          <Clock size={40} color={C.border} />
          <div style={{ fontSize: 14 }}>Analysis in progress — refresh in a moment</div>
          <button
            type="button"
            onClick={onRetry}
            style={{
              background: C.accent + "22",
              border: `1px solid ${C.accent}44`,
              color: C.accent,
              borderRadius: 8,
              padding: "6px 16px",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            Check again
          </button>
        </div>
      </div>
    );
  }

  const tabs: { id: TabId; label: string }[] = [
    { id: "issues", label: `Issues (${report.issues.length})` },
    { id: "refactors", label: `Refactors (${refactors.length})` },
    { id: "charts", label: "Charts" },
  ];

  return (
    <div>
      <PipelineStepper status={repo.status} />
      {taskStatus && !taskStatus.ready && (
        <div
          style={{
            padding: "8px 16px",
            fontSize: 12,
            color: C.subtext,
            borderBottom: `1px solid ${C.border}`,
            fontFamily: "monospace",
          }}
        >
          Celery task <span style={{ color: C.accent }}>{taskStatus.task_id.slice(0, 8)}…</span>
          {" · "}
          <span style={{ color: C.yellow }}>{taskStatus.status}</span>
        </div>
      )}
      <div style={{ display: "flex", borderBottom: `1px solid ${C.border}`, padding: "0 16px" }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => onTabChange(t.id)}
            style={{
              background: "transparent",
              border: "none",
              borderBottom: tab === t.id ? `2px solid ${C.accent}` : "2px solid transparent",
              color: tab === t.id ? C.accent : C.muted,
              padding: "12px 16px",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "issues" && (
        <>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 24,
              padding: "12px 16px",
              borderBottom: `1px solid ${C.border}`,
              background: C.bg + "88",
            }}
          >
            {[
              { label: "Files", value: report.report.total_files },
              { label: "Issues", value: report.report.total_issues },
              { label: "Max Complexity", value: report.report.max_complexity },
              { label: "Security", value: report.report.security_issues },
              { label: "Lint", value: report.report.lint_errors },
            ].map((s) => (
              <div key={s.label}>
                <div style={{ fontSize: 18, fontWeight: 700, color: C.text, fontFamily: "monospace" }}>
                  {s.value}
                </div>
                <div style={{ fontSize: 10, color: C.muted }}>{s.label}</div>
              </div>
            ))}
          </div>
          <div style={{ maxHeight: 460, overflowY: "auto" }}>
            <IssueTable issues={report.issues} onRefactor={onRefactor} />
          </div>
        </>
      )}

      {tab === "refactors" && (
        <div style={{ maxHeight: 520, overflowY: "auto" }}>
          <RefactorList refactors={refactors} />
        </div>
      )}

      {tab === "charts" && (
        <ChartsPanel issues={report.issues} refactors={refactors} />
      )}
    </div>
  );
}
