"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Calendar, Layers } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { ArticleCard, type Article as ArticleCardModel } from "@/components/ArticleCard";
import { ReportDocument } from "@/components/report/ReportDocument";
import { ReportOutline } from "@/components/report/ReportOutline";
import { useActiveHeading } from "@/hooks/use-active-heading";
import { canonicalizeReportContent, extractOutline, parseReportContent } from "@/lib/report-content-parser";
import { getArticleById, getReportById, type Article as APIArticle, type Report as APIReport } from "@/lib/api";

const MAX_DAILY_REPORT_EVENTS = 15;
const REPORT_TYPE_LABELS: Record<APIReport["report_type"], string> = {
  daily: "Daily",
  weekly: "Weekly",
  research: "Research",
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

export default function ReportDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const [report, setReport] = useState<APIReport | null>(null);
  const [articles, setArticles] = useState<APIArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      if (!id) return;
      setLoading(true);
      setError(null);
      try {
        const reportData = await getReportById(id);
        if (cancelled) return;
        setReport(reportData);
        const effectiveContent = canonicalizeReportContent(
          reportData.content ?? "",
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
    return canonicalizeReportContent(report.content ?? "", report.events, report.global_tldr ?? "");
  }, [report]);
  const parsedReport = useMemo(() => parseReportContent(effectiveReportContent), [effectiveReportContent]);
  const hasTemplateContent = Boolean(effectiveReportContent.trim() && parsedReport.sections.length > 0);

  const outlineItems = useMemo(() => extractOutline(parsedReport.sections), [parsedReport.sections]);
  const activeHeadingId = useActiveHeading(outlineItems.map((item) => item.id));
  const displayEventCount = report?.events.length ?? 0;
  const displayTitle = useMemo(() => {
    if (!report) return "";
    if (report.report_type === "daily" && report.report_date) {
      return `AI 早报 ${report.report_date}`;
    }
    return report.title;
  }, [report]);

  const sourceCount = useMemo(() => {
    if (!report) return 0;
    const eventSources = new Set(report.events.map((event) => event.source_name).filter(Boolean));
    if (eventSources.size > 0) return eventSources.size;
    const articleSources = new Set(articles.map((article) => article.source_name).filter(Boolean));
    if (articleSources.size > 0) return articleSources.size;
    return report.article_count;
  }, [articles, report]);

  const handleNavigate = (sectionId: string) => {
    const target = document.getElementById(sectionId);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", `#${sectionId}`);
    }
  };

  if (loading) {
    return <div className="py-10 text-sm text-muted-foreground">Loading report...</div>;
  }

  if (error || !report) {
    return <div className="py-10 text-sm text-red-500">Failed to load report: {error ?? "Not found"}</div>;
  }

  return (
    <div className="max-w-[1400px] w-full mx-auto py-8 sm:py-12 pb-24 px-4 lg:px-6">
      <Link
        href="/"
        className="inline-flex items-center space-x-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-10 group"
      >
        <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
        <span>Back to Discover</span>
      </Link>

      <div className={`relative flex flex-col gap-10 items-start ${hasTemplateContent ? 'lg:pr-[210px]' : ''}`}>
        <div className="order-1 min-w-0 w-full">
          <header className="mb-14 mt-2">
            <div className="flex flex-wrap items-center gap-3 mb-6">
              <Badge variant="secondary" className="bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 border-none font-medium px-3 py-1">
                {REPORT_TYPE_LABELS[report.report_type]}
              </Badge>
              <div className="flex items-center space-x-1.5 text-sm font-medium text-muted-foreground/80">
                <Calendar className="w-4 h-4" />
                <span>{new Date(report.report_date).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}</span>
              </div>
              <div className="flex items-center space-x-1.5 text-sm font-medium text-muted-foreground/80">
                <Layers className="w-4 h-4" />
                <span>{sourceCount} Sources</span>
              </div>
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-5xl font-extrabold tracking-tight leading-[1.15] mb-6 text-foreground">
              {displayTitle}
            </h1>

            {report.tldr.length > 0 && !hasTemplateContent && (
              <div className="text-xl sm:text-2xl font-medium text-foreground/70 max-w-3xl leading-relaxed border-l-4 border-blue-500/30 pl-5 py-1">
                {report.tldr[0]}
              </div>
            )}
          </header>

          {hasTemplateContent ? (
            <section className="bg-background rounded-2xl border-none sm:border sm:border-border/40 sm:shadow-sm sm:p-8 md:p-10">
              <ReportDocument
                content={effectiveReportContent}
                events={report.events}
                globalTldr={report.global_tldr}
                topics={report.topics}
              />
            </section>
          ) : (
            <div className="space-y-16">
              {[...grouped.entries()].map(([category, categoryArticles]) => (
                <section key={category}>
                  <div className="flex items-center space-x-3 mb-6">
                    <h2 className="text-2xl font-semibold tracking-tight capitalize">{category.replace("_", " ")}</h2>
                    <Badge variant="outline" className="text-xs font-normal text-muted-foreground">
                      {categoryArticles.length} Updates
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
                  This report currently has no resolved article details.
                </div>
              )}
            </div>
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
    </div>
  );
}
