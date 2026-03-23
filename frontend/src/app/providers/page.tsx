"use client";

import { useCallback, useEffect, useState } from "react";
import { Bot, KeyRound, Save, CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { SecretField } from "@/components/secret-field";
import { cn } from "@/lib/utils";
import {
    getProviders,
    testProvider,
    updateProvider,
    type LLMProviderConfig,
    type Provider,
    type ProviderTestResponse,
} from "@/lib/api";

function buildProviderPayload(providerId: Provider["id"], config: LLMProviderConfig): LLMProviderConfig {
    const authMode = providerId === "llm_codex" && config.auth_mode === "local_codex" ? "local_codex" : "api_key";
    return {
        auth_mode: authMode,
        base_url: String(config.base_url || "").trim(),
        model: String(config.model || "").trim(),
        timeout_sec: Math.max(Number(config.timeout_sec || 30), 1),
        max_retry: Math.max(Number(config.max_retry || 0), 0),
        max_output_tokens: Math.max(Number(config.max_output_tokens || 1200), 1),
        temperature: Number(config.temperature || 0.3),
        api_key: authMode === "local_codex" ? "" : String(config.api_key || "").trim(),
    };
}

export default function ProvidersPage() {
    const [providers, setProviders] = useState<Provider[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [editingId, setEditingId] = useState<string | null>(null);
    const [editConfig, setEditConfig] = useState<LLMProviderConfig | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [testingId, setTestingId] = useState<Provider["id"] | null>(null);
    const [testResult, setTestResult] = useState<ProviderTestResponse | null>(null);
    const [testError, setTestError] = useState<string | null>(null);

    const loadData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await getProviders();
            setProviders(data || []);
        } catch (err) {
            setError(err instanceof Error ? err.message : "加载模型配置失败");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadData();
    }, [loadData]);

    useEffect(() => {
        setTestResult(null);
        setTestError(null);
    }, [editingId, editConfig]);

    const handleEnableToggle = async (provider: Provider) => {
        const nextEnabled = !provider.enabled;
        try {
            setProviders((prev) => prev.map((item) => (item.id === provider.id ? { ...item, enabled: nextEnabled } : item)));
            await updateProvider(provider.id, { enabled: nextEnabled });
        } catch (err) {
            setError(err instanceof Error ? err.message : "更新模型状态失败");
            void loadData();
        }
    };

    const startEditing = (provider: Provider) => {
        setEditingId(provider.id);
        setEditConfig({
            auth_mode: provider.id === "llm_codex" && provider.config.auth_mode === "local_codex" ? "local_codex" : "api_key",
            base_url: provider.config.base_url || "https://api.openai.com/v1",
            model: provider.config.model || "gpt-4o-mini",
            timeout_sec: Number(provider.config.timeout_sec || 30),
            max_retry: Number(provider.config.max_retry || 2),
            max_output_tokens: Number(provider.config.max_output_tokens || 2048),
            temperature: Number(provider.config.temperature || 0.3),
            api_key: provider.config.api_key || "",
        });
    };

    const handleTest = async (provider: Provider) => {
        if (!editConfig) {
            return;
        }
        setTestingId(provider.id);
        setTestError(null);
        setTestResult(null);
        try {
            const result = await testProvider(provider.id, { config: buildProviderPayload(provider.id, editConfig) });
            setTestResult(result);
        } catch (err) {
            setTestError(err instanceof Error ? err.message : "测试模型连接失败");
        } finally {
            setTestingId(null);
        }
    };

    const handleSave = async (providerId: Provider["id"]) => {
        if (!editConfig) {
            return;
        }
        setSubmitting(true);
        setError(null);
        try {
            const updated = await updateProvider(providerId, {
                config: buildProviderPayload(providerId, editConfig),
                enabled: true,
            });
            setProviders((prev) => prev.map((item) => (item.id === providerId ? updated : item)));
            setEditingId(null);
            setEditConfig(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : "保存模型配置失败");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8 md:py-12">
            <header className="mb-8">
                <h1 className="mb-2 text-3xl font-bold tracking-tight">模型配置</h1>
                <p className="max-w-2xl text-sm text-muted-foreground">
                    统一管理工作流使用的 LLM provider。OpenAI 与 Codex 复用同一套 prompts 和 workflow，
                    这里只决定底层模型与连接参数。
                </p>
            </header>

            {loading && <div className="py-10 text-sm text-muted-foreground">正在加载模型配置...</div>}
            {error && <div className="py-4 text-sm text-red-500">{error}</div>}

            {!loading && (
                <div className={cn("grid grid-cols-1 gap-8 lg:grid-cols-2", editingId ? "items-start" : "items-stretch")}>
                    {providers.map((provider) => (
                        <Card
                            key={provider.id}
                            className={cn(
                                "relative flex flex-col overflow-hidden border-border/40 transition-all duration-300",
                                provider.enabled ? "border-green-500/40 border-[1.5px] shadow-sm" : "shadow-sm hover:border-border/80 hover:shadow-md",
                            )}
                        >
                            <CardHeader className="pb-4">
                                <div className="flex items-start justify-between">
                                    <div className="flex items-center gap-3">
                                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-800 bg-slate-900 text-white shadow-sm">
                                            <Bot className="h-5 w-5" />
                                        </div>
                                        <div>
                                            <CardTitle className="text-lg font-bold leading-snug tracking-tight">{provider.name}</CardTitle>
                                            <div className="mt-1 flex items-center gap-2 text-xs">
                                                <Badge
                                                    variant="secondary"
                                                    className={cn(
                                                        "mt-0.5 border-none",
                                                        provider.enabled ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" : "bg-muted text-muted-foreground",
                                                    )}
                                                >
                                                    {provider.enabled ? "已启用" : "已停用"}
                                                </Badge>
                                            </div>
                                        </div>
                                    </div>

                                    <label className="flex cursor-pointer items-center">
                                        <div className="relative">
                                            <input
                                                type="checkbox"
                                                className="sr-only"
                                                checked={provider.enabled}
                                                onChange={() => void handleEnableToggle(provider)}
                                                disabled={editingId === provider.id}
                                            />
                                            <div className={cn("block h-6 w-10 rounded-full transition-colors", provider.enabled ? "bg-green-500" : "bg-neutral-300 dark:bg-neutral-700")} />
                                            <div className={cn("dot absolute left-1 top-1 h-4 w-4 rounded-full bg-white transition-transform", provider.enabled ? "translate-x-4 transform" : "")} />
                                        </div>
                                    </label>
                                </div>
                                <p className="mt-4 text-sm leading-relaxed text-muted-foreground">{provider.description}</p>
                            </CardHeader>

                            <CardContent className="flex-1 border-t border-border/20 bg-muted/20 pb-6 pt-4 text-sm">
                                {editingId === provider.id && editConfig ? (
                                    <div className="animate-in zoom-in-95 fade-in space-y-4 duration-200">
                                        <div className="mb-2 flex items-center gap-2 font-medium text-foreground">
                                            <KeyRound className="h-4 w-4 text-primary" />
                                            模型连接配置
                                        </div>

                                        {provider.id === "llm_codex" && (
                                            <div className="space-y-1.5">
                                                <label className="text-xs font-medium text-muted-foreground" htmlFor={`${provider.id}-auth-mode`}>
                                                    连接模式
                                                </label>
                                                <select
                                                    id={`${provider.id}-auth-mode`}
                                                    aria-label="连接模式"
                                                    value={editConfig.auth_mode}
                                                    onChange={(e) =>
                                                        setEditConfig({
                                                            ...editConfig,
                                                            auth_mode: e.target.value === "local_codex" ? "local_codex" : "api_key",
                                                        })
                                                    }
                                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                >
                                                    <option value="api_key">API Key</option>
                                                    <option value="local_codex">Local 已登录 Codex</option>
                                                </select>
                                            </div>
                                        )}

                                        {editConfig.auth_mode !== "local_codex" && (
                                            <>
                                        <div className="space-y-1.5">
                                            <label className="text-xs font-medium text-muted-foreground" htmlFor={`${provider.id}-base-url`}>
                                                Base URL
                                            </label>
                                            <input
                                                id={`${provider.id}-base-url`}
                                                aria-label="Base URL"
                                                value={editConfig.base_url}
                                                onChange={(e) => setEditConfig({ ...editConfig, base_url: e.target.value })}
                                                placeholder="https://api.openai.com/v1"
                                                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                            />
                                        </div>
                                            </>
                                        )}

                                        <div className="space-y-1.5">
                                            <label className="text-xs font-medium text-muted-foreground" htmlFor={`${provider.id}-model`}>
                                                模型
                                            </label>
                                            <input
                                                id={`${provider.id}-model`}
                                                aria-label="模型"
                                                value={editConfig.model}
                                                onChange={(e) => setEditConfig({ ...editConfig, model: e.target.value })}
                                                placeholder="gpt-4o-mini"
                                                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                            />
                                        </div>

                                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                            <div className="space-y-1.5">
                                                <label className="text-xs font-medium text-muted-foreground" htmlFor={`${provider.id}-timeout`}>
                                                    超时（秒）
                                                </label>
                                                <input
                                                    id={`${provider.id}-timeout`}
                                                    aria-label="超时（秒）"
                                                    type="number"
                                                    min={1}
                                                    value={editConfig.timeout_sec}
                                                    onChange={(e) => setEditConfig({ ...editConfig, timeout_sec: Number(e.target.value) })}
                                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                />
                                            </div>
                                            <div className="space-y-1.5">
                                                <label className="text-xs font-medium text-muted-foreground" htmlFor={`${provider.id}-max-retry`}>
                                                    重试次数
                                                </label>
                                                <input
                                                    id={`${provider.id}-max-retry`}
                                                    aria-label="重试次数"
                                                    type="number"
                                                    min={0}
                                                    value={editConfig.max_retry}
                                                    onChange={(e) => setEditConfig({ ...editConfig, max_retry: Number(e.target.value) })}
                                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                />
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                            <div className="space-y-1.5">
                                                <label className="text-xs font-medium text-muted-foreground" htmlFor={`${provider.id}-max-output-tokens`}>
                                                    最大输出 Tokens
                                                </label>
                                                <input
                                                    id={`${provider.id}-max-output-tokens`}
                                                    aria-label="最大输出 Tokens"
                                                    type="number"
                                                    min={1}
                                                    value={editConfig.max_output_tokens}
                                                    onChange={(e) => setEditConfig({ ...editConfig, max_output_tokens: Number(e.target.value) })}
                                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                />
                                            </div>
                                            <div className="space-y-1.5">
                                                <label className="text-xs font-medium text-muted-foreground" htmlFor={`${provider.id}-temperature`}>
                                                    Temperature
                                                </label>
                                                <input
                                                    id={`${provider.id}-temperature`}
                                                    aria-label="Temperature"
                                                    type="number"
                                                    min={0}
                                                    step="0.1"
                                                    value={editConfig.temperature}
                                                    onChange={(e) => setEditConfig({ ...editConfig, temperature: Number(e.target.value) })}
                                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                />
                                            </div>
                                        </div>

                                        {editConfig.auth_mode !== "local_codex" && (
                                            <div className="space-y-1.5">
                                                <label className="text-xs font-medium text-muted-foreground" htmlFor={`${provider.id}-api-key`}>
                                                    API Key
                                                </label>
                                                <SecretField
                                                    inputId={`${provider.id}-api-key`}
                                                    label="API Key"
                                                    value={editConfig.api_key}
                                                    onChange={(value) => setEditConfig({ ...editConfig, api_key: value })}
                                                    placeholder="sk-..."
                                                />
                                            </div>
                                        )}

                                        {testError && (
                                            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
                                                {testError}
                                            </div>
                                        )}
                                        {testResult && (
                                            <div
                                                className={cn(
                                                    "rounded-md border px-3 py-2 text-xs",
                                                    testResult.success
                                                        ? "border-green-200 bg-green-50 text-green-700 dark:border-green-900/60 dark:bg-green-950/30 dark:text-green-300"
                                                        : "border-red-200 bg-red-50 text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300",
                                                )}
                                            >
                                                <div className="font-medium">{testResult.message}</div>
                                                <div className="mt-1 text-[11px] opacity-80">
                                                    {testResult.model || provider.config.model || "-"} · {testResult.latency_ms ?? 0} ms
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        {provider.id === "llm_codex" && (
                                            <div className="flex justify-between border-b border-border/30 pb-2">
                                                <span className="text-xs text-muted-foreground">连接模式</span>
                                                <span className="font-mono text-xs text-foreground">
                                                    {provider.config.auth_mode === "local_codex" ? "Local 已登录 Codex" : "API Key"}
                                                </span>
                                            </div>
                                        )}
                                        <div className="flex justify-between border-b border-border/30 pb-2">
                                            <span className="text-xs text-muted-foreground">Base URL</span>
                                            <span className="max-w-[65%] truncate text-right font-mono text-xs text-foreground">{provider.config.base_url}</span>
                                        </div>
                                        <div className="flex justify-between border-b border-border/30 pb-2">
                                            <span className="text-xs text-muted-foreground">模型</span>
                                            <span className="font-mono text-xs text-foreground">{provider.config.model}</span>
                                        </div>
                                        <div className="flex justify-between border-b border-border/30 pb-2">
                                            <span className="text-xs text-muted-foreground">重试次数</span>
                                            <span className="font-mono text-xs text-foreground">{provider.config.max_retry ?? 0}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-xs text-muted-foreground">超时</span>
                                            <span className="font-mono text-xs text-foreground">{provider.config.timeout_sec}s</span>
                                        </div>
                                    </div>
                                )}
                            </CardContent>

                            <CardFooter className="flex items-center justify-between gap-3 pt-4">
                                {editingId === provider.id && editConfig ? (
                                    <>
                                        <button
                                            onClick={() => {
                                                setEditingId(null);
                                                setEditConfig(null);
                                            }}
                                            className="flex-1 rounded-md border border-border py-2 text-sm transition-colors hover:bg-muted"
                                        >
                                            取消
                                        </button>
                                        <button
                                            onClick={() => void handleTest(provider)}
                                            disabled={testingId === provider.id || submitting}
                                            className="flex-1 rounded-md border border-border py-2 text-sm transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                                        >
                                            {testingId === provider.id ? "测试中..." : "测试连接"}
                                        </button>
                                        <button
                                            onClick={() => void handleSave(provider.id)}
                                            disabled={submitting || testingId === provider.id}
                                            className="flex flex-1 items-center justify-center gap-2 rounded-md bg-foreground py-2 text-sm text-background transition-colors hover:bg-foreground/90 disabled:cursor-not-allowed disabled:opacity-50"
                                        >
                                            <Save className="h-4 w-4" />
                                            {submitting ? "保存中..." : "保存"}
                                        </button>
                                    </>
                                ) : (
                                    <>
                                        <button
                                            onClick={() => startEditing(provider)}
                                            className="flex-1 rounded-md border border-border py-2 text-sm transition-colors hover:bg-muted"
                                        >
                                            配置
                                        </button>
                                        <div className="flex items-center gap-2 px-3 text-xs text-green-600">
                                            <CheckCircle2 className="h-4 w-4" />
                                            {provider.enabled ? "已生效" : "未启用"}
                                        </div>
                                    </>
                                )}
                            </CardFooter>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
