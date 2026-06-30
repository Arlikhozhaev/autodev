import { C } from "@/lib/theme";

const STEPS = [
  { key: "pending", label: "Queued" },
  { key: "cloning", label: "Clone" },
  { key: "analyzing", label: "Analyze" },
  { key: "refactoring", label: "Refactor" },
  { key: "validating", label: "Validate" },
  { key: "done", label: "Complete" },
] as const;

const ORDER = STEPS.map((s) => s.key);

function stepIndex(status: string): number {
  if (status === "failed") return -1;
  const idx = ORDER.indexOf(status as (typeof ORDER)[number]);
  return idx >= 0 ? idx : 0;
}

export function PipelineStepper({ status }: { status: string }) {
  const current = stepIndex(status);
  const failed = status === "failed";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 0,
        padding: "12px 16px",
        borderBottom: `1px solid ${C.border}`,
        background: C.bg + "88",
        overflowX: "auto",
      }}
    >
      {STEPS.map((step, i) => {
        const done = !failed && current > i;
        const active = !failed && current === i;
        const isFailed = failed && i === Math.max(current, 0);

        const dotColor = isFailed ? C.red : done ? C.green : active ? C.accent : C.border;
        const textColor = isFailed ? C.red : done ? C.green : active ? C.accent : C.muted;

        return (
          <div key={step.key} style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: 64 }}>
              <div
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  background: dotColor,
                  border: active ? `2px solid ${C.accent}88` : "none",
                  boxShadow: active ? `0 0 0 3px ${C.accent}33` : "none",
                }}
              />
              <span style={{ fontSize: 10, color: textColor, marginTop: 6, fontWeight: active ? 600 : 400 }}>
                {isFailed ? "Failed" : step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                style={{
                  width: 28,
                  height: 2,
                  background: done ? C.green : C.border,
                  marginBottom: 18,
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
