"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Calendar, Layers } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { ArticleCard, type Article as ArticleCardModel } from "@/components/ArticleCard";
import { ReportDocument } from "@/components/report/ReportDocument";
import { ReportMetaPanel } from "@/components/report/ReportMetaPanel";
import { ReportOutline } from "@/components/report/ReportOutline";
import { useActiveHeading } from "@/hooks/use-active-heading";
import { extractOutline, parseReportContent } from "@/lib/report-content-parser";
import { getArticleById, getReportById, type Article as APIArticle, type Report as APIReport } from "@/lib/api";

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
        if (!reportData.content?.trim()) {
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

  const hasTemplateContent = Boolean(report?.content?.trim());
  const parsedReport = useMemo(() => {
    if (!report || !hasTemplateContent) return { sections: [] };
    return parseReportContent(report.content);
  }, [hasTemplateContent, report]);

  const outlineItems = useMemo(() => extractOutline(parsedReport.sections), [parsedReport.sections]);
  const activeHeadingId = useActiveHeading(outlineItems.map((item) => item.id));

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
    <div className="max-w-4xl py-6 pb-20">
      <Link
        href="/"
        className="inline-flex items-center space-x-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-8 group"
      >
        <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
        <span>Back to Discover</span>
      </Link>

      <header className="mb-12 border-b border-border/50 pb-8">
        <div className="flex items-center space-x-3 mb-4">
          <Badge variant="secondary" className="bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 border-none font-medium px-2.5 py-1">
            {report.depth === "brief" ? "L1" : "L2"} • {report.time_period}
          </Badge>
          <div className="flex items-center space-x-1.5 text-sm text-muted-foreground">
            <Calendar className="w-4 h-4" />
            <span>{new Date(report.report_date).toLocaleDateString()}</span>
          </div>
          <div className="flex items-center space-x-1.5 text-sm text-muted-foreground">
            <Layers className="w-4 h-4" />
            <span>{sourceCount} Sources</span>
          </div>
        </div>

        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight leading-tight mb-4">{report.title}</h1>

        <p className="text-muted-foreground text-lg max-w-2xl leading-relaxed">
          {report.tldr.length > 0 ? report.tldr[0] : "Generated report detail view."}
        </p>
      </header>

      {hasTemplateContent ? (
        <div className="grid gap-6 lg:grid-cols-[220px_minmax(0,1fr)_240px]">
          <aside className="order-1 lg:order-none lg:sticky lg:top-6 lg:self-start">
            <ReportOutline items={outlineItems} activeId={activeHeadingId} onNavigate={handleNavigate} />
          </aside>

          <section className="order-2 lg:order-none min-w-0">
            <ReportDocument
              content={report.content}
              events={report.events}
              globalTldr={report.global_tldr}
              topics={report.topics}
            />
          </section>

          <aside className="order-3 lg:order-none lg:sticky lg:top-6 lg:self-start">
            <ReportMetaPanel
              eventCount={report.events.length}
              sourceCount={sourceCount}
              topics={report.topics}
              onTopicSelect={(topicName) => {
                const topicLower = topicName.toLowerCase();
                const matched = parsedReport.sections.find((section) =>
                  section.lines.some((line) => line.toLowerCase().includes(topicLower))
                );
                if (matched) {
                  handleNavigate(matched.id);
                }
              }}
            />
          </aside>
        </div>
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
  );
}
