"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/Primitives";
import { DiffViewer } from "@/components/dashboard/DiffViewer";
import { C } from "@/lib/theme";
import { shortPath } from "@/lib/utils";
import type { Refactor } from "@/lib/api";

function statusColor(status: string) {
  if (status === "pr_opened") return C.green;
  if (status === "validated") return C.accent;
  if (status === "failed") return C.red;
  return C.yellow;
}

function RefactorCard({ refactor }: { refactor: Refactor }) {
  const [expanded, setExpanded] = useState(false);
  const hasDiff = refactor.original_code && refactor.refactored_code;

  return (
    <div style={{ borderBottom: `1px solid ${C.border}` }}>
      <button
        type="button"
        onClick={() => hasDiff && setExpanded(!expanded)}
        style={{
          width: "100%",
          padding: "14px 16px",
          background: "transparent",
          border: "none",
          cursor: hasDiff ? "pointer" : "default",
          textAlign: "left",
          color: C.text,
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr auto",
            gap: 12,
            alignItems: "center",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <Badge text={refactor.status} color={statusColor(refactor.status)} />
              {refactor.validation_passed === true && (
                <Badge text="validated" color={C.green} />
              )}
              {refactor.function_name && (
                <span style={{ fontSize: 12, fontFamily: "monospace", color: C.text }}>
                  {refactor.function_name}
                </span>
              )}
            </div>
            {refactor.file_path && (
              <div style={{ fontSize: 11, color: C.muted, marginTop: 4 }}>
                {shortPath(refactor.file_path)}
              </div>
            )}
            <div style={{ fontSize: 12, color: C.subtext, marginTop: 6, fontFamily: "monospace" }}>
              {refactor.complexity_before != null
                ? `CC ${refactor.complexity_before} → ${refactor.complexity_after}`
                : "—"}
              {refactor.lines_before != null &&
                ` · ${refactor.lines_before} → ${refactor.lines_after} lines`}
              {refactor.tokens_used > 0 && ` · ${refactor.tokens_used} tokens`}
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {refactor.pr_url && (
              <a
                href={refactor.pr_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                style={{
                  color: C.accent,
                  fontSize: 11,
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  textDecoration: "none",
                }}
              >
                PR #{refactor.pr_number} <ExternalLink size={11} />
              </a>
            )}
            {hasDiff && (expanded ? <ChevronUp size={16} color={C.muted} /> : <ChevronDown size={16} color={C.muted} />)}
          </div>
        </div>
      </button>
      {expanded && hasDiff && (
        <div style={{ padding: "0 16px 16px" }}>
          <DiffViewer
            before={refactor.original_code!}
            after={refactor.refactored_code!}
            subtitle={refactor.explanation || refactor.validation_notes || undefined}
          />
        </div>
      )}
    </div>
  );
}

export function RefactorList({ refactors }: { refactors: Refactor[] }) {
  if (refactors.length === 0) {
    return (
      <div style={{ padding: 32, textAlign: "center", color: C.muted, fontSize: 13 }}>
        No refactors generated yet.
      </div>
    );
  }

  return (
    <div>
      {refactors.map((r) => (
        <RefactorCard key={r.id} refactor={r} />
      ))}
    </div>
  );
}
