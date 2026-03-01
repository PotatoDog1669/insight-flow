"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Calendar, Layers } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { ArticleCard, type Article as ArticleCardModel } from "@/components/ArticleCard";
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
    const load = async () => {
      if (!id) return;
      setLoading(true);
      setError(null);
      try {
        const reportData = await getReportById(id);
        setReport(reportData);
        const articleData = await Promise.all(
          reportData.article_ids.map(async (articleId) => {
            try {
              return await getArticleById(articleId);
            } catch {
              return null;
            }
          })
        );
        setArticles(articleData.filter((item): item is APIArticle => item !== null));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    void load();
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
            <span>{articles.length} Sources</span>
          </div>
        </div>

        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight leading-tight mb-4">{report.title}</h1>

        <p className="text-muted-foreground text-lg max-w-2xl leading-relaxed">
          {report.tldr.length > 0 ? report.tldr[0] : "Generated report detail view."}
        </p>
      </header>

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
    </div>
  );
}
