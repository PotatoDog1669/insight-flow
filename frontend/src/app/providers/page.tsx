"use client";

import { useCallback, useEffect, useState } from "react";
import { Bot, KeyRound, Save, CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
    getProviders,
    updateProvider,
    type AgentProviderConfig,
    type LLMProviderConfig,
    type Provider,
    type ProviderConfig,
} from "@/lib/api";

export default function ProvidersPage() {
    const [providers, setProviders] = useState<Provider[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [editingId, setEditingId] = useState<string | null>(null);
    const [editConfig, setEditConfig] = useState<ProviderConfig | null>(null);
    const [submitting, setSubmitting] = useState(false);

    const loadData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await getProviders();
            setProviders(data || []);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load providers");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadData();
    }, [loadData]);

    const handleEnableToggle = async (provider: Provider) => {
        const nextEnabled = !provider.enabled;
        try {
            setProviders(prev => prev.map(item => item.id === provider.id ? { ...item, enabled: nextEnabled } : item));
            await updateProvider(provider.id, { enabled: nextEnabled });
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to update provider status");
            void loadData();
        }
    };

    const startEditing = (provider: Provider) => {
        setEditingId(provider.id);
        if (provider.id === "agent_codex") {
            setEditConfig({
                auth_mode: provider.config.auth_mode || "api_key",
                base_url: provider.config.base_url || "",
                model: provider.config.model || "gpt-5-codex",
                timeout_sec: Number(provider.config.timeout_sec || 90),
                api_key: provider.config.api_key || "",
                oauth_token: provider.config.oauth_token || "",
            });
            return;
        }
        setEditConfig({
            base_url: provider.config.base_url || "https://api.openai.com/v1",
            model: provider.config.model || "gpt-4o-mini",
            timeout_sec: Number(provider.config.timeout_sec || 30),
            max_retry: Number(provider.config.max_retry || 2),
            max_output_tokens: Number(provider.config.max_output_tokens || 2048),
            temperature: Number(provider.config.temperature || 0.3),
            api_key: provider.config.api_key || "",
        });
    };

    const handleSave = async (providerId: Provider["id"]) => {
        if (!editConfig) {
            return;
        }
        const provider = providers.find(item => item.id === providerId);
        if (!provider) {
            return;
        }
        setSubmitting(true);
        setError(null);
        try {
            let payload: ProviderConfig;
            if (provider.id === "agent_codex") {
                const config = editConfig as AgentProviderConfig;
                payload = {
                    auth_mode: config.auth_mode,
                    base_url: String(config.base_url || "").trim(),
                    model: String(config.model || "").trim(),
                    timeout_sec: Math.max(Number(config.timeout_sec || 90), 1),
                    api_key: String(config.api_key || "").trim(),
                    oauth_token: String(config.oauth_token || "").trim(),
                };
            } else {
                const config = editConfig as LLMProviderConfig;
                payload = {
                    base_url: String(config.base_url || "").trim(),
                    model: String(config.model || "").trim(),
                    timeout_sec: Math.max(Number(config.timeout_sec || 30), 1),
                    max_retry: Math.max(Number(config.max_retry || 0), 0),
                    max_output_tokens: Math.max(Number(config.max_output_tokens || 1200), 1),
                    temperature: Number(config.temperature || 0.3),
                    api_key: String(config.api_key || "").trim(),
                };
            }
            const updated = await updateProvider(providerId, { config: payload, enabled: true });
            setProviders(prev => prev.map(item => item.id === providerId ? updated : item));
            setEditingId(null);
            setEditConfig(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save provider config");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 py-8 md:py-12">
            <header className="mb-8">
                <h1 className="text-3xl font-bold tracking-tight mb-2">Providers</h1>
                <p className="text-muted-foreground text-sm max-w-2xl">
                    Manage AI executors for processing stages. Configure Codex Agent and LLM provider credentials/models in one place.
                </p>
            </header>

            {loading && <div className="py-10 text-sm text-muted-foreground">Loading providers...</div>}
            {error && <div className="py-4 text-sm text-red-500">{error}</div>}

            {!loading && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {providers.map((provider) => (
                        <Card
                            key={provider.id}
                            className={cn(
                                "border-border/40 transition-all duration-300 flex flex-col relative overflow-hidden",
                                provider.enabled ? "border-green-500/30 shadow-sm" : "hover:border-border/80 shadow-sm hover:shadow-md"
                            )}
                        >
                            {provider.enabled && (
                                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-green-400 to-emerald-500" />
                            )}

                            <CardHeader className="pb-4">
                                <div className="flex items-start justify-between">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-sm border bg-slate-900 text-white border-slate-800">
                                            <Bot className="w-5 h-5" />
                                        </div>
                                        <div>
                                            <CardTitle className="text-lg font-bold leading-snug tracking-tight">{provider.name}</CardTitle>
                                            <div className="flex items-center mt-1 gap-2 text-xs">
                                                <Badge
                                                    variant="secondary"
                                                    className={cn(
                                                        "border-none mt-0.5",
                                                        provider.enabled ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" : "bg-muted text-muted-foreground"
                                                    )}
                                                >
                                                    {provider.enabled ? "Enabled" : "Disabled"}
                                                </Badge>
                                            </div>
                                        </div>
                                    </div>

                                    <label className="flex items-center cursor-pointer">
                                        <div className="relative">
                                            <input
                                                type="checkbox"
                                                className="sr-only"
                                                checked={provider.enabled}
                                                onChange={() => void handleEnableToggle(provider)}
                                                disabled={editingId === provider.id}
                                            />
                                            <div className={cn("block w-10 h-6 rounded-full transition-colors", provider.enabled ? "bg-green-500" : "bg-neutral-300 dark:bg-neutral-700")} />
                                            <div className={cn("dot absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition-transform", provider.enabled ? "transform translate-x-4" : "")} />
                                        </div>
                                    </label>
                                </div>
                                <p className="text-sm text-muted-foreground mt-4 leading-relaxed">{provider.description}</p>
                            </CardHeader>

                            <CardContent className="pb-6 flex-1 text-sm bg-muted/20 border-t border-border/20 pt-4">
                                {editingId === provider.id && editConfig ? (
                                    <div className="space-y-4 animate-in fade-in zoom-in-95 duration-200">
                                        <div className="flex items-center gap-2 mb-2 text-foreground font-medium">
                                            <KeyRound className="w-4 h-4 text-primary" />
                                            Provider Configuration
                                        </div>
                                        {provider.id === "agent_codex" && "auth_mode" in editConfig ? (
                                            <>
                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">Auth Mode</label>
                                                    <select
                                                        value={editConfig.auth_mode}
                                                        onChange={(e) => setEditConfig({ ...editConfig, auth_mode: e.target.value as "api_key" | "oauth" })}
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    >
                                                        <option value="api_key">API Key</option>
                                                        <option value="oauth">OAuth Token</option>
                                                    </select>
                                                </div>

                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">Base URL</label>
                                                    <input
                                                        value={editConfig.base_url}
                                                        onChange={(e) => setEditConfig({ ...editConfig, base_url: e.target.value })}
                                                        placeholder="https://api.openai.com/v1"
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    />
                                                </div>

                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">Model</label>
                                                    <input
                                                        value={editConfig.model}
                                                        onChange={(e) => setEditConfig({ ...editConfig, model: e.target.value })}
                                                        placeholder="gpt-5-codex"
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    />
                                                </div>

                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">Timeout (sec)</label>
                                                    <input
                                                        type="number"
                                                        min={1}
                                                        value={editConfig.timeout_sec}
                                                        onChange={(e) => setEditConfig({ ...editConfig, timeout_sec: Number(e.target.value || 90) })}
                                                        placeholder="90"
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    />
                                                </div>

                                                {editConfig.auth_mode === "api_key" ? (
                                                    <div className="space-y-1.5">
                                                        <label className="text-xs font-medium text-muted-foreground">API Key</label>
                                                        <input
                                                            type="password"
                                                            value={editConfig.api_key}
                                                            onChange={(e) => setEditConfig({ ...editConfig, api_key: e.target.value })}
                                                            placeholder="sk-..."
                                                            className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                        />
                                                    </div>
                                                ) : (
                                                    <div className="space-y-1.5">
                                                        <label className="text-xs font-medium text-muted-foreground">OAuth Access Token</label>
                                                        <input
                                                            type="password"
                                                            value={editConfig.oauth_token}
                                                            onChange={(e) => setEditConfig({ ...editConfig, oauth_token: e.target.value })}
                                                            placeholder="oauth token"
                                                            className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                        />
                                                    </div>
                                                )}
                                            </>
                                        ) : (
                                            <>
                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">Base URL</label>
                                                    <input
                                                        value={editConfig.base_url}
                                                        onChange={(e) => setEditConfig({ ...editConfig, base_url: e.target.value })}
                                                        placeholder="https://api.openai.com/v1"
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    />
                                                </div>

                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">Model</label>
                                                    <input
                                                        value={editConfig.model}
                                                        onChange={(e) => setEditConfig({ ...editConfig, model: e.target.value })}
                                                        placeholder="gpt-4o-mini"
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    />
                                                </div>

                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">Timeout (sec)</label>
                                                    <input
                                                        type="number"
                                                        min={1}
                                                        value={editConfig.timeout_sec}
                                                        onChange={(e) => setEditConfig({ ...editConfig, timeout_sec: Number(e.target.value || 30) })}
                                                        placeholder="30"
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    />
                                                </div>

                                                {"max_retry" in editConfig && (
                                                    <div className="space-y-1.5">
                                                        <label className="text-xs font-medium text-muted-foreground">Max Retry</label>
                                                        <input
                                                            type="number"
                                                            min={0}
                                                            value={editConfig.max_retry}
                                                            onChange={(e) => setEditConfig({ ...editConfig, max_retry: Number(e.target.value || 0) })}
                                                            placeholder="2"
                                                            className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                        />
                                                    </div>
                                                )}

                                                {"max_output_tokens" in editConfig && (
                                                    <div className="space-y-1.5">
                                                        <label className="text-xs font-medium text-muted-foreground">Max Output Tokens</label>
                                                        <input
                                                            type="number"
                                                            min={1}
                                                            value={editConfig.max_output_tokens}
                                                            onChange={(e) => setEditConfig({ ...editConfig, max_output_tokens: Number(e.target.value || 1) })}
                                                            placeholder="2048"
                                                            className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                        />
                                                    </div>
                                                )}

                                                {"temperature" in editConfig && (
                                                    <div className="space-y-1.5">
                                                        <label className="text-xs font-medium text-muted-foreground">Temperature</label>
                                                        <input
                                                            type="number"
                                                            step="0.1"
                                                            value={editConfig.temperature}
                                                            onChange={(e) => setEditConfig({ ...editConfig, temperature: Number(e.target.value || 0) })}
                                                            placeholder="0.3"
                                                            className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                        />
                                                    </div>
                                                )}

                                                <div className="space-y-1.5">
                                                    <label className="text-xs font-medium text-muted-foreground">API Key</label>
                                                    <input
                                                        type="password"
                                                        value={editConfig.api_key}
                                                        onChange={(e) => setEditConfig({ ...editConfig, api_key: e.target.value })}
                                                        placeholder="sk-..."
                                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                    />
                                                </div>
                                            </>
                                        )}
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        {provider.id === "agent_codex" && (
                                            <div className="flex justify-between border-b border-border/30 pb-2">
                                                <span className="text-muted-foreground text-xs">Auth Mode</span>
                                                <span className="font-mono text-xs text-foreground">{provider.config.auth_mode || "-"}</span>
                                            </div>
                                        )}
                                        <div className="flex justify-between border-b border-border/30 pb-2">
                                            <span className="text-muted-foreground text-xs">Base URL</span>
                                            <span className="font-mono text-xs text-foreground truncate max-w-[65%] text-right">{provider.config.base_url || "-"}</span>
                                        </div>
                                        <div className="flex justify-between border-b border-border/30 pb-2">
                                            <span className="text-muted-foreground text-xs">Model</span>
                                            <span className="font-mono text-xs text-foreground">{provider.config.model || "-"}</span>
                                        </div>
                                        {provider.id === "llm_openai" && (
                                            <div className="flex justify-between border-b border-border/30 pb-2">
                                                <span className="text-muted-foreground text-xs">Max Retry</span>
                                                <span className="font-mono text-xs text-foreground">{provider.config.max_retry ?? "-"}</span>
                                            </div>
                                        )}
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground text-xs">Timeout</span>
                                            <span className="font-mono text-xs text-foreground">{provider.config.timeout_sec || "-"}s</span>
                                        </div>
                                    </div>
                                )}
                            </CardContent>

                            <CardFooter className="pt-4 flex justify-between gap-3">
                                {editingId === provider.id ? (
                                    <>
                                        <button
                                            onClick={() => {
                                                setEditingId(null);
                                                setEditConfig(null);
                                            }}
                                            className="flex-1 border border-border rounded-md py-2 text-sm hover:bg-muted transition-colors"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            onClick={() => void handleSave(provider.id)}
                                            disabled={submitting}
                                            className="flex-1 bg-foreground text-background rounded-md py-2 text-sm hover:bg-foreground/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                        >
                                            <Save className="w-4 h-4" />
                                            {submitting ? "Saving..." : "Save"}
                                        </button>
                                    </>
                                ) : (
                                    <>
                                        <button
                                            onClick={() => startEditing(provider)}
                                            className="flex-1 border border-border rounded-md py-2 text-sm hover:bg-muted transition-colors"
                                        >
                                            Configure
                                        </button>
                                        {provider.enabled && (
                                            <div className="flex items-center gap-2 text-green-600 text-xs px-3">
                                                <CheckCircle2 className="w-4 h-4" />
                                                Active
                                            </div>
                                        )}
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
