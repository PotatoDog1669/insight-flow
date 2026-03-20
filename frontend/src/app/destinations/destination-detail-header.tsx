"use client";

import { CheckCircle2, Loader2, Settings2, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardHeader, CardTitle } from "@/components/ui/card";
import type { Destination } from "@/lib/api";
import { cn } from "@/lib/utils";

import { getTypeIcon } from "@/app/destinations/shared";
import { getDestinationSummary, getTypeLabel } from "@/app/destinations/utils";

type DestinationDetailHeaderProps = {
  activeDestination: Destination;
  onDelete: (destination: Destination) => void;
  onEnableToggle: (destination: Destination) => void;
  onSaveConfig: () => void;
  onTestConfig: () => void;
  submitting: boolean;
  testingId: string | null;
};

export function DestinationDetailHeader({
  activeDestination,
  onDelete,
  onEnableToggle,
  onSaveConfig,
  onTestConfig,
  submitting,
  testingId,
}: DestinationDetailHeaderProps) {
  return (
    <CardHeader className="border-b border-border/60 bg-[radial-gradient(circle_at_top_left,rgba(186,230,253,0.28),transparent_42%),linear-gradient(180deg,rgba(248,250,252,0.95),rgba(255,255,255,0.94))]">
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-muted-foreground">连接详情</p>
      <div className="mt-3 flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-4">
          <div
            className={cn(
              "flex h-14 w-14 shrink-0 items-center justify-center rounded-[22px] border shadow-sm",
              activeDestination.type === "notion"
                ? "border-slate-200 bg-white text-slate-900"
                : activeDestination.type === "obsidian"
                  ? "border-violet-200 bg-violet-50 text-violet-700"
                  : "border-amber-200 bg-amber-50 text-amber-700",
            )}
          >
            {getTypeIcon(activeDestination.type, "h-5 w-5")}
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="text-2xl font-semibold tracking-tight">{activeDestination.name}</CardTitle>
              <Badge variant="outline" className="rounded-full border-border/70 bg-background/70">
                {getTypeLabel(activeDestination.type)}
              </Badge>
              <Badge
                variant="secondary"
                className={cn(
                  "rounded-full",
                  activeDestination.enabled && "bg-emerald-100 text-emerald-700 hover:bg-emerald-100",
                )}
              >
                {activeDestination.enabled ? "已启用" : "已停用"}
              </Badge>
            </div>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              {activeDestination.description || "为这个落盘点设置连接方式、目标位置和输出规则。"}
            </p>
            <div className="mt-4 flex flex-wrap gap-3 text-xs text-muted-foreground">
              <span className="rounded-full border border-border/70 bg-background/80 px-3 py-1.5">
                当前目标: {getDestinationSummary(activeDestination)}
              </span>
              {activeDestination.enabled ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-emerald-700">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  已参与同步
                </span>
              ) : null}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 rounded-full border border-border/70 bg-background/80 px-3 py-2 text-sm">
            <span className="text-muted-foreground">启用</span>
            <button
              type="button"
              aria-label={activeDestination.enabled ? "停用落盘点" : "启用落盘点"}
              onClick={() => onEnableToggle(activeDestination)}
              className={cn(
                "relative h-6 w-11 rounded-full transition-colors",
                activeDestination.enabled ? "bg-emerald-500" : "bg-slate-300",
              )}
            >
              <span
                className={cn(
                  "absolute left-1 top-1 h-4 w-4 rounded-full bg-white transition-transform",
                  activeDestination.enabled && "translate-x-5",
                )}
              />
            </button>
          </label>
          {activeDestination.type === "obsidian" ? (
            <Button
              type="button"
              variant="outline"
              className="rounded-2xl"
              disabled={testingId === activeDestination.id || submitting}
              onClick={onTestConfig}
            >
              {testingId === activeDestination.id ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  测试中
                </>
              ) : (
                "测试连接"
              )}
            </Button>
          ) : null}
          <Button
            type="button"
            variant="outline"
            className="rounded-2xl text-red-600 hover:bg-red-50 hover:text-red-600"
            onClick={() => onDelete(activeDestination)}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            删除
          </Button>
          <Button type="button" className="rounded-2xl" disabled={submitting} onClick={onSaveConfig}>
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                保存中
              </>
            ) : (
              <>
                <Settings2 className="mr-2 h-4 w-4" />
                保存并启用
              </>
            )}
          </Button>
        </div>
      </div>
    </CardHeader>
  );
}
