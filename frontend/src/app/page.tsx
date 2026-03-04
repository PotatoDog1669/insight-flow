"use client";

import { useEffect, useState } from "react";
import { ReportCard, type Report as ReportCardModel } from "@/components/ReportCard";
import { getReports, type Report as APIReport } from "@/lib/api";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

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

export default function DiscoverPage() {
  const [reports, setReports] = useState<ReportCardModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getReports({ report_type: "research", limit: 10, page: 1 });
        setReports(data.map(toCardReport));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-8 md:py-12">
      <header className="mb-10 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2">Discover</h1>
          <p className="text-muted-foreground text-sm max-w-2xl">
            Latest high-value insights and daily aggregates generated for you.
          </p>
        </div>
        <Link
          href="/library"
          className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 flex items-center group transition-colors whitespace-nowrap"
        >
          View all history
          <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-0.5 transition-transform" />
        </Link>
      </header>

      {loading && <div className="py-10 text-sm text-muted-foreground">Loading reports...</div>}
      {error && <div className="py-10 text-sm text-red-500">Failed to load reports: {error}</div>}

      {!loading && !error && (
        <div className="space-y-6">
          {reports.map((report, i) => (
            <ReportCard key={report.id} report={report} index={i} />
          ))}
          {reports.length === 0 && (
            <div className="text-center py-20 bg-muted/10 rounded-xl border border-dashed border-border/50">
              <p className="text-muted-foreground">No fresh reports available today.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
