import {
  Clock, Loader2, Search, Zap, CheckCircle, XCircle,
} from "lucide-react";
import { C, SPIN_STYLE, PULSE_STYLE } from "@/lib/theme";
import { ago } from "@/lib/utils";
import type { Repo } from "@/lib/api";

const STATUS_ICON: Record<string, React.ReactNode> = {
  pending: <Clock size={14} color={C.yellow} />,
  cloning: <Loader2 size={14} color={C.accent} style={SPIN_STYLE} />,
  analyzing: <Search size={14} color={C.accent} style={PULSE_STYLE} />,
  refactoring: <Zap size={14} color="#a855f7" />,
  validating: <Loader2 size={14} color={C.accent} style={SPIN_STYLE} />,
  done: <CheckCircle size={14} color={C.green} />,
  failed: <XCircle size={14} color={C.red} />,
};

export function RepoSidebar({
  repos,
  selectedId,
  loading,
  onSelect,
  onDelete,
}: {
  repos: Repo[];
  selectedId: string | null;
  loading: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <aside
      style={{
        background: C.panel,
        border: `1px solid ${C.border}`,
        borderRadius: 12,
        overflow: "hidden",
        height: "100%",
      }}
    >
      <div
        style={{
          padding: "14px 16px",
          borderBottom: `1px solid ${C.border}`,
          fontSize: 12,
          fontWeight: 600,
          color: C.subtext,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
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
            <br />
            Paste a GitHub URL above
          </div>
        ) : (
          repos.map((repo) => (
            <div
              key={repo.id}
              role="button"
              tabIndex={0}
              onClick={() => onSelect(repo.id)}
              onKeyDown={(e) => e.key === "Enter" && onSelect(repo.id)}
              style={{
                padding: "12px 16px",
                cursor: "pointer",
                borderBottom: `1px solid ${C.border}`,
                background: selectedId === repo.id ? C.accent + "15" : "transparent",
                borderLeft:
                  selectedId === repo.id ? `3px solid ${C.accent}` : "3px solid transparent",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 4,
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 13, color: C.text }}>{repo.name}</div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  {STATUS_ICON[repo.status] || <Clock size={14} />}
                  <button
                    type="button"
                    aria-label={`Delete ${repo.name}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(repo.id);
                    }}
                    style={{
                      background: "transparent",
                      border: "none",
                      color: C.muted,
                      cursor: "pointer",
                      padding: 2,
                      display: "flex",
                    }}
                  >
                    <XCircle size={13} />
                  </button>
                </div>
              </div>
              <div style={{ fontSize: 11, color: C.muted }}>
                {repo.owner} · {repo.branch}
              </div>
              <div style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>{ago(repo.created_at)}</div>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
