"use client";

import { useMemo, useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { type Source } from "@/lib/api";
import { SiOpenai, SiGithub, SiHuggingface, SiX, SiAnthropic, SiArxiv } from "react-icons/si";
import { Globe } from "lucide-react";

interface SourceStatusPanelProps {
  sources: Source[];
  loading?: boolean;
  error?: string | null;
}

const getSourceIcon = (name: string) => {
  const n = name.toLowerCase();
  if (n.includes("openai")) return <SiOpenai className="w-5 h-5 text-foreground" />;
  if (n.includes("anthropic")) return <SiAnthropic className="w-5 h-5 text-orange-600 dark:text-orange-400" />;
  if (n.includes("github")) return <SiGithub className="w-5 h-5 text-foreground" />;
  if (n.includes("huggingface")) return <SiHuggingface className="w-5 h-5 text-yellow-500" />;
  if (n.includes("twitter") || n.includes("x ") || n.includes("xai")) return <SiX className="w-4 h-4 text-foreground" />;
  if (n.includes("arxiv")) return <SiArxiv className="w-5 h-5 text-red-600 dark:text-red-400" />;
  return <Globe className="w-5 h-5 text-muted-foreground" />;
};

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

export function SourceStatusPanel({ sources, loading = false, error = null }: SourceStatusPanelProps) {
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]["id"]>("all");

  const filteredSources = useMemo(() => {
    return sources.filter((source) => activeTab === "all" || source.category === activeTab);
  }, [sources, activeTab]);

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
              {tab.id === "all" ? sources.length : sources.filter((s) => s.category === tab.id).length}
            </span>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredSources.map((source) => (
          <Card key={source.id} className="border-border/40 hover:border-border/80 transition-all duration-300 shadow-sm hover:shadow-lg flex flex-col relative group overflow-hidden transform-gpu hover:-translate-y-1">
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
            <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-indigo-500/0 via-indigo-500/40 to-indigo-500/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

            <CardHeader className="pb-3 flex flex-row items-start justify-between relative z-10 bg-background/20">
              <div className="space-y-4 flex-1 pr-4">
                <CardTitle className="text-base font-semibold leading-snug flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-background/50 border border-border/50 shadow-sm flex items-center justify-center shrink-0">
                    {getSourceIcon(source.name)}
                  </div>
                  <span className="truncate">{source.name}</span>
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
            </CardContent>
          </Card>
        ))}
      </div>

      {filteredSources.length === 0 && (
        <div className="text-center py-20 bg-muted/10 rounded-xl border border-dashed border-border/50">
          <p className="text-muted-foreground">No sources found for this category.</p>
        </div>
      )}
    </div>
  );
}
