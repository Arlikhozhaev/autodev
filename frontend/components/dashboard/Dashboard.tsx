"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Header } from "@/components/dashboard/Header";
import { AnalyzeBar } from "@/components/dashboard/AnalyzeBar";
import { StatsRow } from "@/components/dashboard/StatsRow";
import { RepoSidebar } from "@/components/dashboard/RepoSidebar";
import { RepoDetailPanel } from "@/components/dashboard/RepoDetailPanel";
import { ConfirmModal, Toast } from "@/components/ui/Primitives";
import { useIsMobile } from "@/hooks/useMediaQuery";
import { api, type Repo, type Stats, type ReportResponse, type Refactor, type TaskStatus } from "@/lib/api";
import { C, type TabId } from "@/lib/theme";
import { errorMessage } from "@/lib/utils";

const ACTIVE_STATUSES = ["cloning", "analyzing", "refactoring", "validating"];
const VALID_TABS: TabId[] = ["issues", "refactors", "charts"];

function parseTab(value: string | null): TabId {
  if (value && VALID_TABS.includes(value as TabId)) return value as TabId;
  return "issues";
}

export function Dashboard({ initialRepoId }: { initialRepoId?: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isMobile = useIsMobile();

  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [repos, setRepos] = useState<Repo[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(initialRepoId ?? null);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [refactors, setRefactors] = useState<Refactor[]>([]);
  const [loading, setLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>(parseTab(searchParams.get("tab")));
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" } | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);

  const selectedRepo = repos.find((r) => r.id === selectedRepoId) ?? null;

  const navigateToRepo = useCallback(
    (repoId: string, nextTab: TabId = tab) => {
      setSelectedRepoId(repoId);
      router.push(`/repos/${repoId}?tab=${nextTab}`);
    },
    [router, tab]
  );

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.listRepos();
      setRepos(r);
    } catch (e: unknown) {
      setError(errorMessage(e));
    }
    try {
      const s = await api.getStats();
      setStats(s);
    } catch {
      // Stats are non-critical; repos list still loads if backend is up.
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadReport = useCallback(async (repoId: string, nextTab?: TabId) => {
    setSelectedRepoId(repoId);
    setReportLoading(true);
    setReport(null);
    setRefactors([]);
    if (nextTab) setTab(nextTab);
    try {
      const [rpt, rfcs] = await Promise.all([
        api.getReport(repoId),
        api.getRefactors(repoId),
      ]);
      setReport(rpt);
      setRefactors(rfcs);
    } catch (e: unknown) {
      setReport(null);
      setRefactors([]);
      const msg = errorMessage(e);
      if (!msg.includes("404")) {
        setError(`Failed to load report: ${msg}`);
      }
    } finally {
      setReportLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  useEffect(() => {
    const urlTab = parseTab(searchParams.get("tab"));
    setTab(urlTab);
  }, [searchParams]);

  useEffect(() => {
    if (initialRepoId) {
      loadReport(initialRepoId, parseTab(searchParams.get("tab")));
    }
  }, [initialRepoId, searchParams, loadReport]);

  useEffect(() => {
    if (!initialRepoId && repos.length > 0 && window.location.pathname === "/") {
      navigateToRepo(repos[0].id);
      loadReport(repos[0].id);
    }
  }, [repos, initialRepoId, navigateToRepo, loadReport]);

  useEffect(() => {
    const active = repos.some((r) => ACTIVE_STATUSES.includes(r.status));
    if (!active) return;
    const t = setInterval(fetchAll, 8000);
    return () => clearInterval(t);
  }, [repos, fetchAll]);

  useEffect(() => {
    const taskId = selectedRepo?.task_id;
    if (!taskId || !ACTIVE_STATUSES.includes(selectedRepo?.status ?? "")) {
      setTaskStatus(null);
      return;
    }

    let cancelled = false;
    const poll = async () => {
      try {
        const status = await api.getTaskStatus(taskId);
        if (!cancelled) setTaskStatus(status);
      } catch {
        if (!cancelled) setTaskStatus(null);
      }
    };

    poll();
    const t = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [selectedRepo?.task_id, selectedRepo?.status]);

  const showToast = (msg: string, type: "success" | "error" = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const handleTabChange = (nextTab: TabId) => {
    setTab(nextTab);
    if (selectedRepoId) {
      router.push(`/repos/${selectedRepoId}?tab=${nextTab}`);
    }
  };

  const handleAnalyze = async () => {
    if (!repoUrl.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.analyzeRepo(repoUrl.trim(), branch.trim() || "main");
      setRepoUrl("");
      showToast("Repository queued for analysis.");
      setTimeout(fetchAll, 500);
    } catch (e: unknown) {
      setError(errorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteRepo = async (repoId: string) => {
    setDeleteTarget(repoId);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await api.deleteRepo(deleteTarget);
      if (selectedRepoId === deleteTarget) {
        setSelectedRepoId(null);
        setReport(null);
        setRefactors([]);
        router.push("/");
      }
      fetchAll();
      showToast("Repository deleted.");
    } catch (e: unknown) {
      showToast(errorMessage(e), "error");
    } finally {
      setDeleteTarget(null);
    }
  };

  const handleRefactor = async (issueId: string) => {
    try {
      await api.triggerRefactor(issueId);
      showToast("Refactor queued — Celery is processing it now.");
      handleTabChange("refactors");
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        if (selectedRepoId) {
          const rfcs = await api.getRefactors(selectedRepoId);
          setRefactors(rfcs);
        }
        if (attempts >= 20) clearInterval(poll);
      }, 2000);
    } catch (e: unknown) {
      showToast(errorMessage(e), "error");
    }
  };

  const handleSelectRepo = (repoId: string) => {
    setSidebarOpen(false);
    navigateToRepo(repoId);
    loadReport(repoId);
  };

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.text }}>
      <Header
        onRefresh={fetchAll}
        showMenu={isMobile}
        onMenuClick={() => setSidebarOpen(true)}
      />

      <main style={{ padding: isMobile ? "16px" : "28px 32px" }}>
        {error && (
          <div
            role="alert"
            style={{
              background: C.red + "15",
              border: `1px solid ${C.red}44`,
              borderRadius: 8,
              padding: "10px 16px",
              marginBottom: 20,
              color: C.red,
              fontSize: 13,
            }}
          >
            {error}
          </div>
        )}

        {toast && <Toast message={toast.msg} type={toast.type} />}

        {deleteTarget && (
          <ConfirmModal
            title="Delete repository?"
            message="This will permanently delete the repository and all analysis data."
            confirmLabel="Delete"
            onConfirm={confirmDelete}
            onCancel={() => setDeleteTarget(null)}
          />
        )}

        <AnalyzeBar
          repoUrl={repoUrl}
          branch={branch}
          submitting={submitting}
          onUrlChange={setRepoUrl}
          onBranchChange={setBranch}
          onSubmit={handleAnalyze}
        />

        {stats && <StatsRow stats={stats} />}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: isMobile ? "1fr" : "280px 1fr",
            gap: 16,
            position: "relative",
          }}
        >
          {isMobile && sidebarOpen && (
            <div
              style={{
                position: "fixed",
                inset: 0,
                zIndex: 900,
                background: "rgba(0,0,0,0.5)",
              }}
              onClick={() => setSidebarOpen(false)}
            />
          )}

          <div
            style={
              isMobile
                ? {
                    position: "fixed",
                    top: 0,
                    left: sidebarOpen ? 0 : -300,
                    width: 280,
                    height: "100vh",
                    zIndex: 950,
                    transition: "left 0.2s ease",
                    padding: 12,
                    background: C.bg,
                  }
                : undefined
            }
          >
            {(!isMobile || sidebarOpen) && (
              <RepoSidebar
                repos={repos}
                selectedId={selectedRepoId}
                loading={loading}
                onSelect={handleSelectRepo}
                onDelete={handleDeleteRepo}
              />
            )}
          </div>

          <section
            style={{
              background: C.panel,
              border: `1px solid ${C.border}`,
              borderRadius: 12,
              overflow: "hidden",
              minWidth: 0,
            }}
          >
            <RepoDetailPanel
              repo={selectedRepo}
              report={report}
              refactors={refactors}
              loading={reportLoading}
              tab={tab}
              taskStatus={taskStatus}
              onTabChange={handleTabChange}
              onRetry={() => selectedRepoId && loadReport(selectedRepoId)}
              onRefactor={handleRefactor}
            />
          </section>
        </div>
      </main>
    </div>
  );
}
