import { RefreshCw, Zap, Menu } from "lucide-react";
import { C } from "@/lib/theme";

export function Header({
  onRefresh,
  onMenuClick,
  showMenu,
}: {
  onRefresh: () => void;
  onMenuClick?: () => void;
  showMenu?: boolean;
}) {
  return (
    <header
      style={{
        borderBottom: `1px solid ${C.border}`,
        padding: "16px 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: C.panel,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {showMenu && onMenuClick && (
          <button
            type="button"
            aria-label="Open repositories"
            onClick={onMenuClick}
            style={{
              background: "transparent",
              border: `1px solid ${C.border}`,
              borderRadius: 8,
              padding: 8,
              cursor: "pointer",
              color: C.subtext,
              display: "flex",
            }}
          >
            <Menu size={18} />
          </button>
        )}
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            background: `linear-gradient(135deg, ${C.accent}, #7c3aed)`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Zap size={20} color="white" />
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 18, letterSpacing: "-0.02em" }}>AutoDev</div>
          <div style={{ fontSize: 11, color: C.muted }}>Self-Healing Codebase Agent</div>
        </div>
      </div>
      <button
        type="button"
        onClick={onRefresh}
        style={{
          background: "transparent",
          border: `1px solid ${C.border}`,
          color: C.subtext,
          borderRadius: 8,
          padding: "6px 12px",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 13,
        }}
      >
        <RefreshCw size={13} /> Refresh
      </button>
    </header>
  );
}
