"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Calendar, Layers, RefreshCcw } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { ArticleCard, type Article as ArticleCardModel } from "@/components/ArticleCard";
import { ReportDocument } from "@/components/report/ReportDocument";
import { ReportOutline } from "@/components/report/ReportOutline";
import { useActiveHeading } from "@/hooks/use-active-heading";
import { canonicalizeReportContent, extractOutline, normalizePaperDigestContent, parseReportContent } from "@/lib/report-content-parser";
import { getReportDisplayTitle } from "@/lib/report-display";
import {
  getArticleById,
  getDestinations,
  getReportById,
  publishReportToDestination,
  type Article as APIArticle,
  type Destination,
  type Report as APIReport,
  type ReportPublishTraceEntry,
} from "@/lib/api";
const REPORT_TYPE_LABELS: Record<APIReport["report_type"], string> = {
  daily: "日报",
  weekly: "周报",
  research: "研究",
  paper: "论文",
};

function toArticleCard(article: APIArticle): ArticleCardModel {
  return {
    id: article.id,
    source_name: article.source_name ?? "Unknown Source",
    title: article.title,
    url: article.url ?? "#",
    summary: article.summary ?? "No summary available",
    score: article.ai_score ?? 0,
    published_at: article.published_at ?? article.collected_at,
    tags: article.keywords,
  };
}

type DestinationSyncState = "success" | "failed" | "pending";

function getDestinationStatus(report: APIReport, destinationId: Destination["id"]): {
  state: DestinationSyncState;
  label: string;
  detail: string;
} {
  const publishedDestinationIds = report.published_destination_instance_ids ?? [];
  if (publishedDestinationIds.includes(destinationId)) {
    return { state: "success", label: "已同步", detail: "该目标已经拥有当前报告内容。" };
  }

  const latestTrace = [...(report.publish_trace ?? [])]
    .reverse()
    .find(
      (entry: ReportPublishTraceEntry) =>
        entry.destination_instance_id === destinationId || entry.provider === destinationId
    );
  if (latestTrace?.status === "success") {
    return { state: "success", label: "已同步", detail: "该目标已经拥有当前报告内容。" };
  }
  if (latestTrace?.status === "failed") {
    return { state: "failed", label: "上次失败", detail: latestTrace.error || "最近一次同步失败。" };
  }
  return { state: "pending", label: "未同步", detail: "该目标还没有同步当前报告。" };
}

export default function ReportDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const [report, setReport] = useState<APIReport | null>(null);
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [articles, setArticles] = useState<APIArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [pendingSyncDestinationId, setPendingSyncDestinationId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      if (!id) return;
      setLoading(true);
      setError(null);
      try {
        const [reportData, destinationData] = await Promise.all([getReportById(id), getDestinations()]);
        if (cancelled) return;
        setReport(reportData);
        setDestinations((destinationData || []).filter((item) => item.enabled));
        const normalizedPaperContent =
          reportData.report_type === "paper"
            ? normalizePaperDigestContent(
                reportData.content ?? "",
                (reportData.metadata ?? {}) as Record<string, unknown>,
                reportData.report_date
              )
            : reportData.content ?? "";
        const effectiveContent = canonicalizeReportContent(
          normalizedPaperContent,
          reportData.events ?? [],
          reportData.global_tldr ?? ""
        );
        const parsedReport = parseReportContent(effectiveContent);
        const canUseTemplateContent = Boolean(effectiveContent.trim() && parsedReport.sections.length > 0);

        if (!canUseTemplateContent) {
          const articleData = await Promise.all(
            reportData.article_ids.map(async (articleId) => {
              try {
                return await getArticleById(articleId);
              } catch {
                return null;
              }
            })
          );
          if (cancelled) return;
          setArticles(articleData.filter((item): item is APIArticle => item !== null));
        } else {
          setArticles([]);
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        if (cancelled) return;
        setLoading(false);
      }
    };
    void load();

    return () => {
      cancelled = true;
    };
  }, [id]);

  const grouped = useMemo(() => {
    const groups = new Map<string, APIArticle[]>();
    for (const article of articles) {
      const key = article.category ?? "others";
      const current = groups.get(key) ?? [];
      current.push(article);
      groups.set(key, current);
    }
    return groups;
  }, [articles]);

  const effectiveReportContent = useMemo(() => {
    if (!report) return "";
    const normalizedPaperContent =
      report.report_type === "paper"
        ? normalizePaperDigestContent(
            report.content ?? "",
            (report.metadata ?? {}) as Record<string, unknown>,
            report.report_date
          )
        : report.content ?? "";
    return canonicalizeReportContent(normalizedPaperContent, report.events, report.global_tldr ?? "");
  }, [report]);
  const parsedReport = useMemo(() => parseReportContent(effectiveReportContent), [effectiveReportContent]);
  const hasTemplateContent = Boolean(effectiveReportContent.trim() && parsedReport.sections.length > 0);
  const shouldShowCoverSummary = Boolean(
    report?.tldr.length && (!hasTemplateContent || report.report_type === "research")
  );

  const outlineItems = useMemo(() => extractOutline(parsedReport.sections), [parsedReport.sections]);
  const activeHeadingId = useActiveHeading(outlineItems.map((item) => item.id));
  const displayTitle = useMemo(() => {
    if (!report) return "";
    return getReportDisplayTitle(report);
  }, [report]);

  const sourceCount = useMemo(() => {
    if (!report) return 0;
    const eventSources = new Set(report.events.map((event) => event.source_name).filter(Boolean));
    if (eventSources.size > 0) return eventSources.size;
    const articleSources = new Set(articles.map((article) => article.source_name).filter(Boolean));
    if (articleSources.size > 0) return articleSources.size;
    return report.article_count;
  }, [articles, report]);

  const syncDestinations = useMemo(
    () => destinations.filter((item) => item.enabled),
    [destinations],
  );

  const handleNavigate = (sectionId: string) => {
    const target = document.getElementById(sectionId);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", `#${sectionId}`);
    }
  };

  const confirmPublish = async (destinationId: Destination["id"]) => {
    if (!report) return;
    setSyncingId(destinationId);
    setSyncError(null);
    setPendingSyncDestinationId(null);
    try {
      const updated = await publishReportToDestination(report.id, [destinationId]);
      setReport(updated);
    } catch (err) {
      setSyncError(err instanceof Error ? err.message : "同步失败");
      try {
        const refreshed = await getReportById(report.id);
        setReport(refreshed);
      } catch {
        // Keep current report state when refresh also fails.
      }
    } finally {
      setSyncingId(null);
    }
  };

  const pendingSyncDestination = useMemo(
    () => syncDestinations.find((item) => item.id === pendingSyncDestinationId) ?? null,
    [pendingSyncDestinationId, syncDestinations]
  );

  if (loading) {
    return <div className="py-10 text-sm text-muted-foreground">正在加载报告...</div>;
  }

  if (error || !report) {
    return <div className="py-10 text-sm text-red-500">加载报告失败：{error ?? "未找到"}</div>;
  }

  return (
    <div className="max-w-[1400px] w-full mx-auto py-8 sm:py-12 pb-24 px-4 lg:px-6">
      <Link
        href="/"
        className="inline-flex items-center space-x-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-10 group"
      >
        <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
        <span>返回发现页</span>
      </Link>

      <div className={`relative flex flex-col gap-10 items-start ${hasTemplateContent ? 'lg:pr-[210px]' : ''}`}>
        <div className="order-1 min-w-0 w-full">
          <header className="mb-14 mt-2">
            <div className="mb-6 flex flex-wrap items-center gap-3">
              <Badge variant="secondary" className="bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 border-none font-medium px-3 py-1">
                {REPORT_TYPE_LABELS[report.report_type]}
              </Badge>
              <div className="flex items-center space-x-1.5 text-sm font-medium text-muted-foreground/80">
                <Calendar className="w-4 h-4" />
                <span>{new Date(report.report_date).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}</span>
              </div>
              <div className="flex items-center space-x-1.5 text-sm font-medium text-muted-foreground/80">
                <Layers className="w-4 h-4" />
                <span>{sourceCount} 个信息源</span>
              </div>
              {report.monitor_name ? (
                <div className="text-sm font-medium text-muted-foreground/80">
                  所属任务：<span className="text-foreground">{report.monitor_name}</span>
                </div>
              ) : null}
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-5xl font-extrabold tracking-tight leading-[1.15] mb-6 text-foreground">
              {displayTitle}
            </h1>

            {shouldShowCoverSummary && (
              <div className="text-xl sm:text-2xl font-medium text-foreground/70 max-w-3xl leading-relaxed border-l-4 border-blue-500/30 pl-5 py-1">
                {report.tldr[0]}
              </div>
            )}
          </header>
          {hasTemplateContent ? (
            <section className="bg-card rounded-2xl border-none sm:border sm:border-border/50 shadow-sm sm:p-8 md:p-10">
              <ReportDocument
                content={effectiveReportContent}
                events={report.events}
                globalTldr={report.global_tldr}
                topics={report.topics}
                suppressFirstHeading={report.report_type === "paper"}
              />
            </section>
          ) : (
            <div className="space-y-16">
              {[...grouped.entries()].map(([category, categoryArticles]) => (
                <section key={category}>
                  <div className="flex items-center space-x-3 mb-6">
                    <h2 className="text-2xl font-semibold tracking-tight capitalize">{category.replace("_", " ")}</h2>
                    <Badge variant="outline" className="text-xs font-normal text-muted-foreground">
                      {categoryArticles.length} 篇更新
                    </Badge>
                  </div>
                  <div className="space-y-5">
                    {categoryArticles.map((article, idx) => (
                      <ArticleCard key={article.id} article={toArticleCard(article)} index={idx} />
                    ))}
                  </div>
                </section>
              ))}

              {articles.length === 0 && (
                <div className="text-center py-12 text-muted-foreground border border-dashed border-border/50 rounded-xl">
                  此报告目前没有解析出的文章详情。
                </div>
              )}
            </div>
          )}

          {syncDestinations.length > 0 && (
            <section className="mt-10 rounded-2xl border border-border/50 bg-muted/20 p-5 sm:p-6">
              <div className="mb-4 flex items-center gap-2">
                <RefreshCcw className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-lg font-semibold tracking-tight">同步</h2>
              </div>
              <p className="mb-4 text-sm text-muted-foreground">
                对未同步或上次失败的目标，可以立即同步这篇报告。
              </p>
              {syncError ? <p className="mb-4 text-sm text-red-500">{syncError}</p> : null}
              <div className="space-y-3">
                {syncDestinations.map((destination) => {
                  const status = report ? getDestinationStatus(report, destination.id) : null;
                  const actionable = status?.state !== "success";
                  return (
                    <div
                      key={destination.id}
                      className="flex flex-col gap-3 rounded-xl border border-border/50 bg-background/80 p-4 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-foreground">{destination.name}</span>
                          {status ? (
                            <Badge variant="outline" className="text-xs">
                              {status.label}
                            </Badge>
                          ) : null}
                        </div>
                        <p className="mt-1 text-sm text-muted-foreground">{status?.detail}</p>
                      </div>
                      {actionable ? (
                        <button
                          type="button"
                          className="inline-flex items-center justify-center rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-background transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                          onClick={() => setPendingSyncDestinationId(destination.id)}
                          disabled={syncingId === destination.id}
                        >
                          {syncingId === destination.id ? "同步中..." : `同步到 ${destination.name}`}
                        </button>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </div>

        {hasTemplateContent && (
          <aside className="hidden lg:block lg:fixed lg:top-24 lg:right-4 lg:w-[220px] lg:max-h-[calc(100vh-7rem)] overflow-y-auto scrollbar-none">
            <div className="pl-2 pr-1">
              <ReportOutline items={outlineItems} activeId={activeHeadingId} onNavigate={handleNavigate} />
            </div>
          </aside>
        )}
      </div>

      {pendingSyncDestination && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-background/80 backdrop-blur-sm"
            onClick={() => setPendingSyncDestinationId(null)}
          />
          <div className="relative z-10 w-full max-w-lg overflow-hidden rounded-3xl border border-border/50 bg-card shadow-2xl">
            <div className="border-b border-border/40 bg-card/90 px-6 py-5">
              <h2 className="text-xl font-semibold tracking-tight">确认同步</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                这会立即把当前报告同步到目标落盘点。
              </p>
            </div>
            <div className="space-y-4 px-6 py-6">
              <div className="rounded-2xl border border-border/50 bg-muted/30 p-4">
                <div className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                  目标实例
                </div>
                <div className="mt-2 text-base font-semibold text-foreground">
                  {pendingSyncDestination.name}
                </div>
                <div className="mt-1 text-sm text-muted-foreground capitalize">
                  {pendingSyncDestination.type}
                </div>
              </div>
              <div className="rounded-2xl border border-border/50 bg-card p-4">
                <div className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                  报告
                </div>
                <div className="mt-2 text-base font-semibold text-foreground">
                  {displayTitle}
                </div>
                <div className="mt-1 text-sm text-muted-foreground">
                  {report.monitor_name ? `来自任务 ${report.monitor_name}` : "手动生成报告"}
                </div>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 border-t border-border/40 bg-card/60 px-6 py-4">
              <button
                type="button"
                onClick={() => setPendingSyncDestinationId(null)}
                className="rounded-xl border border-border/60 bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void confirmPublish(pendingSyncDestination.id)}
                disabled={syncingId === pendingSyncDestination.id}
                className="rounded-xl bg-foreground px-4 py-2 text-sm font-medium text-background transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {syncingId === pendingSyncDestination.id ? "同步中..." : "确认同步"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
