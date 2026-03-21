"use client";

import { useEffect, useState } from "react";
import { ReportCard, type Report as ReportCardModel } from "@/components/ReportCard";
import { getReports, type Report as APIReport } from "@/lib/api";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

const DISCOVER_REPORTS_TIMEOUT_MS = 15_000;

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const timerId = setTimeout(() => {
      reject(new Error(`Request timeout after ${Math.round(timeoutMs / 1000)}s`));
    }, timeoutMs);
    promise.then(
      (value) => {
        clearTimeout(timerId);
        resolve(value);
      },
      (error: unknown) => {
        clearTimeout(timerId);
        reject(error);
      }
    );
  });
}

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

export default function DiscoverPage() {
  const [reports, setReports] = useState<ReportCardModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await withTimeout(getReports({ limit: 10, page: 1 }), DISCOVER_REPORTS_TIMEOUT_MS);
        const filtered = data.filter((report) => {
          if (report.report_type !== "paper") return true;
          const rawMeta = (report.metadata ?? {}) as Record<string, unknown>;
          return rawMeta.paper_mode !== "note";
        });
        setReports(filtered.map(toCardReport));
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
          <h1 className="text-3xl font-bold tracking-tight mb-2">报告</h1>
          <p className="text-muted-foreground text-sm max-w-2xl">
            最近生成的报告
          </p>
        </div>
        <Link
          href="/library"
          className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 flex items-center group transition-colors whitespace-nowrap"
        >
          查看所有历史
          <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-0.5 transition-transform" />
        </Link>
      </header>

      {loading && <div className="py-10 text-sm text-muted-foreground">正在加载报告...</div>}
      {error && <div className="py-10 text-sm text-red-500">加载报告失败：{error}</div>}

      {!loading && !error && (
        <div className="space-y-6">
          {reports.map((report, i) => (
            <ReportCard key={report.id} report={report} index={i} />
          ))}
          {reports.length === 0 && (
            <div className="text-center py-20 bg-muted/10 rounded-xl border border-dashed border-border/50">
              <p className="text-muted-foreground">今日暂无新报告。</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
