"use client";

import { useMemo, useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { type Source } from "@/lib/api";
import { SiOpenai, SiGithub, SiHuggingface, SiX, SiAnthropic, SiArxiv, SiBytedance, SiXiaohongshu, SiReddit } from "react-icons/si";
import { Globe, Building2, Code2, Cpu, AppWindow } from "lucide-react";
import { BilibiliIcon, NotionIcon, ZhihuIcon, MicrosoftIcon, DockerIcon } from "./BrandIcons";

interface SourceStatusPanelProps {
  sources: Source[];
  loading?: boolean;
  error?: string | null;
  onSourceClick?: (source: Source) => void;
}

function asObject(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function asString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function getTwitterUsernames(source: Source): string[] {
  const config = asObject(source.config) ?? {};
  const usernames = asStringArray(config.usernames);
  if (usernames.length > 0) {
    return usernames;
  }
  const single = typeof config.username === "string" ? config.username.trim() : "";
  return single ? [single] : [];
}

function formatTwitterAccountsPreview(source: Source): string {
  const usernames = getTwitterUsernames(source).map((item) => (item.startsWith("@") ? item : `@${item}`));
  if (usernames.length === 0) return "";
  const visible = usernames.slice(0, 3);
  const suffix = usernames.length > 3 ? ", ..." : "";
  return `${visible.join(", ")}${suffix}`;
}

const BRAND_DOMAIN_OVERRIDES: Array<{ patterns: string[]; domain: string }> = [
  { patterns: ["openai", "chatgpt"], domain: "openai.com" },
  { patterns: ["google deepmind", "deepmind"], domain: "deepmind.google" },
  { patterns: ["anthropic", "claude"], domain: "anthropic.com" },
  { patterns: ["xai", "x.ai"], domain: "x.ai" },
  { patterns: ["meta ai", "meta"], domain: "ai.meta.com" },
  { patterns: ["microsoft"], domain: "microsoft.com" },
  { patterns: ["nvidia"], domain: "nvidia.com" },
  { patterns: ["apple"], domain: "apple.com" },
  { patterns: ["amazon"], domain: "amazon.science" },
  { patterns: ["mistral"], domain: "mistral.ai" },
  { patterns: ["cohere"], domain: "cohere.com" },
  { patterns: ["ai21"], domain: "ai21.com" },
  { patterns: ["stability"], domain: "stability.ai" },
  { patterns: ["qwen"], domain: "qwen.ai" },
  { patterns: ["hunyuan", "腾讯"], domain: "tencent.com" },
  { patterns: ["bytedance", "字节"], domain: "bytedance.com" },
  { patterns: ["美团", "longcat"], domain: "meituan.com" },
  { patterns: ["kuaikat", "快手", "kwai"], domain: "kuaishou.com" },
  { patterns: ["xiaomi", "小米"], domain: "mi.com" },
  { patterns: ["小红书", "xiaohongshu"], domain: "xiaohongshu.com" },
  { patterns: ["baidu", "ernie", "百度"], domain: "baidu.com" },
  { patterns: ["huawei", "华为", "盘古"], domain: "huawei.com" },
  { patterns: ["sensenova", "sensetime", "商汤"], domain: "sensetime.com" },
  { patterns: ["讯飞", "xfyun", "星火"], domain: "xfyun.cn" },
  { patterns: ["deepseek"], domain: "deepseek.com" },
  { patterns: ["z.ai", "zhipu", "智谱"], domain: "z.ai" },
  { patterns: ["moonshot", "kimi"], domain: "moonshot.cn" },
  { patterns: ["minimax"], domain: "minimax.io" },
  { patterns: ["stepfun", "阶跃"], domain: "stepfun.com" },
  { patterns: ["baichuan", "百川"], domain: "baichuan-ai.com" },
  { patterns: ["01.ai", "零一万物", "lingyi"], domain: "01.ai" },
  { patterns: ["minicpm", "openbmb", "面壁"], domain: "modelbest.cn" },
  { patterns: ["perplexity"], domain: "perplexity.ai" },
  { patterns: ["nous"], domain: "nousresearch.com" },
  { patterns: ["cursor"], domain: "cursor.com" },
  { patterns: ["cognition", "devin"], domain: "cognition.ai" },
  { patterns: ["huggingface", "hugging face"], domain: "huggingface.co" },
  { patterns: ["together"], domain: "together.ai" },
  { patterns: ["fireworks"], domain: "fireworks.ai" },
  { patterns: ["groq"], domain: "groq.com" },
  { patterns: ["arxiv"], domain: "arxiv.org" },
];

function inferBrandDomain(name: string): string | null {
  const normalized = name.trim().toLowerCase();
  if (!normalized) return null;
  if (normalized === "x" || normalized.includes("twitter")) return "x.com";
  if (normalized.includes("reddit")) return "reddit.com";
  for (const rule of BRAND_DOMAIN_OVERRIDES) {
    if (rule.patterns.some((pattern) => normalized.includes(pattern))) {
      return rule.domain;
    }
  }
  return null;
}

function parseHostname(rawUrl: string): string | null {
  const normalized = rawUrl.startsWith("http://") || rawUrl.startsWith("https://") ? rawUrl : `https://${rawUrl}`;
  try {
    const { hostname } = new URL(normalized);
    if (!hostname) return null;
    return hostname.replace(/^www\./, "").toLowerCase();
  } catch {
    return null;
  }
}

function getConfigUrlCandidates(source: Source): string[] {
  const config = asObject(source.config) ?? {};
  const candidates: string[] = [];
  const push = (value: unknown): void => {
    const raw = asString(value);
    if (raw) candidates.push(raw);
  };
  const pushArray = (value: unknown): void => {
    if (!Array.isArray(value)) return;
    for (const item of value) {
      push(item);
    }
  };

  push(config.feed_url);
  push(config.url);
  pushArray(config.urls);
  pushArray(config.start_urls);
  pushArray(config.github_repo_urls);

  const profile = asObject(config.profile);
  if (profile) {
    pushArray(profile.start_urls);
  }

  if (source.collect_method === "twitter_snaplytics") {
    push("https://x.com");
  }
  if (source.collect_method === "huggingface") {
    push("https://huggingface.co");
  }
  if (source.collect_method === "github_trending") {
    push("https://github.com");
  }

  return candidates;
}

function getSourceLogoUrl(source: Source): string | null {
  const brandDomain = inferBrandDomain(source.name);
  if (brandDomain) {
    return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(brandDomain)}&sz=64`;
  }
  for (const candidate of getConfigUrlCandidates(source)) {
    const hostname = parseHostname(candidate);
    if (!hostname) continue;
    return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(hostname)}&sz=64`;
  }
  return null;
}

function getPinnedBrandIcon(name: string) {
  const n = name.toLowerCase();
  if (n.includes("bytedance") || n.includes("字节")) {
    return <SiBytedance role="img" aria-label={`${name} logo`} className="w-5 h-5 text-[#1B6DFF]" />;
  }
  if (n.includes("xiaohongshu") || n.includes("小红书")) {
    return <SiXiaohongshu role="img" aria-label={`${name} logo`} className="w-5 h-5 text-[#FF2442]" />;
  }
  return null;
}

const getSourceIconFallback = (name: string, category: string) => {
  const pinnedIcon = getPinnedBrandIcon(name);
  if (pinnedIcon) return pinnedIcon;

  const n = name.toLowerCase();

  // Specific brand matches
  if (n.includes("openai") || n.includes("chatgpt")) return <SiOpenai className="w-5 h-5 text-foreground" />;
  if (n.includes("anthropic") || n.includes("claude")) return <SiAnthropic className="w-5 h-5 text-orange-600 dark:text-orange-400" />;
  if (n.includes("github")) return <SiGithub className="w-5 h-5 text-foreground" />;
  if (n.includes("huggingface") || n.includes("hugging")) return <SiHuggingface className="w-5 h-5 text-yellow-500" />;
  if (n === "x" || n.includes("twitter") || n.includes("x ") || n.includes("xai")) return <SiX className="w-4 h-4 text-foreground" />;
  if (n.includes("reddit")) return <SiReddit className="w-5 h-5 text-[#FF4500]" />;
  if (n.includes("arxiv")) return <SiArxiv className="w-5 h-5 text-red-600 dark:text-red-400" />;
  if (n.includes("bilibili") || n.includes("b站")) return <BilibiliIcon className="w-5 h-5 text-[#00AEEC]" />;
  if (n.includes("notion")) return <NotionIcon className="w-5 h-5 text-foreground" />;
  if (n.includes("zhihu") || n.includes("知乎")) return <ZhihuIcon className="w-5 h-5 text-[#0066FF]" />;
  if (n.includes("microsoft") || n.includes("微软")) return <MicrosoftIcon className="w-5 h-5 text-[#00A4EF]" />;
  if (n.includes("docker")) return <DockerIcon className="w-5 h-5 text-[#2496ED]" />;
  if (n.includes("google")) return <Globe className="w-5 h-5 text-[#4285F4]" />;
  if (n.includes("meta")) return <Globe className="w-5 h-5 text-[#0668E1]" />;
  if (n.includes("apple") || n.includes("苹果")) return <Globe className="w-5 h-5 text-foreground" />;

  // Fallbacks based on category if no specific brand matched
  if (category === "open_source") return <Code2 className="w-5 h-5 text-purple-500" />;
  if (category === "academic") return <SiArxiv className="w-5 h-5 text-emerald-500" />;

  // By organization rules
  if (n.includes("deepseek") || n.includes("零一万物") || n.includes("智谱") || n.includes("moonshot") || n.includes("kimi") || n.includes("mistral") || n.includes("cohere")) return <Cpu className="w-5 h-5 text-indigo-500" />;
  if (n.includes("华为") || n.includes("腾讯") || n.includes("字节") || n.includes("阿里") || n.includes("小米") || n.includes("快手") || n.includes("amazon") || n.includes("百度") || n.includes("美团")) return <Building2 className="w-5 h-5 text-blue-500" />;
  if (n.includes("cursor") || n.includes("langchain") || n.includes("vercel") || n.includes("cloudflare") || n.includes("vllm") || n.includes("llamaindex")) return <Code2 className="w-5 h-5 text-orange-500" />;
  if (n.includes("midjourney") || n.includes("runway") || n.includes("perplexity") || n.includes("cognition") || n.includes("devin")) return <AppWindow className="w-5 h-5 text-pink-500" />;

  return <Globe className="w-5 h-5 text-muted-foreground" />;
};

function SourceLogo({ source }: { source: Source }) {
  const [failedLogoUrl, setFailedLogoUrl] = useState<string | null>(null);
  const logoUrl = useMemo(() => getSourceLogoUrl(source), [source]);
  const pinnedIcon = getPinnedBrandIcon(source.name);
  if (pinnedIcon) return pinnedIcon;

  if (source.category === "blog" && logoUrl && failedLogoUrl !== logoUrl) {
    const currentLogoUrl = logoUrl;
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={currentLogoUrl}
        alt={`${source.name} logo`}
        className="w-5 h-5 rounded-sm object-contain"
        loading="lazy"
        decoding="async"
        referrerPolicy="no-referrer"
        onError={() => setFailedLogoUrl(currentLogoUrl)}
      />
    );
  }

  return getSourceIconFallback(source.name, source.category);
}

const categoryColors: Record<string, string> = {
  blog: "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400",
  open_source: "bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-400",
  academic: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400",
  social: "bg-orange-50 text-orange-700 dark:bg-orange-950/40 dark:text-orange-400",
};

const statusDot: Record<Source["status"], string> = {
  healthy: "bg-green-500",
  error: "bg-red-500",
  running: "bg-blue-500 animate-pulse",
};

const TABS = [
  { id: "all", label: "All Sources" },
  { id: "blog", label: "Tech Blogs" },
  { id: "open_source", label: "Open Source" },
  { id: "academic", label: "Academic" },
  { id: "social", label: "Social Media" },
] as const;

function formatLastRun(lastRun: string | null): string {
  if (!lastRun) return "Never";
  const date = new Date(lastRun);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleString();
}

export function SourceStatusPanel({ sources, loading = false, error = null, onSourceClick }: SourceStatusPanelProps) {
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]["id"]>("all");
  const socialSources = useMemo(
    () =>
      sources
        .filter((source) => source.category === "social" || source.collect_method === "twitter_snaplytics")
        .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at)),
    [sources]
  );

  const getTabCount = (tabId: (typeof TABS)[number]["id"]): number => {
    if (tabId === "all") return sources.length;
    if (tabId === "social") return socialSources.length;
    return sources.filter((source) => source.category === tabId).length;
  };

  const filteredSources = useMemo(() => {
    if (activeTab === "all") {
      return sources;
    }
    if (activeTab === "social") {
      return socialSources;
    }
    return sources.filter((source) => source.category === activeTab);
  }, [sources, activeTab, socialSources]);

  if (loading) {
    return <div className="py-10 text-sm text-muted-foreground">Loading sources...</div>;
  }

  if (error) {
    return <div className="py-10 text-sm text-red-500">Failed to load sources: {error}</div>;
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center space-x-2 overflow-x-auto pb-2 scrollbar-none">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "px-4 py-2 rounded-full text-sm font-medium transition-colors whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-ring",
              activeTab === tab.id
                ? "bg-foreground text-background shadow-sm"
                : "bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            {tab.label}
            <span className="ml-2 text-xs opacity-60">
              {getTabCount(tab.id)}
            </span>
          </button>
        ))}
      </div>
      {filteredSources.length > 0 && activeTab === "blog" ? (
        <>
          {(["Top AI Labs & Startups", "Tech Giants", "AI Infra & Tools", "AI Applications & Products", "Other"] as const).map(group => {
            const getOrganizationCategory = (name: string) => {
              const n = name.toLowerCase();
              if (n.includes("openai") || n.includes("deepseek") || n.includes("anthropic") || n.includes("零一万物") || n.includes("01.ai") || n.includes("智谱") || n.includes("z.ai") || n.includes("moonshot") || n.includes("kimi") || n.includes("xai") || n.includes("mistral") || n.includes("cohere") || n.includes("minimax") || n.includes("阶跃") || n.includes("stepfun") || n.includes("百川") || n.includes("面壁") || n.includes("minicpm") || n.includes("nous") || n.includes("科大讯飞") || n.includes("星火") || n.includes("商汤") || n.includes("sensenova") || n.includes("ai21") || n.includes("stability")) return "Top AI Labs & Startups";
              if (n.includes("google") || n.includes("meta") || n.includes("microsoft") || n.includes("apple") || n.includes("华为") || n.includes("盘古") || n.includes("腾讯") || n.includes("hunyuan") || n.includes("字节") || n.includes("bytedance") || n.includes("seed") || n.includes("阿里") || n.includes("qwen") || n.includes("alibaba") || n.includes("小米") || n.includes("mimo") || n.includes("快手") || n.includes("kwaikat") || n.includes("amazon") || n.includes("aws") || n.includes("美团") || n.includes("longcat") || n.includes("百度") || n.includes("ernie")) return "Tech Giants";
              if (n.includes("nvidia") || n.includes("hugging") || n.includes("cursor") || n.includes("langchain") || n.includes("vercel") || n.includes("supabase") || n.includes("cloudflare") || n.includes("docker") || n.includes("github") || n.includes("gitlab") || n.includes("vllm") || n.includes("llamaindex") || n.includes("fireworks") || n.includes("groq") || n.includes("together")) return "AI Infra & Tools";
              if (n.includes("midjourney") || n.includes("runway") || n.includes("perplexity") || n.includes("notion") || n.includes("小红书") || n.includes("bilibili") || n.includes("知乎") || n.includes("cognition") || n.includes("devin")) return "AI Applications & Products";
              return "Other";
            };

            const groupSources = filteredSources.filter(s => getOrganizationCategory(s.name) === group);
            if (groupSources.length === 0) return null;

            return (
              <div key={group} className="space-y-4">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-medium text-muted-foreground">{group}</h3>
                  <div className="h-px bg-border flex-1" />
                  <span className="text-xs text-muted-foreground">{groupSources.length}</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {groupSources.map((source) => (
                    <Card key={source.id} onClick={() => onSourceClick?.(source)} className={cn("border-border/40 hover:border-border/80 transition-all duration-300 shadow-sm hover:shadow-lg flex flex-col relative group overflow-hidden transform-gpu hover:-translate-y-1", onSourceClick && "cursor-pointer")}>
                      <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
                      <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-indigo-500/0 via-indigo-500/40 to-indigo-500/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

                      <CardHeader className="pb-3 flex flex-row items-start justify-between relative z-10 bg-background/20">
                        <div className="space-y-4 flex-1 min-w-0 pr-4">
                          <CardTitle className="text-base font-semibold leading-snug flex items-center gap-2.5 min-w-0">
                            <div className="w-8 h-8 rounded-lg bg-background/50 border border-border/50 shadow-sm flex items-center justify-center shrink-0">
                              <SourceLogo source={source} />
                            </div>
                            <span className="truncate min-w-0">{source.name}</span>
                          </CardTitle>
                          <div className="flex items-center space-x-2">
                            <Badge variant="secondary" className={`font-medium ${categoryColors[source.category] ?? "bg-muted text-muted-foreground"}`}>
                              {source.category.replace("_", " ")}
                            </Badge>
                          </div>
                        </div>

                        <div className="flex items-center space-x-1.5 text-xs text-muted-foreground bg-muted/50 px-2 py-1 rounded-md shrink-0">
                          <span className={`w-2 h-2 rounded-full ${statusDot[source.status]}`}></span>
                          <span className="capitalize">{source.status}</span>
                        </div>
                      </CardHeader>

                      <CardContent className="pb-4 flex-1 relative z-10 bg-background/20">
                        <p className="text-sm text-muted-foreground">Last run: {formatLastRun(source.last_run)}</p>
                        {(source.collect_method === "twitter_snaplytics" || source.category === "social") && (
                          <p className="text-xs text-muted-foreground mt-2 truncate" title={formatTwitterAccountsPreview(source)}>
                            Accounts: {formatTwitterAccountsPreview(source) || "None"}
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            );
          })}
        </>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredSources.map((source) => (
            <Card key={source.id} onClick={() => onSourceClick?.(source)} className={cn("border-border/40 hover:border-border/80 transition-all duration-300 shadow-sm hover:shadow-lg flex flex-col relative group overflow-hidden transform-gpu hover:-translate-y-1", onSourceClick && "cursor-pointer")}>
              <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
              <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-indigo-500/0 via-indigo-500/40 to-indigo-500/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

              <CardHeader className="pb-3 flex flex-row items-start justify-between relative z-10 bg-background/20">
                <div className="space-y-4 flex-1 min-w-0 pr-4">
                  <CardTitle className="text-base font-semibold leading-snug flex items-center gap-2.5 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-background/50 border border-border/50 shadow-sm flex items-center justify-center shrink-0">
                      <SourceLogo source={source} />
                    </div>
                    <span className="truncate min-w-0">{source.name}</span>
                  </CardTitle>
                  <div className="flex items-center space-x-2">
                    <Badge variant="secondary" className={`font-medium ${categoryColors[source.category] ?? "bg-muted text-muted-foreground"}`}>
                      {source.category.replace("_", " ")}
                    </Badge>
                  </div>
                </div>

                <div className="flex items-center space-x-1.5 text-xs text-muted-foreground bg-muted/50 px-2 py-1 rounded-md shrink-0">
                  <span className={`w-2 h-2 rounded-full ${statusDot[source.status]}`}></span>
                  <span className="capitalize">{source.status}</span>
                </div>
              </CardHeader>

              <CardContent className="pb-4 flex-1 relative z-10 bg-background/20">
                <p className="text-sm text-muted-foreground">Last run: {formatLastRun(source.last_run)}</p>
                {(source.collect_method === "twitter_snaplytics" || source.category === "social") && (
                  <p className="text-xs text-muted-foreground mt-2 truncate" title={formatTwitterAccountsPreview(source)}>
                    Accounts: {formatTwitterAccountsPreview(source) || "None"}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {filteredSources.length === 0 && (
        <div className="text-center py-20 bg-muted/10 rounded-xl border border-dashed border-border/50">
          <p className="text-muted-foreground">No sources found for this category.</p>
        </div>
      )}
    </div>
  );
}
