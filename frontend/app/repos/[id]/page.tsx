"use client";

import { Suspense } from "react";
import { useParams } from "next/navigation";
import { Dashboard } from "@/components/dashboard/Dashboard";
import { C, SPIN_STYLE } from "@/lib/theme";
import { Loader2 } from "lucide-react";

function RepoFallback() {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: C.bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: C.muted,
      }}
    >
      <Loader2 size={32} style={SPIN_STYLE} />
    </div>
  );
}

function RepoPageInner() {
  const params = useParams();
  const repoId = typeof params.id === "string" ? params.id : undefined;
  return <Dashboard initialRepoId={repoId} />;
}

export default function RepoPage() {
  return (
    <Suspense fallback={<RepoFallback />}>
      <RepoPageInner />
    </Suspense>
  );
}
