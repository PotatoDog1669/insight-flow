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
    depth: "brief" | "deep";
    source_ids: string[];
    custom_schedule: string | null;
    enabled: boolean;
    status: "active" | "paused";
    last_run: string | null;
    created_at: string;
    updated_at: string;
}

export interface CreateMonitorRequest {
    name: string;
    time_period: "daily" | "weekly" | "custom";
    depth: "brief" | "deep";
    source_ids: string[];
    custom_schedule?: string | null;
    enabled?: boolean;
}

export interface UpdateMonitorRequest {
    name?: string;
    time_period?: "daily" | "weekly" | "custom";
    depth?: "brief" | "deep";
    source_ids?: string[];
    custom_schedule?: string | null;
    enabled?: boolean;
}

export interface MonitorRunResponse {
    task_id: string;
    status: "pending" | "running";
    monitor_id: string;
}

export interface ReportTopic {
    name: string;
    weight: number;
}

export interface Report {
    id: string;
    user_id: string | null;
    time_period: "daily" | "weekly" | "custom";
    depth: "brief" | "deep";
    title: string;
    report_date: string;
    tldr: string[];
    article_count: number;
    topics: ReportTopic[];
    content: string;
    article_ids: string[];
    published_to: string[];
    metadata: Record<string, unknown>;
    report_type: string;
    created_at: string;
}

export interface ReportFilters {
    time_periods: string[];
    depths: string[];
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
    default_depth: "brief" | "deep";
    default_sink: string;
}

export interface CollectTask {
    id: string;
    source_id: string | null;
    trigger_type: string;
    status: string;
    articles_count: number;
}

export interface ReportListParams {
    time_period?: "daily" | "weekly" | "custom";
    depth?: "brief" | "deep";
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

// ---- 文章 ----
export const getArticles = (params?: Record<string, string | number>) => {
    const query = toQueryString(params);
    return fetchAPI<Article[]>(`/api/v1/articles${query}`);
};

export const getArticleById = (articleId: string) => fetchAPI<Article>(`/api/v1/articles/${articleId}`);

// ---- Monitors ----
export const getMonitors = () => fetchAPI<Monitor[]>("/api/v1/monitors");

export const createMonitor = (body: CreateMonitorRequest) =>
    fetchAPI<Monitor>("/api/v1/monitors", {
        method: "POST",
        body: JSON.stringify(body),
    });

export const runMonitor = (monitorId: string) =>
    fetchAPI<MonitorRunResponse>(`/api/v1/monitors/${monitorId}/run`, {
        method: "POST",
    });

export const updateMonitor = (monitorId: string, body: UpdateMonitorRequest) =>
    fetchAPI<Monitor>(`/api/v1/monitors/${monitorId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
    });

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
    depth?: "brief" | "deep";
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
    default_depth?: "brief" | "deep";
    default_sink?: string;
}) =>
    fetchAPI<UserSettings>("/api/v1/users/me/settings", {
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
