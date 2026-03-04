"use client";

import { cn } from "@/lib/utils";
import type { OutlineItem } from "@/lib/report-content-parser";

interface ReportOutlineProps {
  items: OutlineItem[];
  activeId: string | null;
  onNavigate: (id: string) => void;
}

export function ReportOutline({ items, activeId, onNavigate }: ReportOutlineProps) {
  if (items.length === 0) return null;

  return (
    <nav aria-label="Report outline">
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item.id}>
            <a
              href={`#${item.id}`}
              aria-current={activeId === item.id ? "true" : undefined}
              onClick={(event) => {
                event.preventDefault();
                onNavigate(item.id);
              }}
              className={cn(
                "block rounded-md px-2 py-1.5 text-sm transition-colors",
                item.level === 2 ? "ml-2" : "",
                activeId === item.id ? "bg-muted text-foreground font-medium" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {item.title}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
