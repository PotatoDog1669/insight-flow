"use client";

import { SecretValue } from "@/components/secret-field";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Destination } from "@/lib/api";

import { getObsidianMode } from "@/app/destinations/utils";

type DestinationOverviewSidebarProps = {
  activeDestination: Destination;
  editConfig: Record<string, string>;
};

export function DestinationOverviewSidebar({
  activeDestination,
  editConfig,
}: DestinationOverviewSidebarProps) {
  return (
    <div className="space-y-4">
      <Card className="border-border/60 bg-slate-50/70 shadow-none">
        <CardHeader className="pb-4">
          <CardTitle className="text-base font-semibold">当前概览</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {activeDestination.type === "notion" ? (
            <>
              <div className="space-y-1">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">凭证</p>
                <SecretValue
                  label="Notion Token"
                  value={String(activeDestination.config.token || "")}
                  className="rounded-lg border border-border/70 bg-background px-2 py-1 font-mono text-xs"
                />
              </div>
              <div className="space-y-1">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">写入位置</p>
                <div className="rounded-xl border border-border/70 bg-background px-3 py-2 text-xs font-mono">
                  {String(activeDestination.config.database_id || activeDestination.config.parent_page_id || "<未配置>")}
                </div>
              </div>
            </>
          ) : null}

          {activeDestination.type === "obsidian" ? (
            <>
              <div className="space-y-1">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">模式</p>
                <div className="rounded-xl border border-border/70 bg-background px-3 py-2 text-xs font-medium">
                  {getObsidianMode(editConfig)}
                </div>
              </div>
              <div className="space-y-1">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">目标</p>
                <div className="rounded-xl border border-border/70 bg-background px-3 py-2 text-xs font-mono">
                  {getObsidianMode(editConfig) === "rest" ? editConfig.api_url || "<未配置>" : editConfig.vault_path || "<未配置>"}
                </div>
              </div>
            </>
          ) : null}

          {activeDestination.type === "rss" ? (
            <div className="space-y-1">
              <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">订阅地址</p>
              <div className="rounded-xl border border-border/70 bg-background px-3 py-2 text-xs font-mono">
                {String(activeDestination.config.feed_url || "<未配置>")}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card className="border-border/60 bg-[linear-gradient(180deg,rgba(240,249,255,0.8),rgba(255,255,255,0.9))] shadow-none">
        <CardHeader className="pb-4">
          <CardTitle className="text-base font-semibold">使用建议</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
          <p>给每条任务准备独立的落盘点，会比在任务里临时改路径更稳定。</p>
          <p>如果同类报告需要进入不同文件夹，直接新增多个实例，再在任务和同步弹窗里选择即可。</p>
        </CardContent>
      </Card>
    </div>
  );
}
