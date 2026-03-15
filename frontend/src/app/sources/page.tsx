"use client";

import { useEffect, useMemo, useState } from "react";
import { SourceStatusPanel } from "@/components/SourceStatusPanel";
import { createSource, getSources, type Source } from "@/lib/api";
import { Plus, X, Globe, Rss, Github, BookOpen, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";

import { SourceDetailModal } from "@/components/SourceDetailModal";

type SourceCategory = "blog" | "open_source" | "academic" | "social";

function slugify(input: string): string {
  return input
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "_")
    .replace(/_+/g, "_");
}

function inferSourceConfig(category: SourceCategory, url: string, name: string) {
  if (category === "open_source") {
    if (url.includes("huggingface.co")) {
      return {
        collect_method: "huggingface",
        config: { limit: 30, include_paper_detail: true, include_arxiv_repos: true },
      };
    }
    return {
      collect_method: "github_trending",
      config: { since: "daily", limit: 10, include_readme: true, include_repo_tree: true },
    };
  }

  const isLikelyFeed = /rss|feed|\.xml/i.test(url);
  if (isLikelyFeed) {
    return {
      collect_method: "rss",
      config: { feed_url: url, max_items: 20 },
    };
  }

  let origin = "";
  try {
    origin = new URL(url).origin;
  } catch {
    origin = "";
  }

  return {
    collect_method: "blog_scraper",
    config: {
      profile: {
        site_key: slugify(name || "custom_site"),
        start_urls: [url],
        list_page: {
          item_selector: "a[href]",
          url_attr: "href",
        },
        detail_page: {
          content_selector: "article, main, body",
          remove_selectors: ["script", "style", "nav"],
        },
        normalization: {
          url_prefix: origin,
          min_content_chars: 200,
        },
      },
    },
  };
}

export default function SourcesPage() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [category, setCategory] = useState<SourceCategory>("blog");
  const [url, setUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const sourceCount = useMemo(() => sources.length, [sources]);

  const loadSources = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSources();
      setSources(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSources();
  }, []);

  const handleSave = async () => {
    if (!name || !url) return;
    setSubmitting(true);
    setError(null);
    try {
      const inferred = inferSourceConfig(category, url, name);
      await createSource({
        name,
        category,
        collect_method: inferred.collect_method,
        config: inferred.config,
        enabled: true,
      });
      setIsModalOpen(false);
      setName("");
      setCategory("blog");
      setUrl("");
      await loadSources();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create source failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl relative px-4 sm:px-6 lg:px-8 py-8 md:py-12">
      <header className="mb-10 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2">信息源</h1>
          <p className="text-muted-foreground text-sm max-w-2xl">
            监控所有已配置的信息源并维护全局信息源池。
          </p>
          <p className="text-xs text-muted-foreground mt-2">总信息源数: {sourceCount}</p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 bg-foreground text-background shadow hover:bg-foreground/90 h-9 px-4 py-2 group"
        >
          <Plus className="w-4 h-4 mr-2 transition-transform group-hover:rotate-90 duration-300" />
          添加信息源
        </button>
      </header>

      <SourceStatusPanel sources={sources} loading={loading} error={error} onSourceClick={setSelectedSource} />

      {selectedSource && (
        <SourceDetailModal
          source={selectedSource}
          onClose={() => setSelectedSource(null)}
          onUpdated={() => {
            void loadSources();
          }}
        />
      )}

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={() => setIsModalOpen(false)} />
          <div className="relative bg-card border border-border rounded-xl shadow-lg w-full max-w-lg overflow-hidden z-50 animate-in fade-in zoom-in-95 duration-200">
            <div className="bg-card/95 backdrop-blur-sm border-b border-border/40 px-6 py-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold tracking-tight">添加信息源</h2>
              <button onClick={() => setIsModalOpen(false)} className="p-2 -mr-2 text-muted-foreground hover:bg-muted rounded-md transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              <div className="space-y-3">
                <label className="text-sm font-medium">信息源类型</label>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { id: "blog", label: "科技博客 / RSS", icon: Rss },
                    { id: "open_source", label: "开源项目", icon: Github },
                    { id: "academic", label: "学术论文", icon: BookOpen },
                    { id: "social", label: "社交媒体", icon: MessageSquare },
                  ].map((c) => {
                    const Icon = c.icon;
                    return (
                      <div
                        key={c.id}
                        onClick={() => setCategory(c.id as SourceCategory)}
                        className={cn(
                          "border rounded-lg p-3 cursor-pointer transition-all flex items-center space-x-3",
                          category === c.id ? "border-foreground bg-secondary/50" : "border-border hover:border-foreground/50"
                        )}
                      >
                        <Icon className={cn("w-4 h-4", category === c.id ? "text-foreground" : "text-muted-foreground")} />
                        <span className="font-medium text-sm">{c.label}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-3">
                <label className="text-sm font-medium">信息源名称</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="例如：OpenAI 官方博客"
                  className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                />
              </div>

              <div className="space-y-3">
                <label className="text-sm font-medium">目标 URL / ID</label>
                <div className="relative">
                  <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <input
                    type="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://example.com/blog"
                    className="flex h-10 w-full rounded-md border border-input bg-transparent pl-9 pr-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  系统会自动推断抓取策略（例如：RSS / 博客爬虫 / GitHub 趋势 / Hugging Face）。
                </p>
              </div>
            </div>

            <div className="bg-card border-t border-border/40 px-6 py-4 flex items-center justify-end space-x-3">
              <button
                onClick={() => setIsModalOpen(false)}
                className="px-4 py-2 text-sm font-medium hover:bg-muted rounded-md transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleSave}
                disabled={!name || !url || submitting}
                className="px-4 py-2 text-sm font-medium bg-foreground text-background hover:bg-foreground/90 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors shadow-sm"
              >
                {submitting ? "正在创建..." : "创建信息源"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
