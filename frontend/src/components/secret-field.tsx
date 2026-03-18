"use client";

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

import { cn } from "@/lib/utils";

type SecretFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  onBlur?: () => void;
  className?: string;
  inputClassName?: string;
};

export function SecretField({
  label,
  value,
  onChange,
  placeholder,
  onBlur,
  className,
  inputClassName,
}: SecretFieldProps) {
  const [visible, setVisible] = useState(false);

  return (
    <div className={cn("relative", className)}>
      <input
        type={visible ? "text" : "password"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onBlur={onBlur}
        placeholder={placeholder}
        className={cn(
          "flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 pr-11 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
          inputClassName,
        )}
      />
      <button
        type="button"
        aria-label={visible ? `隐藏 ${label}` : `显示 ${label}`}
        title={visible ? `隐藏 ${label}` : `显示 ${label}`}
        onClick={() => setVisible((current) => !current)}
        className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}

type SecretValueProps = {
  label: string;
  value?: string;
  emptyText?: string;
  className?: string;
};

export function SecretValue({ label, value, emptyText = "<未配置>", className }: SecretValueProps) {
  const [visible, setVisible] = useState(false);

  if (!value) {
    return <span className={className}>{emptyText}</span>;
  }

  return (
    <div className="flex items-center gap-2">
      <span className={className}>{visible ? value : "••••••••••••"}</span>
      <button
        type="button"
        aria-label={visible ? `隐藏 ${label}` : `显示 ${label}`}
        title={visible ? `隐藏 ${label}` : `显示 ${label}`}
        onClick={() => setVisible((current) => !current)}
        className="flex h-6 w-6 items-center justify-center rounded border border-border/60 bg-background text-muted-foreground transition-colors hover:text-foreground"
      >
        {visible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}
