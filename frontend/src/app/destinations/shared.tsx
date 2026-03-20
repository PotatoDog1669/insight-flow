"use client";

import type { ReactNode } from "react";
import { Rss } from "lucide-react";
import { SiNotion, SiObsidian } from "react-icons/si";

import { cn } from "@/lib/utils";
import type { Destination } from "@/lib/api";

export const inputClassName =
  "flex h-10 w-full rounded-xl border border-border/70 bg-background px-3 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function getTypeIcon(type: Destination["type"], className?: string) {
  if (type === "notion") {
    return <SiNotion className={cn("h-4 w-4", className)} />;
  }
  if (type === "obsidian") {
    return <SiObsidian className={cn("h-4 w-4", className)} />;
  }
  return <Rss className={cn("h-4 w-4", className)} />;
}

export function FormField({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-2">
      <label className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">{label}</label>
      {children}
      {hint ? <p className="text-xs leading-5 text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function ModalFrame({
  title,
  description,
  children,
  onClose,
}: {
  title: string;
  description: string;
  children: ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="关闭弹窗"
        className="absolute inset-0 bg-slate-950/35 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-lg rounded-[28px] border border-border/60 bg-background p-6 shadow-2xl">
        <div className="mb-6 space-y-1">
          <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
        {children}
      </div>
    </div>
  );
}
