"use client";

import { Loader2, PencilLine, Settings2, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { CardHeader, CardTitle } from "@/components/ui/card";
import type { Destination } from "@/lib/api";
import { cn } from "@/lib/utils";

import { getTypeIcon } from "@/app/destinations/shared";
import {
  getDestinationDescription,
  getDestinationSummary,
  getDestinationSummaryLabel,
  getTypeLabel,
} from "@/app/destinations/utils";

type DestinationDetailHeaderProps = {
  activeDestination: Destination;
  editName: string;
  isEditing: boolean;
  onCancelEditing: () => void;
  onDelete: (destination: Destination) => void;
  onEdit: () => void;
  onEnableToggle: (destination: Destination) => void;
  onNameChange: (name: string) => void;
  onSaveConfig: () => void;
  onTestConfig: () => void;
  submitting: boolean;
  testingId: string | null;
};

export function DestinationDetailHeader({
  activeDestination,
  editName,
  isEditing,
  onCancelEditing,
  onDelete,
  onEdit,
  onEnableToggle,
  onNameChange,
  onSaveConfig,
  onTestConfig,
  submitting,
  testingId,
}: DestinationDetailHeaderProps) {
  return (
    <CardHeader className="border-b border-border/60 bg-card">
      <p className="text-xs font-medium uppercase tracking-[0.22em] text-muted-foreground">连接详情</p>
      <div className="mt-4 grid gap-6 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-start">
        <div className="flex items-start gap-5">
          <div
            className={cn(
              "flex h-20 w-20 shrink-0 items-center justify-center rounded-[28px] border shadow-sm",
              activeDestination.type === "notion"
                ? "border-slate-200 bg-white text-slate-900"
                : activeDestination.type === "obsidian"
                  ? "border-violet-200 bg-violet-50 text-violet-700"
                  : "border-amber-200 bg-amber-50 text-amber-700",
            )}
          >
            {getTypeIcon(activeDestination.type, "h-8 w-8")}
          </div>
          <div className="min-w-0 flex-1">
            <CardTitle className="sr-only">{editName || activeDestination.name}</CardTitle>
            <div className="space-y-4">
              <div className="min-w-0">
                <label
                  htmlFor={`destination-name-${activeDestination.id}`}
                  className="text-[11px] font-medium uppercase tracking-[0.22em] text-muted-foreground"
                >
                  实例名称
                </label>
                <input
                  id={`destination-name-${activeDestination.id}`}
                  aria-label="实例名称"
                  value={editName}
                  onChange={(event) => onNameChange(event.target.value)}
                  readOnly={!isEditing}
                  placeholder={`输入${getTypeLabel(activeDestination.type)}实例名称`}
                  className={cn(
                    "mt-2 h-auto w-full border-0 bg-transparent p-0 text-2xl font-semibold tracking-tight text-foreground shadow-none outline-none placeholder:text-muted-foreground/55 focus-visible:ring-0 sm:text-3xl",
                    !isEditing && "cursor-default",
                  )}
                />
                <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground">
                  {getDestinationDescription(activeDestination)}
                </p>
              </div>

            </div>
          </div>
        </div>

        <div className="flex flex-col gap-3 xl:items-end" data-testid="destination-actions">
          <div className="flex flex-wrap items-center gap-2 xl:justify-end">
            <label className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/88 px-3 py-2 text-sm shadow-sm">
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

            <Button
              type="button"
              variant="outline"
              className="rounded-2xl text-red-600 hover:bg-red-50 hover:text-red-600"
              onClick={() => onDelete(activeDestination)}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              删除
            </Button>

            {isEditing ? (
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
            ) : (
              <Button type="button" className="rounded-2xl" onClick={onEdit}>
                <PencilLine className="mr-2 h-4 w-4" />
                编辑配置
              </Button>
            )}
          </div>

          {isEditing ? (
            <div className="flex flex-wrap items-center gap-2 xl:justify-end">
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
              <Button type="button" variant="outline" className="rounded-2xl" onClick={onCancelEditing}>
                <X className="mr-2 h-4 w-4" />
                取消
              </Button>
            </div>
          ) : null}

          <span className="rounded-full border border-border/70 bg-background/80 px-3 py-1.5 text-xs text-muted-foreground xl:max-w-full">
            {getDestinationSummaryLabel(activeDestination)}: {getDestinationSummary(activeDestination)}
          </span>
        </div>
      </div>
    </CardHeader>
  );
}
