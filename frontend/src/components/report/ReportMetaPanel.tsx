"use client";

import type { ReportTopic } from "@/lib/api";

interface ReportMetaPanelProps {
  eventCount: number;
  sourceCount: number;
  topics: ReportTopic[];
  onTopicSelect: (topic: string) => void;
}

export function ReportMetaPanel({
  eventCount,
  sourceCount,
  topics,
  onTopicSelect,
}: ReportMetaPanelProps) {
  return (
    <aside className="rounded-lg border border-border/50 bg-card p-4">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Meta</h3>

      <div className="space-y-1 text-sm text-muted-foreground">
        <p>{eventCount} events</p>
        <p>{sourceCount} sources</p>
      </div>

      <div className="mt-4 space-y-2">
        <p className="text-xs font-medium text-muted-foreground">Topics</p>
        <div className="flex flex-wrap gap-2">
          {topics.map((topic) => (
            <button
              key={topic.name}
              type="button"
              className="rounded-md border border-border/50 bg-muted/30 px-2 py-1 text-xs hover:bg-muted"
              onClick={() => onTopicSelect(topic.name)}
            >
              {topic.name}
            </button>
          ))}
          {topics.length === 0 && <p className="text-xs text-muted-foreground">No topics</p>}
        </div>
      </div>
    </aside>
  );
}
