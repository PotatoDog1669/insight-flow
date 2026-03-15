"use client";

import { useEffect, useMemo, useState } from "react";
import { ReportCard, type Report as ReportCardModel } from "@/components/ReportCard";
import { deleteReport, getReportFilters, getReports, type Report as APIReport, type ReportFilters } from "@/lib/api";
import { cn } from "@/lib/utils";

const TIME_TABS = [
  { id: "all", label: "总览" },
  { id: "daily", label: "日报" },
  { id: "weekly", label: "周报" },
  { id: "custom", label: "自定义" },
] as const;

type TimeFilter = (typeof TIME_TABS)[number]["id"];

function toCardReport(report: APIReport): ReportCardModel {
  return {
    id: report.id,
    time_period: report.time_period,
    report_type: report.report_type,
    title: report.title,
    report_date: report.report_date,
    tldr: report.tldr,
    article_count: report.article_count,
    topics: report.topics,
    monitor_id: report.monitor_id,
    monitor_name: report.monitor_name,
  };
}

export default function LibraryPage() {
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("all");
  const [monitorFilter, setMonitorFilter] = useState("all");
  const [reports, setReports] = useState<ReportCardModel[]>([]);
  const [reportFilters, setReportFilters] = useState<ReportFilters>({
    time_periods: [],
    report_types: [],
    categories: [],
    monitors: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingReportIds, setDeletingReportIds] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [data, filters] = await Promise.all([
          getReports({ limit: 100, page: 1 }),
          getReportFilters(),
        ]);
        setReports(data.map(toCardReport));
        setReportFilters(filters);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const filteredReports = useMemo(() => {
    return reports.filter((report) => {
      const matchesTime = timeFilter === "all" || report.time_period === timeFilter;
      const matchesMonitor = monitorFilter === "all" || report.monitor_id === monitorFilter;
      return matchesTime && matchesMonitor;
    });
  }, [monitorFilter, reports, timeFilter]);

  const handleDelete = async (reportId: string) => {
    if (typeof window !== "undefined" && !window.confirm("确认删除这份报告吗？")) {
      return;
    }
    setError(null);
    setDeletingReportIds((prev) => ({ ...prev, [reportId]: true }));
    try {
      await deleteReport(reportId);
      setReports((prev) => prev.filter((report) => report.id !== reportId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setDeletingReportIds((prev) => {
        const next = { ...prev };
        delete next[reportId];
        return next;
      });
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-8 md:py-12">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2">归档</h1>
        <p className="text-muted-foreground text-sm max-w-2xl">
          搜索并浏览历史上生成的所有报告和分析。
        </p>
      </header>

      <div className="mb-8 flex flex-col gap-4 border-b border-border/60 pb-px md:flex-row md:items-end md:justify-between">
        <div className="flex items-center space-x-6 overflow-x-auto scrollbar-none">
          {TIME_TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setTimeFilter(tab.id)}
              className={cn(
                "pb-3 px-1 text-sm font-medium transition-colors relative whitespace-nowrap outline-none flex items-center rounded-t-md focus-visible:ring-2 focus-visible:ring-ring",
                timeFilter === tab.id ? "text-foreground" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {tab.label}
              {timeFilter === tab.id && <span className="absolute left-0 right-0 bottom-0 h-0.5 bg-foreground rounded-t-full" />}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3 pb-3 md:justify-end">
          <label htmlFor="library-monitor-filter" className="text-sm font-medium whitespace-nowrap">
            任务主题
          </label>
          <select
            id="library-monitor-filter"
            value={monitorFilter}
            onChange={(event) => setMonitorFilter(event.target.value)}
            className="h-10 min-w-[220px] rounded-md border border-border bg-background px-3 text-sm shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="all">全部任务</option>
            {reportFilters.monitors.map((monitor) => (
              <option key={monitor.id} value={monitor.id}>
                {monitor.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && <div className="py-10 text-sm text-muted-foreground">正在加载报告...</div>}
      {error && <div className="py-10 text-sm text-red-500">加载报告失败：{error}</div>}

      {!loading && !error && (
        <div className="space-y-6">
          {filteredReports.map((report, i) => (
            <ReportCard
              key={report.id}
              report={report}
              index={i}
              onDelete={(reportId) => {
                void handleDelete(reportId);
              }}
              deleting={Boolean(deletingReportIds[report.id])}
            />
          ))}
          {filteredReports.length === 0 && (
            <div className="text-center py-20 bg-muted/10 rounded-xl border border-dashed border-border/50">
              <p className="text-muted-foreground">没有符合筛选条件的报告。</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
