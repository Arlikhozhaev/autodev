"use client";

import { useState } from "react";
import { CheckCircle, Loader2, Zap } from "lucide-react";
import { Badge } from "@/components/ui/Primitives";
import { C, SEVERITY_COLOR } from "@/lib/theme";
import { shortPath } from "@/lib/utils";
import type { Issue } from "@/lib/api";

function IssueRow({
  issue,
  onRefactor,
}: {
  issue: Issue;
  onRefactor: (id: string) => Promise<void>;
}) {
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
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
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(120px,1fr) minmax(140px,2fr) 90px 80px 72px",
        gap: 10,
        padding: "12px 16px",
        alignItems: "center",
        borderBottom: `1px solid ${C.border}`,
      }}
    >
      <div>
        <div style={{ fontSize: 12, color: C.text, fontFamily: "monospace" }}>
          {issue.function_name || "—"}
        </div>
        <div style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>
          {shortPath(issue.file_path)}
          {issue.line_start ? `:${issue.line_start}` : ""}
        </div>
      </div>
      <div style={{ fontSize: 12, color: C.subtext }}>{issue.description}</div>
      <Badge text={issue.issue_type.replace("_", " ")} color={C.accent} />
      <Badge text={issue.severity} color={color} />
      <button
        type="button"
        onClick={handleRefactor}
        disabled={loading || done}
        style={{
          background: done ? C.green + "22" : C.accent + "22",
          border: `1px solid ${done ? C.green : C.accent}44`,
          color: done ? C.green : C.accent,
          borderRadius: 6,
          padding: "4px 8px",
          fontSize: 11,
          cursor: loading || done ? "not-allowed" : "pointer",
          display: "flex",
          alignItems: "center",
          gap: 4,
          fontWeight: 600,
        }}
      >
        {loading ? (
          <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} />
        ) : done ? (
          <CheckCircle size={12} />
        ) : (
          <Zap size={12} />
        )}
        {done ? "Queued" : "Fix"}
      </button>
    </div>
  );
}

export function IssueTable({
  issues,
  onRefactor,
}: {
  issues: Issue[];
  onRefactor: (id: string) => Promise<void>;
}) {
  if (issues.length === 0) {
    return (
      <div style={{ padding: 32, textAlign: "center", color: C.muted, fontSize: 13 }}>
        <CheckCircle size={32} color={C.green} style={{ marginBottom: 8 }} />
        <div>No issues found — clean codebase!</div>
      </div>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(120px,1fr) minmax(140px,2fr) 90px 80px 72px",
          gap: 10,
          padding: "8px 16px",
          borderBottom: `1px solid ${C.border}`,
          fontSize: 10,
          fontWeight: 700,
          color: C.muted,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          minWidth: 520,
        }}
      >
        <div>Function</div>
        <div>Description</div>
        <div>Type</div>
        <div>Severity</div>
        <div>Action</div>
      </div>
      {issues.map((issue) => (
        <IssueRow key={issue.id} issue={issue} onRefactor={onRefactor} />
      ))}
    </div>
  );
}
