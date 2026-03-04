"use client";

import { useEffect, useMemo, useState } from "react";
import { ReportCard, type Report as ReportCardModel } from "@/components/ReportCard";
import { getReports, type Report as APIReport } from "@/lib/api";
import { cn } from "@/lib/utils";

const TIME_TABS = [
  { id: "all", label: "Overview" },
  { id: "daily", label: "Daily" },
  { id: "weekly", label: "Weekly" },
  { id: "custom", label: "Custom" },
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
  };
}

export default function LibraryPage() {
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("all");
  const [reports, setReports] = useState<ReportCardModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getReports({ limit: 100, page: 1 });
        setReports(data.map(toCardReport));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const filteredReports = useMemo(() => {
    return reports.filter((report) => timeFilter === "all" || report.time_period === timeFilter);
  }, [reports, timeFilter]);

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-8 md:py-12">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2">Knowledge Library</h1>
        <p className="text-muted-foreground text-sm max-w-2xl">
          Search and browse through all historically generated reports and analyses.
        </p>
      </header>

      <div className="flex items-center space-x-6 mb-8 border-b border-border/60 pb-px overflow-x-auto scrollbar-none">
        {TIME_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setTimeFilter(tab.id)}
            className={cn(
              "pb-3 text-sm font-medium transition-colors relative whitespace-nowrap outline-none flex items-center",
              timeFilter === tab.id ? "text-foreground" : "text-muted-foreground hover:text-foreground"
            )}
          >
            {tab.label}
            {timeFilter === tab.id && <span className="absolute left-0 right-0 bottom-0 h-0.5 bg-foreground rounded-t-full" />}
          </button>
        ))}
      </div>

      {loading && <div className="py-10 text-sm text-muted-foreground">Loading reports...</div>}
      {error && <div className="py-10 text-sm text-red-500">Failed to load reports: {error}</div>}

      {!loading && !error && (
        <div className="space-y-6">
          {filteredReports.map((report, i) => (
            <ReportCard key={report.id} report={report} index={i} />
          ))}
          {filteredReports.length === 0 && (
            <div className="text-center py-20 bg-muted/10 rounded-xl border border-dashed border-border/50">
              <p className="text-muted-foreground">No reports match the selected filters.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
