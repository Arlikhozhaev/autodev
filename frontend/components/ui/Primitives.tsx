import { C } from "@/lib/theme";

export function Badge({ text, color }: { text: string; color: string }) {
  return (
    <span
      style={{
        background: color + "22",
        color,
        border: `1px solid ${color}44`,
        borderRadius: 6,
        padding: "2px 8px",
        fontSize: 11,
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        whiteSpace: "nowrap",
      }}
    >
      {text}
    </span>
  );
}

export function StatCard({
  label,
  value,
  sub,
  icon,
  color = C.accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
  color?: string;
}) {
  return (
    <div
      style={{
        background: C.panel,
        border: `1px solid ${C.border}`,
        borderRadius: 12,
        padding: "20px 24px",
        display: "flex",
        gap: 16,
        alignItems: "center",
      }}
    >
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: 10,
          background: color + "22",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {icon}
      </div>
      <div>
        <div style={{ fontSize: 26, fontWeight: 700, color: C.text, fontFamily: "monospace" }}>
          {value}
        </div>
        <div style={{ fontSize: 12, color: C.subtext }}>{label}</div>
        {sub && <div style={{ fontSize: 11, color, marginTop: 2 }}>{sub}</div>}
      </div>
    </div>
  );
}

export function Toast({
  message,
  type,
}: {
  message: string;
  type: "success" | "error";
}) {
  const color = type === "success" ? C.green : C.red;
  return (
    <div
      role="status"
      style={{
        position: "fixed",
        bottom: 24,
        right: 24,
        zIndex: 1000,
        background: color + "22",
        border: `1px solid ${color}66`,
        borderRadius: 10,
        padding: "12px 20px",
        color,
        fontSize: 13,
        fontWeight: 500,
        boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
        animation: "slideIn 0.2s ease",
      }}
    >
      {message}
    </div>
  );
}

export function ConfirmModal({
  title,
  message,
  confirmLabel = "Confirm",
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1100,
        background: "rgba(0,0,0,0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
      onClick={onCancel}
    >
      <div
        style={{
          background: C.panel,
          border: `1px solid ${C.border}`,
          borderRadius: 12,
          padding: 24,
          maxWidth: 400,
          width: "100%",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 style={{ margin: "0 0 8px", fontSize: 16, color: C.text }}>{title}</h2>
        <p style={{ margin: "0 0 20px", fontSize: 14, color: C.subtext, lineHeight: 1.5 }}>
          {message}
        </p>
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button
            type="button"
            onClick={onCancel}
            style={{
              background: "transparent",
              border: `1px solid ${C.border}`,
              color: C.subtext,
              borderRadius: 8,
              padding: "8px 16px",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            style={{
              background: C.red,
              border: "none",
              color: "white",
              borderRadius: 8,
              padding: "8px 16px",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
