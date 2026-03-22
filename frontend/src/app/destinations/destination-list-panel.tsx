"use client";

import { Loader2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Destination } from "@/lib/api";

import { FILTER_OPTIONS, getDestinationSummary, getTypeLabel, type DestinationFilter } from "@/app/destinations/utils";
import { getTypeIcon } from "@/app/destinations/shared";

type DestinationListPanelProps = {
  activeDestinationId: string | null;
  filter: DestinationFilter;
  filteredDestinations: Destination[];
  loading: boolean;
  onFilterChange: (filter: DestinationFilter) => void;
  onSelect: (destinationId: string) => void;
};

export function DestinationListPanel({
  activeDestinationId,
  filter,
  filteredDestinations,
  loading,
  onFilterChange,
  onSelect,
}: DestinationListPanelProps) {
  return (
    <Card className="overflow-hidden border-slate-200/80 bg-[linear-gradient(180deg,rgba(248,250,252,0.98),rgba(255,255,255,0.96))]">
      <CardHeader className="border-b border-border/60 bg-slate-50/80">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.22em] text-muted-foreground">落盘点列表</p>
            <CardTitle className="mt-2 text-lg font-semibold">按实例管理发布目标</CardTitle>
          </div>
          <div className="rounded-full bg-slate-900 px-3 py-1 text-xs font-medium text-white">
            {filteredDestinations.length}
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {FILTER_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => onFilterChange(option.value)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                filter === option.value
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-border/70 bg-background text-muted-foreground hover:text-foreground",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="p-3">
        {loading ? (
          <div className="flex items-center gap-2 rounded-2xl px-3 py-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            正在加载落盘点...
          </div>
        ) : null}

        {!loading && !filteredDestinations.length ? (
          <div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 px-4 py-8 text-center">
            <p className="text-sm font-medium text-foreground">当前筛选下还没有落盘点</p>
            <p className="mt-2 text-sm text-muted-foreground">可以先新增一个实例，再绑定到对应任务。</p>
          </div>
        ) : null}

        {!loading ? (
          <div className="space-y-2">
            {filteredDestinations.map((destination) => {
              const selected = destination.id === activeDestinationId;
              return (
                <div
                  key={destination.id}
                  className={cn(
                    "group rounded-2xl border transition-all",
                    selected
                      ? "border-slate-900 bg-slate-50 shadow-sm ring-1 ring-inset ring-slate-900 text-foreground"
                      : "border-border/70 bg-background hover:border-slate-300 hover:bg-slate-50/70",
                  )}
                >
                  <button
                    type="button"
                    aria-label={`${destination.name} 落盘点`}
                    aria-pressed={selected}
                    onClick={() => onSelect(destination.id)}
                    className="flex w-full items-start gap-3 px-4 py-4 text-left"
                  >
                    <div
                      className={cn(
                        "mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border",
                        destination.type === "notion"
                          ? "border-slate-200 bg-white text-slate-900"
                          : destination.type === "obsidian"
                            ? "border-violet-200 bg-violet-50 text-violet-700"
                            : "border-amber-200 bg-amber-50 text-amber-700",
                        selected && "shadow-sm"
                      )}
                    >
                      {getTypeIcon(destination.type)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-sm font-semibold">{destination.name}</span>
                        <span
                          className={cn(
                            "inline-flex h-2.5 w-2.5 rounded-full",
                            destination.enabled ? "bg-emerald-500" : "bg-slate-300",
                          )}
                        />
                      </div>
                      <p className={cn("mt-1 text-xs", selected ? "text-slate-600 font-medium" : "text-muted-foreground")}>
                        {getTypeLabel(destination.type)}
                      </p>
                      <p className={cn("mt-3 truncate text-xs leading-5", selected ? "text-slate-700" : "text-slate-600")}>
                        {getDestinationSummary(destination)}
                      </p>
                    </div>
                  </button>
                </div>
              );
            })}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
