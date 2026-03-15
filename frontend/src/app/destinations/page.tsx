"use client";

import { useCallback, useEffect, useState } from "react";
import { Settings, ExternalLink, HardDrive, Key, Save, CheckCircle2, Rss, Copy } from "lucide-react";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { getDestinations, updateDestination, type Destination } from "@/lib/api";

const NOTION_ID_PATTERN_GLOBAL = /([0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})/g;
const NOTION_ID_PATTERN_SINGLE = /([0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})/;

function extractNotionId(value: string): string | null {
    const raw = value.trim();
    if (!raw) {
        return null;
    }

    try {
        const parsed = new URL(raw);
        if (parsed.hostname.toLowerCase().includes("notion.so")) {
            const pathMatches = Array.from(parsed.pathname.matchAll(NOTION_ID_PATTERN_GLOBAL));
            const fromPath = pathMatches[pathMatches.length - 1]?.[1];
            if (fromPath) {
                return fromPath.replaceAll("-", "").toLowerCase();
            }
            for (const key of ["database_id", "page_id", "id", "p", "block_id"]) {
                const candidate = parsed.searchParams.get(key);
                if (!candidate) {
                    continue;
                }
                const queryMatch = candidate.match(NOTION_ID_PATTERN_SINGLE);
                if (queryMatch?.[1]) {
                    return queryMatch[1].replaceAll("-", "").toLowerCase();
                }
            }
        }
    } catch {
        // Raw ID or non-URL text input, continue with generic matching.
    }

    const match = raw.match(NOTION_ID_PATTERN_SINGLE);
    if (!match?.[1]) {
        return null;
    }
    return match[1].replaceAll("-", "").toLowerCase();
}

function normalizeNotionField(value: string): string {
    const parsed = extractNotionId(value);
    if (parsed) {
        return parsed;
    }
    return value.trim();
}

function normalizeNotionConfig(config: Record<string, string>): Record<string, string> {
    const normalized = { ...config };
    if (normalized.database_id) {
        normalized.database_id = normalizeNotionField(normalized.database_id);
    }
    if (normalized.parent_page_id) {
        normalized.parent_page_id = normalizeNotionField(normalized.parent_page_id);
    }
    return normalized;
}

export default function DestinationsPage() {
    const [destinations, setDestinations] = useState<Destination[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Track editing state per destination
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editConfig, setEditConfig] = useState<Record<string, string>>({});
    const [submitting, setSubmitting] = useState(false);

    const loadData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await getDestinations();
            setDestinations(data || []);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadData();
    }, [loadData]);

    const handleEnableToggle = async (dest: Destination) => {
        const nextEnabled = !dest.enabled;
        try {
            setDestinations(prev => prev.map(d => d.id === dest.id ? { ...d, enabled: nextEnabled } : d));
            await updateDestination(dest.id, { enabled: nextEnabled });
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to toggle status");
            // Revert changes on error
            void loadData();
        }
    };

    const handleSaveConfig = async (destId: Destination["id"]) => {
        setSubmitting(true);
        setError(null);
        try {
            const destination = destinations.find((item) => item.id === destId);
            const configPayload = destination?.type === "notion" ? normalizeNotionConfig(editConfig) : editConfig;
            if (destination?.type === "notion") {
                setEditConfig(configPayload);
            }
            const updated = await updateDestination(destId, { config: configPayload, enabled: true });
            setDestinations(prev => prev.map(d => d.id === destId ? updated : d));

            setEditingId(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save configuration");
        } finally {
            setSubmitting(false);
        }
    };

    const startEditing = (dest: Destination) => {
        setEditingId(dest.id);
        const normalized = Object.fromEntries(
            Object.entries(dest.config ?? {}).map(([key, value]) => [key, typeof value === "string" ? value : String(value ?? "")])
        );
        setEditConfig(normalized);
    };

    const normalizeEditConfigNotionId = (field: "database_id" | "parent_page_id") => {
        setEditConfig((prev) => {
            const raw = String(prev[field] || "");
            if (!raw) {
                return prev;
            }
            const normalized = normalizeNotionField(raw);
            if (normalized === raw) {
                return prev;
            }
            return { ...prev, [field]: normalized };
        });
    };

    const getTypeIcon = (destType: string, className?: string) => {
        switch (destType) {
            case "notion": return <ExternalLink className={cn("w-5 h-5", className)} />;
            case "obsidian": return <HardDrive className={cn("w-5 h-5", className)} />;
            case "rss": return <Rss className={cn("w-5 h-5", className)} />;
            default: return <Settings className={cn("w-5 h-5", className)} />;
        }
    };

    const isConnected = (dest: Destination) => dest.enabled;

    return (
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 py-8 md:py-12">
            <header className="mb-10 flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight mb-2">输出配置</h1>
                    <p className="text-muted-foreground text-sm max-w-2xl">
                        配置多端输出渠道，将自动生成的洞察报告持续同步到您的工作流中。
                    </p>
                </div>
            </header>

            {loading && <div className="py-10 text-sm text-muted-foreground">正在加载输出配置...</div>}
            {error && <div className="py-4 text-sm text-red-500">{error}</div>}

            {!loading && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {destinations.map((dest) => (
                        <Card
                            key={dest.id}
                            className={cn(
                                "border-border/40 transition-all duration-300 flex flex-col relative overflow-hidden",
                                isConnected(dest) ? "border-green-500/30 shadow-sm" : "hover:border-border/80 shadow-sm hover:shadow-md"
                            )}
                        >
                            {/* Active Indicator Bar */}
                            {isConnected(dest) && (
                                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-green-400 to-emerald-500" />
                            )}

                            <CardHeader className="pb-4">
                                <div className="flex items-start justify-between">
                                    <div className="flex items-center gap-3">
                                        <div className={cn(
                                            "w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-sm border",
                                            dest.type === "notion" ? "bg-white text-black border-neutral-200" :
                                                dest.type === "obsidian" ? "bg-purple-600 text-white border-purple-700" :
                                                    dest.type === "rss" ? "bg-orange-500 text-white border-orange-600" : "bg-secondary text-foreground"
                                        )}>
                                            {getTypeIcon(dest.type)}
                                        </div>
                                        <div>
                                            <CardTitle className="text-lg font-bold leading-snug tracking-tight">
                                                {dest.name}
                                            </CardTitle>
                                            <div className="flex items-center mt-1 gap-2 text-xs">
                                                <Badge variant="secondary" className={cn(
                                                    "border-none mt-0.5",
                                                    isConnected(dest) ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" :
                                                        "bg-muted text-muted-foreground"
                                                )}>
                                                    {isConnected(dest) ? "已生效" : "已停用"}
                                                </Badge>
                                            </div>
                                        </div>
                                    </div>

                                    <label className="flex items-center cursor-pointer">
                                        <div className="relative">
                                            <input
                                                type="checkbox"
                                                className="sr-only"
                                                checked={dest.enabled}
                                                onChange={() => void handleEnableToggle(dest)}
                                                disabled={editingId === dest.id}
                                            />
                                            <div className={cn(
                                                "block w-10 h-6 rounded-full transition-colors",
                                                dest.enabled ? "bg-green-500" : "bg-neutral-300 dark:bg-neutral-700"
                                            )}></div>
                                            <div className={cn(
                                                "dot absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition-transform",
                                                dest.enabled ? "transform translate-x-4" : ""
                                            )}></div>
                                        </div>
                                    </label>
                                </div>
                                <p className="text-sm text-muted-foreground mt-4 leading-relaxed">
                                    {dest.description}
                                </p>
                            </CardHeader>

                            <CardContent className="pb-6 flex-1 text-sm bg-muted/20 border-t border-border/20 pt-4">
                                {editingId === dest.id ? (
                                    <div className="space-y-4 animate-in fade-in zoom-in-95 duration-200">
                                        <div className="flex items-center gap-2 mb-2 text-foreground font-medium">
                                            <Key className="w-4 h-4 text-primary" />
                                            连接凭证
                                        </div>

                                        {dest.type === "notion" && (
                                            <>
                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">集成令牌 (Token)</label>
                                                    <input
                                                        type="password"
                                                        value={editConfig.token || ""}
                                                        onChange={(e) => setEditConfig({ ...editConfig, token: e.target.value })}
                                                        placeholder="secret_..."
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    />
                                                </div>
                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">目标 Database ID</label>
                                                    <input
                                                        value={editConfig.database_id || ""}
                                                        onChange={(e) => setEditConfig({ ...editConfig, database_id: e.target.value })}
                                                        onBlur={() => normalizeEditConfigNotionId("database_id")}
                                                        placeholder="粘贴 Notion 数据库链接或 ID"
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    />
                                                    <p className="text-[10px] text-muted-foreground leading-snug">
                                                        请确保在 Notion 数据库右上角菜单中已与您的内部集成共享了此数据库。
                                                    </p>
                                                </div>
                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">父级 Page ID（可选）</label>
                                                    <input
                                                        value={editConfig.parent_page_id || ""}
                                                        onChange={(e) => setEditConfig({ ...editConfig, parent_page_id: e.target.value })}
                                                        onBlur={() => normalizeEditConfigNotionId("parent_page_id")}
                                                        placeholder="粘贴 Notion 页面链接或 ID"
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    />
                                                    <p className="text-[10px] text-muted-foreground leading-snug">
                                                        如果您希望报告作为普通的 Notion 页面的子页面创建，请在此设置。
                                                    </p>
                                                </div>
                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">标题属性名称 (Title Property)</label>
                                                    <input
                                                        value={editConfig.title_property || "Name"}
                                                        onChange={(e) => setEditConfig({ ...editConfig, title_property: e.target.value })}
                                                        placeholder="Name"
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    />
                                                    <p className="text-[10px] text-muted-foreground leading-snug">
                                                        将其设置为您的数据库标题列（例如：名称、Name）。
                                                    </p>
                                                </div>
                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">摘要属性名称 (Summary Property)</label>
                                                    <input
                                                        value={editConfig.summary_property || "TL;DR"}
                                                        onChange={(e) => setEditConfig({ ...editConfig, summary_property: e.target.value })}
                                                        placeholder="TL;DR"
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    />
                                                    <p className="text-[10px] text-muted-foreground leading-snug">
                                                        此属性将用于接收报告级别的摘要 + 犀利评论。
                                                    </p>
                                                </div>
                                            </>
                                        )}

                                        {dest.type === "obsidian" && (
                                            <>
                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">本地 REST API URL</label>
                                                    <input
                                                        value={editConfig.api_url || ""}
                                                        onChange={(e) => setEditConfig({ ...editConfig, api_url: e.target.value })}
                                                        placeholder="http://127.0.0.1:27123"
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    />
                                                </div>
                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">API Key</label>
                                                    <input
                                                        type="password"
                                                        value={editConfig.api_key || ""}
                                                        onChange={(e) => setEditConfig({ ...editConfig, api_key: e.target.value })}
                                                        placeholder="来自 Obsidian 本地 REST API 设置"
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    />
                                                </div>
                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">Vault 目标活页夹（可选）</label>
                                                    <input
                                                        value={editConfig.target_folder || ""}
                                                        onChange={(e) => setEditConfig({ ...editConfig, target_folder: e.target.value })}
                                                        placeholder="例如：AI-Reports/"
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    />
                                                </div>
                                            </>
                                        )}

                                        {dest.type === "rss" && (
                                            <>
                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">订阅源 URL (Feed URL Endpoint)</label>
                                                    <div className="flex items-center gap-2">
                                                        <input
                                                            readOnly
                                                            value={editConfig.feed_url || "http://localhost:8000/api/v1/feed.xml"}
                                                            className="flex h-9 w-full rounded-md border border-input bg-muted px-3 py-1 text-sm shadow-sm opacity-80 cursor-not-allowed"
                                                        />
                                                        <button
                                                            onClick={() => navigator.clipboard.writeText(editConfig.feed_url || "http://localhost:8000/api/v1/feed.xml")}
                                                            className="h-9 px-3 rounded-md border bg-background hover:bg-muted transition-colors flex items-center justify-center shrink-0"
                                                            title="复制到剪贴板"
                                                        >
                                                            <Copy className="w-4 h-4 text-muted-foreground" />
                                                        </button>
                                                    </div>
                                                    <p className="text-[10px] text-muted-foreground leading-snug pt-1">
                                                        将此 URL 复制到您的 RSS 阅读器（例如 Feedly、Reeder）中进行订阅。后端将自动生成此订阅源。
                                                    </p>
                                                </div>
                                            </>
                                        )}

                                        <div className="flex items-center justify-end gap-2 pt-2">
                                            <button
                                                onClick={() => setEditingId(null)}
                                                className="px-3 py-1.5 text-xs font-medium bg-transparent hover:bg-muted text-muted-foreground rounded-md transition-colors"
                                            >
                                                取消
                                            </button>
                                            <button
                                                onClick={() => void handleSaveConfig(dest.id)}
                                                disabled={submitting}
                                                className="px-3 py-1.5 text-xs font-medium bg-foreground text-background hover:bg-foreground/90 disabled:opacity-50 rounded-md transition-colors flex items-center"
                                            >
                                                {submitting ? "测试中..." : <><Save className="w-3.5 h-3.5 mr-1" />保存并连接</>}
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        <div className="text-xs font-medium text-muted-foreground">当前配置</div>

                                        {dest.type === "notion" && (
                                            <div className="flex flex-col gap-1.5">
                                                <div className="flex items-center text-xs">
                                                    <span className="w-24 text-muted-foreground">Token:</span>
                                                    <span className="font-mono bg-background px-1.5 py-0.5 rounded border">{dest.config.token ? "••••••••••••" : "<未配置>"}</span>
                                                </div>
                                                <div className="flex items-center text-xs">
                                                    <span className="w-24 text-muted-foreground">数据库 ID:</span>
                                                    <span className="font-mono bg-background px-1.5 py-0.5 rounded border">{dest.config.database_id || "<未配置>"}</span>
                                                </div>
                                                <div className="flex items-center text-xs">
                                                    <span className="w-24 text-muted-foreground">标题字段:</span>
                                                    <span className="font-mono bg-background px-1.5 py-0.5 rounded border">{dest.config.title_property || "Name"}</span>
                                                </div>
                                                <div className="flex items-center text-xs">
                                                    <span className="w-24 text-muted-foreground">摘要:</span>
                                                    <span className="font-mono bg-background px-1.5 py-0.5 rounded border">{dest.config.summary_property || "TL;DR"}</span>
                                                </div>
                                            </div>
                                        )}

                                        {dest.type === "obsidian" && (
                                            <div className="flex flex-col gap-1.5">
                                                <div className="flex items-center text-xs">
                                                    <span className="w-24 text-muted-foreground">API 主机:</span>
                                                    <span className="font-mono bg-background px-1.5 py-0.5 rounded border text-foreground/80 truncate">{dest.config.api_url || "<未配置>"}</span>
                                                </div>
                                                <div className="flex items-center text-xs">
                                                    <span className="w-24 text-muted-foreground">活页夹:</span>
                                                    <span className="font-mono bg-background px-1.5 py-0.5 rounded border">{dest.config.target_folder || "/"}</span>
                                                </div>
                                            </div>
                                        )}

                                        {dest.type === "rss" && (
                                            <div className="flex flex-col gap-1.5">
                                                <div className="flex items-center text-xs">
                                                    <span className="w-24 text-muted-foreground shrink-0">RSS 地址:</span>
                                                    <span className="font-mono bg-background px-1.5 py-0.5 rounded border text-foreground/80 truncate">{dest.config.feed_url || "<无效>"}</span>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </CardContent>

                            {editingId !== dest.id && (
                                <CardFooter className="pt-0 justify-between bg-muted/20 border-border/40 pb-4 mt-auto">
                                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                        {isConnected(dest) ? (
                                            <><CheckCircle2 className="w-3.5 h-3.5 text-green-500" /> Ping 成功</>
                                        ) : (
                                            <span className="opacity-50">未连接</span>
                                        )}
                                    </div>
                                    <button
                                        onClick={() => startEditing(dest)}
                                        className="text-xs font-medium bg-secondary hover:bg-secondary/80 px-3 py-1.5 rounded-md transition-colors"
                                    >
                                        配置
                                    </button>
                                </CardFooter>
                            )}
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
