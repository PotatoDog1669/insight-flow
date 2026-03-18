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
    const [testKeywords, setTestKeywords] = useState("");
    const [testMaxResults, setTestMaxResults] = useState("30");
    const [testStartDate, setTestStartDate] = useState("");
    const [testEndDate, setTestEndDate] = useState("");
    const [testValidationError, setTestValidationError] = useState<string | null>(null);

    const canEditUrl = source.collect_method === "blog_scraper" || source.collect_method === "deepbrowse" || source.collect_method === "rss";
    const canEditTwitterUsers = source.collect_method === "twitter_snaplytics";
    const isArxivTestSource = isArxivSource(source);

    useEffect(() => {
        // Extract url from config
        let initialUrl = source.target_url ?? "";
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
            initialUrl = typeof sourceConfig.feed_url === "string" ? sourceConfig.feed_url : initialUrl;
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
        if (isArxivSource(source)) {
            setTestKeywords(asStringArray(sourceConfig.keywords).join(", "));
            setTestMaxResults(resolveInitialArxivMaxResults(sourceConfig));
        } else {
            setTestKeywords("");
            setTestMaxResults("30");
        }
        setTestStartDate("");
        setTestEndDate("");
        setTestValidationError(null);
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
        const testPayload = isArxivTestSource ? buildArxivTestPayload({
            keywordsValue: testKeywords,
            maxResultsValue: testMaxResults,
            startDate: testStartDate,
            endDate: testEndDate,
        }) : null;
        if (isArxivTestSource && !testPayload.success) {
            setTestValidationError(testPayload.message);
            return;
        }
        setTesting(true);
        setTestResult(null);
        setError(null);
        setTestValidationError(null);
        try {
            // URL edits still require save first, but arXiv test params are request-local only.
            const res = await testSource(source.id, testPayload?.payload);
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
                            <label className="text-sm font-medium">{isArxivTestSource ? "arXiv Test" : "Connectivity Test"}</label>
                            <button
                                onClick={handleTest}
                                disabled={testing}
                                className="flex items-center justify-center rounded-md bg-foreground text-background hover:bg-foreground/90 px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
                            >
                                <Play className={cn("w-3.5 h-3.5 mr-1.5", testing && "animate-pulse")} />
                                {testing ? "Testing..." : "Run Test"}
                            </button>
                        </div>

                        {isArxivTestSource && (
                            <div className="space-y-4 rounded-lg border border-border/50 bg-muted/20 p-4">
                                <div className="space-y-2">
                                    <label htmlFor="arxiv-test-keywords" className="text-xs font-medium text-muted-foreground">
                                        Keywords
                                    </label>
                                    <input
                                        id="arxiv-test-keywords"
                                        aria-label="Keywords for arXiv test"
                                        type="text"
                                        value={testKeywords}
                                        onChange={(e) => setTestKeywords(e.target.value)}
                                        placeholder="reasoning, agent, multimodal"
                                        className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                    />
                                    <p className="text-[11px] text-muted-foreground">
                                        Test-only keywords. Leave empty to reuse saved source keywords.
                                    </p>
                                </div>

                                <div className="space-y-2">
                                    <label htmlFor="arxiv-test-max-results" className="text-xs font-medium text-muted-foreground">
                                        Max Results
                                    </label>
                                    <input
                                        id="arxiv-test-max-results"
                                        aria-label="Max results for arXiv test"
                                        type="number"
                                        min={1}
                                        max={200}
                                        value={testMaxResults}
                                        onChange={(e) => setTestMaxResults(e.target.value)}
                                        className="flex h-10 w-40 rounded-md border border-input bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                    />
                                    <p className="text-[11px] text-muted-foreground">
                                        Test-only fetch cap. Uses the saved source limit when available.
                                    </p>
                                </div>

                                <div className="space-y-2">
                                    <span className="text-xs font-medium text-muted-foreground">Quick Ranges</span>
                                    <div className="flex flex-wrap gap-2">
                                        {[
                                            { label: "Last 24 Hours", amount: 1, unit: "hours" as const },
                                            { label: "Last 7 Days", amount: 7, unit: "days" as const },
                                            { label: "Last 15 Days", amount: 15, unit: "days" as const },
                                            { label: "Last 30 Days", amount: 30, unit: "days" as const },
                                        ].map((preset) => (
                                            <button
                                                key={preset.label}
                                                type="button"
                                                onClick={() => {
                                                    const range = buildPresetRange(preset.amount, preset.unit);
                                                    setTestStartDate(range.startDate);
                                                    setTestEndDate(range.endDate);
                                                    setTestValidationError(null);
                                                }}
                                                className="rounded-md border border-border/60 px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-background hover:text-foreground"
                                            >
                                                {preset.label}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div className="grid gap-3 sm:grid-cols-2">
                                    <div className="space-y-2">
                                        <label htmlFor="arxiv-test-start-date" className="text-xs font-medium text-muted-foreground">
                                            Start Date
                                        </label>
                                        <input
                                            id="arxiv-test-start-date"
                                            aria-label="Start date for arXiv test"
                                            type="date"
                                            value={testStartDate}
                                            onChange={(e) => setTestStartDate(e.target.value)}
                                            className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label htmlFor="arxiv-test-end-date" className="text-xs font-medium text-muted-foreground">
                                            End Date
                                        </label>
                                        <input
                                            id="arxiv-test-end-date"
                                            aria-label="End date for arXiv test"
                                            type="date"
                                            value={testEndDate}
                                            onChange={(e) => setTestEndDate(e.target.value)}
                                            className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                        />
                                    </div>
                                </div>
                                <p className="text-[11px] text-muted-foreground">
                                    Date-only ranges use the full local day: start at 00:00 and end at 23:59.
                                </p>

                                {testValidationError && (
                                    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-400">
                                        {testValidationError}
                                    </div>
                                )}
                            </div>
                        )}

                        {testing && (
                            <div className="h-32 rounded-lg border border-dashed border-border/60 bg-muted/20 flex items-center justify-center flex-col gap-2">
                                <div className="w-5 h-5 rounded-full border-2 border-foreground border-t-transparent animate-spin" />
                                <p className="text-sm text-muted-foreground">
                                    {isArxivTestSource ? "Running arXiv retrieval test..." : "Running dry-run collector..."}
                                </p>
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

                                {isArxivTestSource && testResult.success && (
                                    <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                                        <p>Fetched: {testResult.fetched_count ?? 0}</p>
                                        <p>Matched: {testResult.matched_count ?? 0}</p>
                                        <p className="sm:col-span-2">
                                            Keywords: {(testResult.effective_keywords ?? []).join(", ") || "Saved source defaults"}
                                        </p>
                                        <p className="sm:col-span-2">
                                            Max results: {testResult.effective_max_results ?? "Default"}
                                        </p>
                                        <p className="sm:col-span-2">
                                            Window: {formatWindowRange(testResult.window_start, testResult.window_end)}
                                        </p>
                                    </div>
                                )}

                                {testResult.sample_articles.length > 0 && (
                                    <div className="space-y-2 mt-4 pt-4 border-t border-border/30">
                                        <p className="text-xs font-medium text-foreground">
                                            {isArxivTestSource ? "Matched Sample Articles:" : "Sample Items Fetched:"}
                                        </p>
                                        <div className="space-y-2">
                                            {testResult.sample_articles.map((article, idx) => (
                                                <div key={idx} className="bg-background/80 rounded border border-border/50 p-2 text-xs">
                                                    <p className="font-medium whitespace-normal break-words" title={article.title}>{article.title}</p>
                                                    {article.url && <p className="text-muted-foreground whitespace-normal break-all mt-0.5">{article.url}</p>}
                                                    {article.published_at && <p className="text-muted-foreground mt-1">Published: {article.published_at}</p>}
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

function isArxivSource(source: Source): boolean {
    const sourceConfig = asObject(source.config) ?? {};
    return source.category === "academic" && source.collect_method === "rss" && Boolean(sourceConfig.arxiv_api);
}

function buildPresetRange(amount: number, unit: "hours" | "days"): {
    startDate: string;
    endDate: string;
} {
    const end = new Date();
    const start = new Date(end.getTime());
    if (unit === "hours") {
        start.setHours(start.getHours() - amount);
    } else {
        start.setDate(start.getDate() - amount);
    }
    return {
        startDate: formatDateInput(start),
        endDate: formatDateInput(end),
    };
}

function buildArxivTestPayload({
    keywordsValue,
    maxResultsValue,
    startDate,
    endDate,
}: {
    keywordsValue: string;
    maxResultsValue: string;
    startDate: string;
    endDate: string;
}): { success: true; payload: { keywords?: string[]; start_at?: string; end_at?: string } } | { success: false; message: string } {
    if ((startDate && !endDate) || (!startDate && endDate)) {
        return { success: false, message: "Please provide both start and end dates." };
    }

    const startAt = startDate ? toLocalIso(startDate, true) : undefined;
    const endAt = endDate ? toLocalIso(endDate, false) : undefined;
    if (startAt && endAt && new Date(startAt).getTime() > new Date(endAt).getTime()) {
        return { success: false, message: "Start date must be on or before end date." };
    }

    const keywords = keywordsValue
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
    const payload: { keywords?: string[]; max_results?: number; start_at?: string; end_at?: string } = {};
    const normalizedMaxResults = normalizeMaxResults(maxResultsValue);
    if (normalizedMaxResults === null) {
        return { success: false, message: "Max results must be between 1 and 200." };
    }
    if (keywords.length > 0) {
        payload.keywords = Array.from(new Set(keywords)).slice(0, 20);
    }
    payload.max_results = normalizedMaxResults;
    if (startAt) {
        payload.start_at = startAt;
    }
    if (endAt) {
        payload.end_at = endAt;
    }
    return { success: true, payload };
}

function toLocalIso(dateValue: string, isStartOfDay: boolean): string {
    const [year, month, day] = dateValue.split("-").map(Number);
    const date = isStartOfDay
        ? new Date(year, (month || 1) - 1, day || 1, 0, 0, 0, 0)
        : new Date(year, (month || 1) - 1, day || 1, 23, 59, 59, 999);
    return date.toISOString();
}

function formatDateInput(value: Date): string {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function formatWindowRange(start: string | null | undefined, end: string | null | undefined): string {
    if (!start && !end) return "No time window";
    return `${start ?? "Unbounded"} -> ${end ?? "Unbounded"}`;
}

function resolveInitialArxivMaxResults(sourceConfig: ConfigObject): string {
    const candidates = [sourceConfig.max_results, sourceConfig.max_items];
    for (const candidate of candidates) {
        if (typeof candidate === "number" && Number.isFinite(candidate) && candidate >= 1 && candidate <= 200) {
            return String(Math.floor(candidate));
        }
        if (typeof candidate === "string") {
            const normalized = normalizeMaxResults(candidate);
            if (normalized !== null) {
                return String(normalized);
            }
        }
    }
    return "30";
}

function normalizeMaxResults(value: string): number | null {
    const raw = value.trim();
    if (!raw) return 30;
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return null;
    const normalized = Math.floor(parsed);
    if (normalized < 1 || normalized > 200) return null;
    return normalized;
}
