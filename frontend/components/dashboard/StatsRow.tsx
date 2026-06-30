import { GitBranch, GitPullRequest, AlertTriangle, Code, TrendingDown } from "lucide-react";
import { StatCard } from "@/components/ui/Primitives";
import { C } from "@/lib/theme";
import type { Stats } from "@/lib/api";

export function StatsRow({ stats }: { stats: Stats }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
        gap: 12,
        marginBottom: 28,
      }}
    >
      <StatCard label="Repositories" value={stats.total_repos} icon={<GitBranch size={22} color={C.accent} />} />
      <StatCard
        label="Issues Found"
        value={stats.total_issues}
        icon={<AlertTriangle size={22} color={C.yellow} />}
        color={C.yellow}
      />
      <StatCard
        label="PRs Opened"
        value={stats.prs_opened}
        icon={<GitPullRequest size={22} color={C.green} />}
        color={C.green}
      />
      <StatCard
        label="Avg Complexity"
        value={stats.avg_complexity_before?.toFixed(1)}
        sub="before refactor"
        icon={<Code size={22} color="#f97316" />}
        color="#f97316"
      />
      <StatCard
        label="Complexity Reduction"
        value={`${stats.complexity_reduction_pct}%`}
        sub="avg across refactors"
        icon={<TrendingDown size={22} color={C.green} />}
        color={C.green}
      />
    </div>
  );
}
