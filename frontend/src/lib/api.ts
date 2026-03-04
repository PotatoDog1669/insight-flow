/**
 * LexDeepResearch — 后端 API 调用封装
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Source {
    id: string;
    name: string;
    category: string;
    collect_method: string;
    config: Record<string, unknown>;
    enabled: boolean;
    status: "healthy" | "error" | "running";
    last_run: string | null;
    last_collected: string | null;
    created_at: string;
    updated_at: string;
}

export interface Article {
    id: string;
    source_id: string;
    source_name: string | null;
    category: string | null;
    title: string;
    url: string | null;
    summary: string | null;
    keywords: string[];
    ai_score: number | null;
    status: string;
    source_type: string;
    report_ids: string[];
    published_at: string | null;
    collected_at: string;
    created_at: string;
}

export interface Monitor {
    id: string;
    name: string;
    time_period: "daily" | "weekly" | "custom";
    report_type: "daily" | "weekly" | "research";
    source_ids: string[];
    source_overrides?: Record<string, { max_items?: number; limit?: number; max_results?: number; keywords?: string[]; usernames?: string[] }>;
    destination_ids: string[];
    window_hours: number;
    custom_schedule: string | null;
    enabled: boolean;
    status: "active" | "paused";
    last_run: string | null;
    created_at: string;
    updated_at: string;
}

export interface Destination {
    id: "notion" | "obsidian" | "rss";
    name: string;
    type: "notion" | "obsidian" | "rss";
    description: string;
    config: Record<string, string>;
    enabled: boolean;
    created_at?: string;
}

export interface AgentProviderConfig {
    auth_mode: "api_key" | "oauth";
    base_url: string;
    model: string;
    timeout_sec: number;
    api_key: string;
    oauth_token: string;
}

export interface LLMProviderConfig {
    base_url: string;
    model: string;
    timeout_sec: number;
    max_retry: number;
    max_output_tokens: number;
    temperature: number;
    api_key: string;
}

export type ProviderConfig = AgentProviderConfig | LLMProviderConfig;

export interface AgentProvider {
    id: "agent_codex";
    name: string;
    type: "agent";
    description: string;
    config: AgentProviderConfig;
    enabled: boolean;
}

export interface LLMProvider {
    id: "llm_openai";
    name: string;
    type: "llm";
    description: string;
    config: LLMProviderConfig;
    enabled: boolean;
}

export type Provider = AgentProvider | LLMProvider;

export interface MonitorCreate {
    name: string;
    time_period: "daily" | "weekly" | "custom";
    report_type?: "daily" | "weekly" | "research";
    source_ids: string[];
    source_overrides?: Record<string, { max_items?: number; limit?: number; max_results?: number; keywords?: string[]; usernames?: string[] }>;
    destination_ids?: string[];
    window_hours?: number;
    custom_schedule?: string | null;
    enabled: boolean;
}

export interface MonitorUpdate {
    name?: string;
    time_period?: "daily" | "weekly" | "custom";
    report_type?: "daily" | "weekly" | "research";
    source_ids?: string[];
    source_overrides?: Record<string, { max_items?: number; limit?: number; max_results?: number; keywords?: string[]; usernames?: string[] }>;
    destination_ids?: string[];
    window_hours?: number;
    custom_schedule?: string | null;
    enabled?: boolean;
}

export interface MonitorRunResponse {
    task_id: string;
    run_id: string;
    status: "pending" | "running";
    monitor_id: string;
}

export interface MonitorRunSummary {
    run_id: string;
    task_id: string;
    trigger_type?: string;
    status: string;
    articles_count: number;
    source_total: number;
    source_done: number;
    source_failed: number;
    created_at?: string | null;
    started_at?: string | null;
    finished_at?: string | null;
    error_message?: string | null;
}

export interface MonitorRunCancelResponse {
    run_id: string;
    monitor_id: string;
    status: string;
}

export interface TaskEvent {
    id: string;
    run_id: string;
    task_id: string | null;
    source_id: string | null;
    stage: string;
    level: string;
    event_type: string;
    message: string;
    payload: Record<string, unknown>;
    created_at: string | null;
}

export interface ReportTopic {
    name: string;
    weight: number;
}

export interface ReportEvent {
    event_id: string;
    index: number;
    title: string;
    category: string;
    one_line_tldr: string;
    detail: string;
    keywords: string[];
    entities: string[];
    metrics: string[];
    source_links: string[];
    source_count: number;
    source_name: string;
    published_at: string | null;
}

export interface Report {
    id: string;
    user_id: string | null;
    time_period: "daily" | "weekly" | "custom";
    report_type: "daily" | "weekly" | "research";
    title: string;
    report_date: string;
    tldr: string[];
    article_count: number;
    topics: ReportTopic[];
    events: ReportEvent[];
    global_tldr: string;
    content: string;
    article_ids: string[];
    published_to: string[];
    metadata: Record<string, unknown>;
    created_at: string;
}

export interface ReportFilters {
    time_periods: string[];
    report_types: string[];
    categories: string[];
}

export interface UserMe {
    id: string;
    email: string;
    name: string | null;
    plan: string;
    settings: Record<string, unknown>;
    created_at: string;
    updated_at: string;
}

export interface UserSettings {
    default_time_period: "daily" | "weekly" | "custom";
    default_report_type: "daily" | "weekly" | "research";
    default_sink: string;
}

export interface CollectTask {
    id: string;
    run_id?: string;
    source_id: string | null;
    trigger_type: string;
    status: string;
    articles_count: number;
    started_at?: string | null;
    finished_at?: string | null;
    created_at?: string | null;
    error_message?: string | null;
    stage_trace?: Record<string, unknown>[];
}

export interface ReportListParams {
    time_period?: "daily" | "weekly" | "custom";
    report_type?: "daily" | "weekly" | "research";
    limit?: number;
    page?: number;
}

function toQueryString(params?: object): string {
    if (!params) return "";
    const sp = new URLSearchParams();
    Object.entries(params as Record<string, unknown>).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
            sp.set(key, String(value));
        }
    });
    const query = sp.toString();
    return query ? `?${query}` : "";
}

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    if (!res.ok) throw new Error(`API Error: ${res.status}`);
    return res.json();
}

// ---- 信息源 ----
export const getSources = (category?: string) =>
    fetchAPI<Source[]>(`/api/v1/sources${category ? `?category=${category}` : ""}`);

export const getSourceCategories = () =>
    fetchAPI<{ category: string; count: number }[]>("/api/v1/sources/categories");

export const getSource = (sourceId: string) =>
    fetchAPI<Source>(`/api/v1/sources/${sourceId}`);

export const createSource = (body: {
    name: string;
    category: string;
    collect_method: string;
    config?: Record<string, unknown>;
    enabled?: boolean;
}) =>
    fetchAPI<Source>("/api/v1/sources", {
        method: "POST",
        body: JSON.stringify(body),
    });

export const updateSource = (
    sourceId: string,
    body: { name?: string; config?: Record<string, unknown>; enabled?: boolean }
) =>
    fetchAPI<Source>(`/api/v1/sources/${sourceId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
    });

export const deleteSource = (sourceId: string) =>
    fetchAPI<void>(`/api/v1/sources/${sourceId}`, { method: "DELETE" });

export interface SourceTestResponse {
    success: boolean;
    message: string | null;
    sample_articles: {
        title: string;
        url: string | null;
        published_at: string | null;
    }[];
}

export const testSource = (sourceId: string) =>
    fetchAPI<SourceTestResponse>(`/api/v1/sources/${sourceId}/test`, {
        method: "POST",
    });

// ---- 文章 ----
export const getArticles = (params?: Record<string, string | number>) => {
    const query = toQueryString(params);
    return fetchAPI<Article[]>(`/api/v1/articles${query}`);
};

export const getArticleById = (articleId: string) => fetchAPI<Article>(`/api/v1/articles/${articleId}`);

// ---- Monitors ----
export const getMonitors = () => fetchAPI<Monitor[]>("/api/v1/monitors");

export async function createMonitor(data: MonitorCreate): Promise<Monitor> {
    return fetchAPI<Monitor>("/api/v1/monitors", {
        method: "POST",
        body: JSON.stringify(data),
    });
}

export const runMonitor = (monitorId: string, body?: { window_hours?: number; trigger_type?: "manual" | "test" }) =>
    fetchAPI<MonitorRunResponse>(`/api/v1/monitors/${monitorId}/run`, {
        method: "POST",
        body: JSON.stringify(body ?? {}),
    });

export const getMonitorLogs = (monitorId: string) =>
    fetchAPI<CollectTask[]>(`/api/v1/monitors/${monitorId}/logs`);

export const getMonitorRuns = (monitorId: string, limit = 30) =>
    fetchAPI<MonitorRunSummary[]>(`/api/v1/monitors/${monitorId}/runs?limit=${limit}`);

export const getMonitorRunEvents = (monitorId: string, runId: string) =>
    fetchAPI<TaskEvent[]>(`/api/v1/monitors/${monitorId}/runs/${runId}/events`);

export const cancelMonitorRun = (monitorId: string, runId: string) =>
    fetchAPI<MonitorRunCancelResponse>(`/api/v1/monitors/${monitorId}/runs/${runId}/cancel`, {
        method: "POST",
    });

export async function updateMonitor(id: string, data: MonitorUpdate): Promise<Monitor> {
    return fetchAPI<Monitor>(`/api/v1/monitors/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
    });
}

export const deleteMonitor = (monitorId: string) =>
    fetchAPI<void>(`/api/v1/monitors/${monitorId}`, { method: "DELETE" });

// ---- Reports ----
export const getReports = (params?: ReportListParams) => {
    const query = toQueryString(params);
    return fetchAPI<Report[]>(`/api/v1/reports${query}`);
};

export const getReportById = (reportId: string) => fetchAPI<Report>(`/api/v1/reports/${reportId}`);

export const getReportFilters = () => fetchAPI<ReportFilters>("/api/v1/reports/filters");

export const createCustomReport = (body: {
    title: string;
    prompt: string;
    time_period?: "daily" | "weekly" | "custom";
    report_type?: "daily" | "weekly" | "research";
    category?: string;
    report_date?: string;
}) =>
    fetchAPI<unknown>("/api/v1/reports/custom", {
        method: "POST",
        body: JSON.stringify(body),
    });

// ---- Users ----
export const getMe = () => fetchAPI<UserMe>("/api/v1/users/me");

export const updateMySettings = (body: {
    default_time_period?: "daily" | "weekly" | "custom";
    default_report_type?: "daily" | "weekly" | "research";
    default_sink?: string;
}) =>
    fetchAPI<UserSettings>("/api/v1/users/me/settings", {
        method: "PATCH",
        body: JSON.stringify(body),
    });

// ---- Destinations ----
export const getDestinations = () => fetchAPI<Destination[]>("/api/v1/destinations");

export const updateDestination = (
    id: "notion" | "obsidian" | "rss",
    body: { config?: Record<string, string>; enabled?: boolean }
) =>
    fetchAPI<Destination>(`/api/v1/destinations/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
    });

// ---- Providers ----
export const getProviders = () => fetchAPI<Provider[]>("/api/v1/providers");

export const updateProvider = (
    id: Provider["id"],
    body: { config?: Partial<ProviderConfig>; enabled?: boolean }
) =>
    fetchAPI<Provider>(`/api/v1/providers/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
    });

// ---- 采集任务（兼容旧页面）----
export const getTasks = () => fetchAPI<CollectTask[]>("/api/v1/tasks");

export const triggerCollect = (body: { source_id?: string; category?: string }) =>
    fetchAPI<CollectTask>("/api/v1/tasks/trigger", {
        method: "POST",
        body: JSON.stringify(body),
    });

// ---- 健康检查 ----
export const healthCheck = () => fetchAPI<{ status: string }>("/health");
