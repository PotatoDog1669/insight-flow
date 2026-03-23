"use client";

import type { Dispatch, SetStateAction } from "react";
import { Copy, Loader2 } from "lucide-react";

import { SecretField } from "@/components/secret-field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Destination, DestinationTestResponse, ObsidianVaultCandidate } from "@/lib/api";
import { cn } from "@/lib/utils";

import { FormField, inputClassName } from "@/app/destinations/shared";
import { getObsidianMode, normalizeNotionField } from "@/app/destinations/utils";

type DestinationFormSectionsProps = {
  activeDestination: Destination;
  detectedVaults: ObsidianVaultCandidate[];
  detectingVaultPath: boolean;
  editConfig: Record<string, string>;
  isEditing: boolean;
  onDetectObsidianVaultPath: () => void;
  setEditConfig: Dispatch<SetStateAction<Record<string, string>>>;
  testError: string | null;
  testResult: DestinationTestResponse | null;
  vaultDetectMessage: string | null;
};

export function DestinationFormSections(props: DestinationFormSectionsProps) {
  if (props.activeDestination.type === "notion") {
    return <NotionDestinationForm {...props} />;
  }
  if (props.activeDestination.type === "obsidian") {
    return <ObsidianDestinationForm {...props} />;
  }
  return <RssDestinationForm editConfig={props.editConfig} isEditing={props.isEditing} setEditConfig={props.setEditConfig} />;
}

function NotionDestinationForm({
  editConfig,
  isEditing,
  setEditConfig,
}: Pick<DestinationFormSectionsProps, "editConfig" | "isEditing" | "setEditConfig">) {
  const normalizeEditConfigNotionId = (field: "database_id" | "parent_page_id") => {
    setEditConfig((current) => {
      const raw = String(current[field] || "");
      if (!raw) {
        return current;
      }
      const normalized = normalizeNotionField(raw);
      return normalized === raw ? current : { ...current, [field]: normalized };
    });
  };

  return (
    <>
      <Card className="border-border/60 bg-background/80 shadow-none">
        <CardHeader className="pb-4">
          <CardTitle className="text-base font-semibold">凭证与目标</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <FormField label="集成令牌" hint="使用 Notion 内部集成生成的 token。">
            <SecretField
              label="集成令牌 (Token)"
              value={editConfig.token || ""}
              onChange={(value) => setEditConfig((current) => ({ ...current, token: value }))}
              placeholder="secret_..."
              inputClassName={getInputClassName(isEditing)}
              readOnly={!isEditing}
            />
          </FormField>
          <FormField label="目标 Database ID" hint="可以直接粘贴数据库链接，系统会自动提取 ID。">
            <input
              value={editConfig.database_id || ""}
              onChange={(event) => setEditConfig((current) => ({ ...current, database_id: event.target.value }))}
              onBlur={isEditing ? () => normalizeEditConfigNotionId("database_id") : undefined}
              readOnly={!isEditing}
              placeholder="粘贴 Notion 数据库链接或 ID"
              className={getInputClassName(isEditing)}
            />
          </FormField>
          <FormField label="父级 Page ID" hint="如果要把报告写成普通页面的子页面，可以在这里指定父页面。">
            <input
              value={editConfig.parent_page_id || ""}
              onChange={(event) => setEditConfig((current) => ({ ...current, parent_page_id: event.target.value }))}
              onBlur={isEditing ? () => normalizeEditConfigNotionId("parent_page_id") : undefined}
              readOnly={!isEditing}
              placeholder="粘贴 Notion 页面链接或 ID"
              className={getInputClassName(isEditing)}
            />
          </FormField>
        </CardContent>
      </Card>

      <Card className="border-border/60 bg-background/80 shadow-none">
        <CardHeader className="pb-4">
          <CardTitle className="text-base font-semibold">字段映射</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-5 md:grid-cols-2">
          <FormField label="标题属性" hint="数据库中作为标题列的属性名，例如 Name。">
            <input
              value={editConfig.title_property || "Name"}
              onChange={(event) => setEditConfig((current) => ({ ...current, title_property: event.target.value }))}
              readOnly={!isEditing}
              placeholder="Name"
              className={getInputClassName(isEditing)}
            />
          </FormField>
          <FormField label="摘要属性" hint="用于写入报告摘要与评论的属性名。">
            <input
              value={editConfig.summary_property || "TL;DR"}
              onChange={(event) =>
                setEditConfig((current) => ({ ...current, summary_property: event.target.value }))
              }
              readOnly={!isEditing}
              placeholder="TL;DR"
              className={getInputClassName(isEditing)}
            />
          </FormField>
        </CardContent>
      </Card>
    </>
  );
}

function ObsidianDestinationForm({
  activeDestination,
  detectedVaults,
  detectingVaultPath,
  editConfig,
  isEditing,
  onDetectObsidianVaultPath,
  setEditConfig,
  testError,
  testResult,
  vaultDetectMessage,
}: DestinationFormSectionsProps) {
  const mode = getObsidianMode(editConfig);

  return (
    <>
      <Card className="border-border/60 bg-background/80 shadow-none">
        <CardHeader className="pb-4">
          <CardTitle className="text-base font-semibold">连接方式</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <label
              className={cn(
                "rounded-2xl border px-4 py-4 transition-all relative overflow-hidden",
                isEditing ? "cursor-pointer hover:border-slate-400 hover:bg-slate-50/70" : "cursor-default opacity-90",
                mode === "rest" ? "border-slate-900 bg-slate-50 ring-1 ring-inset ring-slate-900" : "border-border/70 bg-background",
              )}
            >
              <input
                type="radio"
                name={`obsidian-mode-${activeDestination.id}`}
                className="sr-only"
                checked={mode === "rest"}
                disabled={!isEditing}
                onChange={() => setEditConfig((current) => ({ ...current, mode: "rest" }))}
              />
              <div className="flex items-center justify-between">
                <div className={cn("text-sm font-semibold", mode === "rest" ? "text-foreground" : "")}>REST API</div>
                <div className={cn("flex h-4 w-4 shrink-0 flex-col items-center justify-center rounded-full border", mode === "rest" ? "border-slate-900" : "border-slate-300 bg-background")}>
                  {mode === "rest" && <div className="h-2 w-2 rounded-full bg-slate-900" />}
                </div>
              </div>
              <p className={cn("mt-2 text-xs leading-5", mode === "rest" ? "text-slate-600" : "text-muted-foreground")}>
                通过本地插件写入，适合已经启用 Local REST API 的场景。
              </p>
            </label>
            <label
              className={cn(
                "rounded-2xl border px-4 py-4 transition-all relative overflow-hidden",
                isEditing ? "cursor-pointer hover:border-slate-400 hover:bg-slate-50/70" : "cursor-default opacity-90",
                mode === "file" ? "border-slate-900 bg-slate-50 ring-1 ring-inset ring-slate-900" : "border-border/70 bg-background",
              )}
            >
              <input
                type="radio"
                name={`obsidian-mode-${activeDestination.id}`}
                className="sr-only"
                checked={mode === "file"}
                disabled={!isEditing}
                onChange={() => setEditConfig((current) => ({ ...current, mode: "file" }))}
              />
              <div className="flex items-center justify-between">
                <div className={cn("text-sm font-semibold", mode === "file" ? "text-foreground" : "")}>本地文件</div>
                <div className={cn("flex h-4 w-4 shrink-0 flex-col items-center justify-center rounded-full border", mode === "file" ? "border-slate-900" : "border-slate-300 bg-background")}>
                  {mode === "file" && <div className="h-2 w-2 rounded-full bg-slate-900" />}
                </div>
              </div>
              <p className={cn("mt-2 text-xs leading-5", mode === "file" ? "text-slate-600" : "text-muted-foreground")}>
                直接写入 vault 目录，适合本地文件同步工作流。
              </p>
            </label>
          </div>

          {mode === "rest" ? (
            <div className="grid gap-5">
              <FormField label="本地 REST API URL" hint="推荐使用插件默认地址 https://127.0.0.1:27124。">
                <input
                  value={editConfig.api_url || ""}
                  onChange={(event) => setEditConfig((current) => ({ ...current, api_url: event.target.value }))}
                  readOnly={!isEditing}
                  placeholder="https://127.0.0.1:27124"
                  className={getInputClassName(isEditing)}
                />
              </FormField>
              <FormField label="API Key" hint="来自 Obsidian Local REST API 插件设置页。">
                <SecretField
                  label="API Key"
                  value={editConfig.api_key || ""}
                  onChange={(value) => setEditConfig((current) => ({ ...current, api_key: value }))}
                  placeholder="来自 Obsidian 本地 REST API 设置"
                  inputClassName={getInputClassName(isEditing)}
                  readOnly={!isEditing}
                />
              </FormField>
            </div>
          ) : (
            <div className="grid gap-5">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <label className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    Vault 路径
                  </label>
                  <Button
                    type="button"
                    variant="outline"
                    className="rounded-xl"
                    disabled={detectingVaultPath}
                    onClick={onDetectObsidianVaultPath}
                  >
                    {detectingVaultPath ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        检测中
                      </>
                    ) : (
                      "自动检测路径"
                    )}
                  </Button>
                </div>
                <div className="space-y-3">
                  <input
                    value={editConfig.vault_path || ""}
                    onChange={(event) => setEditConfig((current) => ({ ...current, vault_path: event.target.value }))}
                    readOnly={!isEditing}
                    placeholder="/Users/leo/Documents/MyVault"
                    className={getInputClassName(isEditing)}
                  />
                  <p className="text-xs leading-5 text-muted-foreground">指向 Obsidian vault 根目录。</p>
                  {vaultDetectMessage && (
                    <p className="text-xs leading-5 text-emerald-600 animate-in fade-in slide-in-from-top-1 duration-300">
                      {vaultDetectMessage}
                    </p>
                  )}
                </div>
              </div>

              {detectedVaults.length > 1 ? (
                <FormField label="检测到的 Vault" hint="如果本机打开了多个 vault，可以在这里切换。">
                  <select
                    value={editConfig.vault_path || ""}
                    onChange={(event) => setEditConfig((current) => ({ ...current, vault_path: event.target.value }))}
                    disabled={!isEditing}
                    className={getInputClassName(isEditing)}
                  >
                    {detectedVaults.map((vault) => (
                      <option key={vault.path} value={vault.path}>
                        {vault.open ? "当前打开 · " : ""}
                        {vault.name} · {vault.path}
                      </option>
                    ))}
                  </select>
                </FormField>
              ) : null}
            </div>
          )}

          <FormField label="目标文件夹" hint="例如 AI Daily/、客户周报/，为空则直接写到根目录。">
            <input
              value={editConfig.target_folder || ""}
              onChange={(event) => setEditConfig((current) => ({ ...current, target_folder: event.target.value }))}
              readOnly={!isEditing}
              placeholder="例如：AI Daily/"
              className={getInputClassName(isEditing)}
            />
          </FormField>
        </CardContent>
      </Card>

      {isEditing && (testResult || testError) ? (
        <div
          className={cn(
            "rounded-2xl border px-4 py-3 text-sm",
            testResult?.success ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-600",
          )}
        >
          <div className="font-medium">{testResult?.message || testError}</div>
          {testResult?.success ? (
            <div className="mt-1 text-xs opacity-80">
              {testResult.mode || "rest"} · {testResult.latency_ms ?? 0} ms
              {testResult.checked_target ? ` · ${testResult.checked_target}` : ""}
            </div>
          ) : null}
        </div>
      ) : null}
    </>
  );
}

function RssDestinationForm({
  editConfig,
  isEditing,
  setEditConfig,
}: Pick<DestinationFormSectionsProps, "editConfig" | "isEditing" | "setEditConfig">) {
  return (
    <Card className="border-border/60 bg-background/80 shadow-none">
      <CardHeader className="pb-4">
        <CardTitle className="text-base font-semibold">订阅源配置</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-5">
        <FormField label="订阅地址" hint="把这个地址添加到 Feedly、Reeder 等阅读器即可。">
          <div className="flex items-center gap-2">
            <input
              readOnly
              value={editConfig.feed_url || "http://localhost:8000/api/v1/feed.xml"}
              className={cn(inputClassName, "bg-muted/40 text-muted-foreground")}
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="rounded-xl"
              onClick={() => void navigator.clipboard?.writeText(editConfig.feed_url || "")}
            >
              <Copy className="h-4 w-4" />
            </Button>
          </div>
        </FormField>
        <FormField label="站点地址" hint="阅读器中打开条目时跳转到的站点地址。">
            <input
              value={editConfig.site_url || ""}
              onChange={(event) => setEditConfig((current) => ({ ...current, site_url: event.target.value }))}
              readOnly={!isEditing}
              placeholder="http://localhost:3018"
              className={getInputClassName(isEditing)}
            />
          </FormField>
          <FormField label="订阅标题" hint="显示在 RSS 阅读器中的频道名称。">
            <input
              value={editConfig.feed_title || ""}
              onChange={(event) => setEditConfig((current) => ({ ...current, feed_title: event.target.value }))}
              readOnly={!isEditing}
              placeholder="LexDeepResearch Reports"
              className={getInputClassName(isEditing)}
            />
          </FormField>
          <FormField label="频道简介" hint="用一句话说明这条订阅主要承载什么内容。">
            <input
              value={editConfig.feed_description || ""}
              onChange={(event) => setEditConfig((current) => ({ ...current, feed_description: event.target.value }))}
              readOnly={!isEditing}
              placeholder="Latest generated reports from LexDeepResearch."
              className={getInputClassName(isEditing)}
            />
          </FormField>
          <FormField label="保留条目数" hint="订阅输出中保留的历史项目数量。">
            <input
              type="number"
              min={1}
              value={editConfig.max_items || "20"}
              onChange={(event) => setEditConfig((current) => ({ ...current, max_items: event.target.value }))}
              readOnly={!isEditing}
              className={getInputClassName(isEditing)}
            />
          </FormField>
      </CardContent>
    </Card>
  );
}

function getInputClassName(isEditing: boolean) {
  return cn(inputClassName, !isEditing && "bg-muted/30 text-muted-foreground focus-visible:ring-0");
}
