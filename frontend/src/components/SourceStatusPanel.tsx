"use client";

import { useMemo, useState } from "react";

import type { Source } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { getLogoFrameClassName, SourceLogo } from "@/components/source-brand-registry";
import { BLOG_GROUPS, getOrganizationCategory } from "@/components/source-grouping";

interface SourceStatusPanelProps {
  sources: Source[];
  loading?: boolean;
  error?: string | null;
  onSourceClick?: (source: Source) => void;
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

function asObject(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
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

function formatLastRun(lastRun: string | null): string {
  if (!lastRun) return "Never";
  const date = new Date(lastRun);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleString();
}

function SourceCard({
  source,
  onSourceClick,
}: {
  source: Source;
  onSourceClick?: (source: Source) => void;
}) {
  return (
    <Card
      onClick={() => onSourceClick?.(source)}
      className={cn(
        "border-border/40 hover:border-border/80 transition-all duration-300 shadow-sm hover:shadow-lg flex flex-col relative group overflow-hidden transform-gpu hover:-translate-y-1",
        onSourceClick && "cursor-pointer"
      )}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
      <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-indigo-500/0 via-indigo-500/40 to-indigo-500/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

      <CardHeader className="pb-3 flex flex-row items-start justify-between relative z-10 bg-background/20">
        <div className="space-y-4 flex-1 min-w-0 pr-4">
          <CardTitle className="text-base font-semibold leading-snug flex items-center gap-2.5 min-w-0">
            <div className={getLogoFrameClassName(source)}>
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
  );
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
            <span className="ml-2 text-xs opacity-60">{getTabCount(tab.id)}</span>
          </button>
        ))}
      </div>

      {filteredSources.length > 0 && activeTab === "blog" ? (
        <>
          {BLOG_GROUPS.map((group) => {
            const groupSources = filteredSources.filter((source) => getOrganizationCategory(source.name) === group);
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
                    <SourceCard key={source.id} source={source} onSourceClick={onSourceClick} />
                  ))}
                </div>
              </div>
            );
          })}
        </>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredSources.map((source) => (
            <SourceCard key={source.id} source={source} onSourceClick={onSourceClick} />
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
