"use client";

import { Loader2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Destination } from "@/lib/api";
import { cn } from "@/lib/utils";

import { FormField, ModalFrame, getTypeIcon, inputClassName } from "@/app/destinations/shared";
import { getTypeLabel } from "@/app/destinations/utils";

type CreateDestinationModalProps = {
  createName: string;
  createType: Destination["type"];
  creating: boolean;
  isOpen: boolean;
  onClose: () => void;
  onCreate: () => void;
  onNameChange: (name: string) => void;
  onTypeChange: (type: Destination["type"]) => void;
};

export function CreateDestinationModal({
  createName,
  createType,
  creating,
  isOpen,
  onClose,
  onCreate,
  onNameChange,
  onTypeChange,
}: CreateDestinationModalProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <ModalFrame
      title="新增落盘点"
      description="先创建实例，再为它配置具体目录、数据库或 RSS 信息。"
      onClose={onClose}
    >
      <div className="space-y-5">
        <FormField label="类型">
          <div className="grid gap-3 sm:grid-cols-3">
            {(["notion", "obsidian", "rss"] as const).map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => onTypeChange(type)}
                className={cn(
                  "rounded-2xl border px-4 py-4 text-left transition-colors",
                  createType === type
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-border/70 bg-background hover:border-slate-300",
                )}
              >
                <div className="flex items-center gap-2 text-sm font-semibold">
                  {getTypeIcon(type)}
                  {getTypeLabel(type)}
                </div>
                <p className={cn("mt-2 text-xs leading-5", createType === type ? "text-white/75" : "text-muted-foreground")}>
                  {type === "notion" ? "数据库或页面" : type === "obsidian" ? "本地文件夹" : "独立 RSS 线路"}
                </p>
              </button>
            ))}
          </div>
        </FormField>
        <FormField label="名称" hint="建议直接写业务语义，例如 客户周报、研究仓库、日报 RSS。">
          <input
            value={createName}
            onChange={(event) => onNameChange(event.target.value)}
            placeholder="例如：研究仓库 / 客户周报 / RSS 主线"
            className={inputClassName}
          />
        </FormField>
        <div className="flex items-center justify-end gap-3">
          <Button type="button" variant="ghost" className="rounded-2xl" onClick={onClose}>
            取消
          </Button>
          <Button type="button" className="rounded-2xl" disabled={!createName.trim() || creating} onClick={onCreate}>
            {creating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                创建中
              </>
            ) : (
              "创建并配置"
            )}
          </Button>
        </div>
      </div>
    </ModalFrame>
  );
}

type DeleteDestinationModalProps = {
  deleting: boolean;
  destination: Destination | null;
  onClose: () => void;
  onDelete: () => void;
};

export function DeleteDestinationModal({ deleting, destination, onClose, onDelete }: DeleteDestinationModalProps) {
  if (!destination) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/20 backdrop-blur-[2px]"
        onClick={onClose}
      />
      {/* dialog */}
      <div className="relative w-[min(90vw,24rem)] rounded-[1.5rem] border border-slate-200/80 bg-white/98 px-7 py-6 shadow-[0_32px_80px_rgba(0,0,0,0.12)] backdrop-blur-xl">
        <h2 className="mb-1.5 text-[1.05rem] font-semibold text-slate-800">删除落盘点</h2>
        <p className="text-sm leading-6 text-slate-500">
          删除后，任务和同步弹窗里将不再显示“<span className="font-medium text-slate-700">{destination.name}</span>”。
        </p>
        
        <div className="mt-4 rounded-xl border border-red-100 bg-red-50/50 px-4 py-3 text-xs leading-5 text-red-600">
          请确认这个落盘点已经不再被使用。如果它还绑定在任务上，后续同步会失去这个目标。
        </div>

        <div className="mt-6 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-slate-200 bg-white px-5 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
          >
            取消
          </button>
          <button
            type="button"
            onClick={onDelete}
            disabled={deleting}
            className="flex items-center gap-2 rounded-full bg-red-500 px-5 py-2 text-sm font-medium text-white transition hover:bg-red-600 disabled:opacity-50"
          >
            {deleting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
            确认删除
          </button>
        </div>
      </div>
    </div>
  );
}
