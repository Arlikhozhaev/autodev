import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, Legend,
} from "recharts";
import { C } from "@/lib/theme";
import type { Issue, Refactor } from "@/lib/api";

export function ChartsPanel({
  issues,
  refactors,
}: {
  issues: Issue[];
  refactors: Refactor[];
}) {
  const complexityChartData = issues
    .filter((i) => i.issue_type === "complexity" && i.metric_value)
    .slice(0, 12)
    .map((i) => ({
      name: i.function_name || "fn",
      complexity: i.metric_value,
    }));

  const issueTypeData = Object.entries(
    issues.reduce((acc, i) => {
      acc[i.issue_type] = (acc[i.issue_type] || 0) + 1;
      return acc;
    }, {} as Record<string, number>)
  ).map(([type, count]) => ({ type: type.replace("_", " "), count }));

  const refactorChart = refactors
    .filter((r) => r.complexity_before && r.complexity_after)
    .slice(0, 10)
    .map((r, i) => ({
      name: `#${i + 1}`,
      before: r.complexity_before,
      after: r.complexity_after,
    }));

  const tooltipStyle = {
    contentStyle: { background: C.panel, border: `1px solid ${C.border}`, borderRadius: 8 },
    labelStyle: { color: C.text },
  };

  return (
    <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 24 }}>
      {complexityChartData.length > 0 && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: C.subtext, marginBottom: 12 }}>
            FUNCTION COMPLEXITY SCORES
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={complexityChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis dataKey="name" tick={{ fill: C.muted, fontSize: 10 }} />
              <YAxis tick={{ fill: C.muted, fontSize: 10 }} />
              <Tooltip {...tooltipStyle} />
              <Bar dataKey="complexity" fill={C.accent} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      {issueTypeData.length > 0 && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: C.subtext, marginBottom: 12 }}>
            ISSUES BY TYPE
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={issueTypeData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis type="number" tick={{ fill: C.muted, fontSize: 10 }} />
              <YAxis dataKey="type" type="category" tick={{ fill: C.muted, fontSize: 10 }} width={100} />
              <Tooltip {...tooltipStyle} />
              <Bar dataKey="count" fill="#a855f7" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      {refactorChart.length > 0 && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: C.subtext, marginBottom: 12 }}>
            COMPLEXITY BEFORE vs AFTER REFACTOR
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={refactorChart}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis dataKey="name" tick={{ fill: C.muted, fontSize: 10 }} />
              <YAxis tick={{ fill: C.muted, fontSize: 10 }} />
              <Tooltip {...tooltipStyle} />
              <Legend wrapperStyle={{ color: C.muted, fontSize: 11 }} />
              <Line type="monotone" dataKey="before" stroke={C.red} strokeWidth={2} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="after" stroke={C.green} strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
