import { Loader2, Plus } from "lucide-react";
import { C, SPIN_STYLE } from "@/lib/theme";

export function AnalyzeBar({
  repoUrl,
  branch,
  submitting,
  onUrlChange,
  onBranchChange,
  onSubmit,
}: {
  repoUrl: string;
  branch: string;
  submitting: boolean;
  onUrlChange: (v: string) => void;
  onBranchChange: (v: string) => void;
  onSubmit: () => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 10,
        marginBottom: 28,
        background: C.panel,
        border: `1px solid ${C.border}`,
        borderRadius: 12,
        padding: 16,
      }}
    >
      <input
        value={repoUrl}
        onChange={(e) => onUrlChange(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && onSubmit()}
        placeholder="https://github.com/owner/repo"
        aria-label="GitHub repository URL"
        style={{
          flex: "1 1 240px",
          background: C.bg,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: "10px 14px",
          color: C.text,
          fontSize: 14,
          outline: "none",
          fontFamily: "monospace",
        }}
      />
      <input
        value={branch}
        onChange={(e) => onBranchChange(e.target.value)}
        placeholder="main"
        aria-label="Branch name"
        style={{
          flex: "0 1 120px",
          background: C.bg,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: "10px 14px",
          color: C.text,
          fontSize: 14,
          outline: "none",
          fontFamily: "monospace",
        }}
      />
      <button
        type="button"
        onClick={onSubmit}
        disabled={submitting || !repoUrl.trim()}
        style={{
          background: submitting ? C.muted : C.accent,
          border: "none",
          borderRadius: 8,
          padding: "10px 20px",
          color: "white",
          fontWeight: 600,
          fontSize: 14,
          cursor: submitting ? "not-allowed" : "pointer",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        {submitting ? <Loader2 size={16} style={SPIN_STYLE} /> : <Plus size={16} />}
        Analyze Repo
      </button>
    </div>
  );
}
