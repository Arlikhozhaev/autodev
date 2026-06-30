"use client";

import { C } from "@/lib/theme";
import { useIsMobile } from "@/hooks/useMediaQuery";

type DiffLine = { num: number; text: string; kind: "same" | "add" | "remove" };

function buildDiff(before: string, after: string): { left: DiffLine[]; right: DiffLine[] } {
  const beforeLines = before.split("\n");
  const afterLines = after.split("\n");
  const max = Math.max(beforeLines.length, afterLines.length);
  const left: DiffLine[] = [];
  const right: DiffLine[] = [];

  for (let i = 0; i < max; i++) {
    const b = beforeLines[i];
    const a = afterLines[i];
    if (b === a) {
      if (b !== undefined) {
        left.push({ num: i + 1, text: b, kind: "same" });
        right.push({ num: i + 1, text: a, kind: "same" });
      }
    } else {
      if (b !== undefined) left.push({ num: i + 1, text: b, kind: "remove" });
      if (a !== undefined) right.push({ num: i + 1, text: a, kind: "add" });
    }
  }
  return { left, right };
}

const LINE_BG: Record<DiffLine["kind"], string> = {
  same: "transparent",
  add: C.green + "18",
  remove: C.red + "18",
};

function DiffPane({ title, lines, accent }: { title: string; lines: DiffLine[]; accent: string }) {
  return (
    <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
      <div
        style={{
          padding: "8px 12px",
          fontSize: 11,
          fontWeight: 600,
          color: accent,
          borderBottom: `1px solid ${C.border}`,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
        }}
      >
        {title}
      </div>
      <pre
        style={{
          margin: 0,
          padding: 12,
          overflow: "auto",
          maxHeight: 320,
          fontSize: 12,
          lineHeight: 1.55,
          fontFamily: "ui-monospace, 'Cascadia Code', monospace",
          color: C.text,
        }}
      >
        {lines.map((line) => (
          <div
            key={`${title}-${line.num}`}
            style={{
              display: "flex",
              background: LINE_BG[line.kind],
              borderRadius: 2,
            }}
          >
            <span style={{ width: 36, flexShrink: 0, color: C.muted, userSelect: "none" }}>
              {line.num}
            </span>
            <code style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{line.text}</code>
          </div>
        ))}
      </pre>
    </div>
  );
}

export function DiffViewer({
  before,
  after,
  title,
  subtitle,
}: {
  before: string;
  after: string;
  title?: string;
  subtitle?: string;
}) {
  const isMobile = useIsMobile();
  const { left, right } = buildDiff(before, after);

  return (
    <div
      style={{
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        overflow: "hidden",
        background: C.bg,
      }}
    >
      {(title || subtitle) && (
        <div style={{ padding: "10px 14px", borderBottom: `1px solid ${C.border}` }}>
          {title && <div style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{title}</div>}
          {subtitle && <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>{subtitle}</div>}
        </div>
      )}
      <div
        style={{
          display: "flex",
          flexDirection: isMobile ? "column" : "row",
        }}
      >
        <DiffPane title="Before" lines={left} accent={C.red} />
        {!isMobile && <div style={{ width: 1, background: C.border, flexShrink: 0 }} />}
        {isMobile && <div style={{ height: 1, background: C.border }} />}
        <DiffPane title="After" lines={right} accent={C.green} />
      </div>
    </div>
  );
}
