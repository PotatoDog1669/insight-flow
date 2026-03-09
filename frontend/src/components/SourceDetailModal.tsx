"use client";

import { useState, useEffect } from "react";
import { Source, updateSource, testSource, SourceTestResponse } from "@/lib/api";
import { X, Globe, Play, Save, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface SourceDetailModalProps {
    source: Source;
    onClose: () => void;
    onUpdated: () => void;
}

type ConfigObject = Record<string, unknown>;

function asObject(value: unknown): ConfigObject | null {
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    return value as ConfigObject;
}

function asStringArray(value: unknown): string[] {
    if (!Array.isArray(value)) return [];
    return value.filter((item): item is string => typeof item === "string");
}

export function SourceDetailModal({ source, onClose, onUpdated }: SourceDetailModalProps) {
    const [url, setUrl] = useState("");
    const [twitterUsernames, setTwitterUsernames] = useState<string[]>([]);
    const [usernameDraft, setUsernameDraft] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [testing, setTesting] = useState(false);
    const [testResult, setTestResult] = useState<SourceTestResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    const canEditUrl = source.collect_method === "blog_scraper" || source.collect_method === "deepbrowse" || source.collect_method === "rss";
    const canEditTwitterUsers = source.collect_method === "twitter_snaplytics";

    useEffect(() => {
        // Extract url from config
        let initialUrl = "";
        const sourceConfig = asObject(source.config) ?? {};
        if (source.collect_method === "blog_scraper" || source.collect_method === "deepbrowse") {
            const profile = asObject(sourceConfig.profile);
            const startUrls = asStringArray(profile?.start_urls);
            if (Array.isArray(startUrls) && startUrls.length > 0) {
                initialUrl = startUrls[0];
            } else if (typeof sourceConfig.url === "string") {
                initialUrl = sourceConfig.url;
            }
        } else if (source.collect_method === "rss") {
            initialUrl = typeof sourceConfig.feed_url === "string" ? sourceConfig.feed_url : "";
        }
        if (source.collect_method === "twitter_snaplytics") {
            const usernames = asStringArray(sourceConfig.usernames);
            if (Array.isArray(usernames) && usernames.length > 0) {
                setTwitterUsernames(usernames.map(normalizeTwitterUsername).filter(Boolean));
            } else {
                setTwitterUsernames([]);
            }
            setUsernameDraft("");
        }
        setUrl(initialUrl);
    }, [source]);

    const handleSave = async () => {
        if (canEditUrl && !url) return;
        setSubmitting(true);
        setError(null);
        try {
            const currentConfig: ConfigObject = { ...(asObject(source.config) ?? {}) };

            if (source.collect_method === "blog_scraper" || source.collect_method === "deepbrowse") {
                const profile = asObject(currentConfig.profile) ?? {};
                profile.start_urls = [url];
                // update url_prefix heuristic
                try {
                    const origin = new URL(url).origin;
                    const normalization = asObject(profile.normalization) ?? {};
                    normalization.url_prefix = origin;
                    profile.normalization = normalization;
                } catch {
                    // ignore invalid url
                }
                currentConfig.profile = profile;
            } else if (source.collect_method === "rss") {
                currentConfig.feed_url = url;
            } else if (source.collect_method === "twitter_snaplytics") {
                currentConfig.usernames = twitterUsernames;
                delete currentConfig.username;
            }

            await updateSource(source.id, { config: currentConfig });
            onUpdated();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to update source");
        } finally {
            setSubmitting(false);
        }
    };

    const persistTwitterUsernames = async (nextUsernames: string[]): Promise<boolean> => {
        setSubmitting(true);
        setError(null);
        try {
            const currentConfig: ConfigObject = { ...(asObject(source.config) ?? {}) };
            currentConfig.usernames = nextUsernames;
            delete currentConfig.username;
            await updateSource(source.id, { config: currentConfig });
            setTwitterUsernames(nextUsernames);
            onUpdated();
            return true;
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to update source");
            return false;
        } finally {
            setSubmitting(false);
        }
    };

    const handleAddTwitterUsername = async () => {
        const normalized = normalizeTwitterUsername(usernameDraft);
        if (!normalized) return;
        const deduped = Array.from(new Set([...twitterUsernames, normalized]));
        if (deduped.length === twitterUsernames.length) {
            setUsernameDraft("");
            return;
        }
        const saved = await persistTwitterUsernames(deduped);
        if (saved) {
            setUsernameDraft("");
        }
    };

    const handleRemoveTwitterUsername = async (username: string) => {
        const nextUsernames = twitterUsernames.filter((item) => item !== username);
        await persistTwitterUsernames(nextUsernames);
    };

    const handleTest = async () => {
        setTesting(true);
        setTestResult(null);
        setError(null);
        try {
            // It uses the latest saved config, so if users want to test a new url, they should save first.
            const res = await testSource(source.id);
            setTestResult(res);
        } catch (err) {
            setTestResult({
                success: false,
                message: err instanceof Error ? err.message : "Server error",
                sample_articles: []
            });
        } finally {
            setTesting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={onClose} />
            <div className="relative bg-card border border-border rounded-xl shadow-lg w-full max-w-2xl max-h-[90vh] overflow-hidden z-50 flex flex-col animate-in fade-in zoom-in-95 duration-200">
                <div className="bg-card/95 backdrop-blur-sm border-b border-border/40 px-6 py-4 flex items-center justify-between shrink-0">
                    <div>
                        <h2 className="text-xl font-semibold tracking-tight">{source.name}</h2>
                        <p className="text-xs text-muted-foreground capitalize mt-0.5">{source.category.replace('_', ' ')} • {source.collect_method}</p>
                    </div>
                    <button onClick={onClose} className="p-2 -mr-2 text-muted-foreground hover:bg-muted rounded-md transition-colors">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="overflow-y-auto overflow-x-hidden flex-1 p-6 space-y-8 scrollbar-thin">
                    {error && (
                        <div className="bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-400 p-3 rounded-lg text-sm border border-red-200 dark:border-red-900/50">
                            {error}
                        </div>
                    )}

                    {canEditUrl && (
                        <div className="space-y-3">
                            <label className="text-sm font-medium flex items-center gap-2">
                                Target URL
                                {submitting && <span className="text-xs text-muted-foreground animate-pulse">Saving...</span>}
                            </label>
                            <div className="flex space-x-2">
                                <div className="relative flex-1">
                                    <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                    <input
                                        type="url"
                                        value={url}
                                        onChange={(e) => setUrl(e.target.value)}
                                        placeholder="https://example.com/feed"
                                        className="flex h-10 w-full rounded-md border border-input bg-transparent pl-9 pr-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                    />
                                </div>
                                <button
                                    onClick={handleSave}
                                    disabled={submitting || !url}
                                    className="flex shrink-0 h-10 items-center justify-center rounded-md bg-secondary text-secondary-foreground hover:bg-secondary/80 px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50"
                                >
                                    <Save className="w-4 h-4 mr-2" />
                                    Save
                                </button>
                            </div>
                            <p className="text-xs text-muted-foreground mt-1">
                                Note: You should save changes before testing if you modified the URL.
                            </p>
                        </div>
                    )}

                    {canEditTwitterUsers && (
                        <div className="space-y-3">
                            <label className="text-sm font-medium flex items-center gap-2">
                                Followed X Usernames
                                {submitting && <span className="text-xs text-muted-foreground animate-pulse">Saving...</span>}
                            </label>
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={usernameDraft}
                                    onChange={(e) => setUsernameDraft(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter") {
                                            e.preventDefault();
                                            void handleAddTwitterUsername();
                                        }
                                    }}
                                    placeholder="@OpenAI"
                                    className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                />
                                <button
                                    onClick={() => void handleAddTwitterUsername()}
                                    disabled={!normalizeTwitterUsername(usernameDraft) || submitting}
                                    className="flex shrink-0 h-10 items-center justify-center rounded-md border border-border/60 bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground transition-all hover:-translate-y-px hover:border-foreground/40 hover:bg-foreground hover:text-background hover:shadow-sm disabled:opacity-50"
                                >
                                    Add
                                </button>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {twitterUsernames.map((username) => (
                                    <div key={username} className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/40 px-3 py-1 text-xs">
                                        <span>@{username}</span>
                                        <button
                                            onClick={() => void handleRemoveTwitterUsername(username)}
                                            disabled={submitting}
                                            className="text-muted-foreground hover:text-foreground"
                                            aria-label={`Remove ${username}`}
                                        >
                                            <X className="w-3 h-3" />
                                        </button>
                                    </div>
                                ))}
                            </div>
                            <p className="text-xs text-muted-foreground">Current watchlist: {twitterUsernames.length}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                                Type `@xxx` then click Add. Changes are saved immediately. Empty list is allowed.
                            </p>
                        </div>
                    )}

                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <label className="text-sm font-medium">Connectivity Test</label>
                            <button
                                onClick={handleTest}
                                disabled={testing}
                                className="flex items-center justify-center rounded-md bg-foreground text-background hover:bg-foreground/90 px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
                            >
                                <Play className={cn("w-3.5 h-3.5 mr-1.5", testing && "animate-pulse")} />
                                {testing ? "Testing..." : "Run Test"}
                            </button>
                        </div>

                        {testing && (
                            <div className="h-32 rounded-lg border border-dashed border-border/60 bg-muted/20 flex items-center justify-center flex-col gap-2">
                                <div className="w-5 h-5 rounded-full border-2 border-foreground border-t-transparent animate-spin" />
                                <p className="text-sm text-muted-foreground">Running dry-run collector...</p>
                            </div>
                        )}

                        {!testing && testResult && (
                            <div className={cn("rounded-lg border p-4 space-y-4", testResult.success ? "border-green-200 dark:border-green-900/40 bg-green-50/50 dark:bg-green-900/10" : "border-red-200 dark:border-red-900/40 bg-red-50/50 dark:bg-red-900/10")}>
                                <div className="flex items-start gap-3">
                                    {testResult.success ? <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-500 shrink-0 mt-0.5" /> : <XCircle className="w-5 h-5 text-red-600 dark:text-red-500 shrink-0 mt-0.5" />}
                                    <div className="flex-1 min-w-0">
                                        <p className={cn("text-sm font-medium", testResult.success ? "text-green-800 dark:text-green-400" : "text-red-800 dark:text-red-400")}>
                                            {testResult.success ? "Test Passed" : "Test Failed"}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-1 break-words">{testResult.message}</p>
                                    </div>
                                </div>

                                {testResult.sample_articles.length > 0 && (
                                    <div className="space-y-2 mt-4 pt-4 border-t border-border/30">
                                        <p className="text-xs font-medium text-foreground">Sample Items Fetched:</p>
                                        <div className="space-y-2">
                                            {testResult.sample_articles.map((article, idx) => (
                                                <div key={idx} className="bg-background/80 rounded border border-border/50 p-2 text-xs">
                                                    <p className="font-medium truncate" title={article.title}>{article.title}</p>
                                                    {article.url && <p className="text-muted-foreground truncate mt-0.5">{article.url}</p>}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

function normalizeTwitterUsername(value: string): string {
    const raw = value.trim();
    if (!raw) return "";
    let normalized = raw.startsWith("@") ? raw.slice(1) : raw;
    if (normalized.startsWith("https://") || normalized.startsWith("http://")) {
        try {
            const parsed = new URL(normalized);
            normalized = parsed.pathname.replace(/^\/+|\/+$/g, "").split("/")[0] || "";
        } catch {
            return "";
        }
    }
    normalized = normalized.trim();
    if (!normalized || /[\s/]/.test(normalized)) return "";
    return normalized;
}
