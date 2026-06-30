export const C = {
  bg: "#0a0e1a",
  panel: "#0f1525",
  border: "#1e2a45",
  accent: "#4f8ef7",
  green: "#22c55e",
  yellow: "#f59e0b",
  red: "#ef4444",
  muted: "#64748b",
  text: "#e2e8f0",
  subtext: "#94a3b8",
} as const;

export const SEVERITY_COLOR: Record<string, string> = {
  critical: C.red,
  high: "#f97316",
  medium: C.yellow,
  low: C.green,
};

export const SPIN_STYLE = { animation: "spin 1s linear infinite" } as const;
export const PULSE_STYLE = { animation: "pulse 2s ease-in-out infinite" } as const;

export type TabId = "issues" | "refactors" | "charts";
