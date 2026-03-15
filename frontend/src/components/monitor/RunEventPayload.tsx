import { cn } from "@/lib/utils";

type PayloadValue = Record<string, unknown> | null | undefined;

interface RunEventPayloadProps {
  payload: PayloadValue;
}

interface TransparentLogSection {
  title: string;
  type: string;
  count?: number;
  artifact_path?: string;
  items: Array<Record<string, unknown>>;
}

interface TransparentLogPayload extends Record<string, unknown> {
  kind: "transparent_log";
  summary: Record<string, unknown>;
  sections: TransparentLogSection[];
}

const META_KEYS = [
  "source_name",
  "source_id",
  "external_id",
  "category",
  "source_count",
  "published_at",
  "reason",
  "event_title",
  "item_count",
] as const;

export function RunEventPayload({ payload }: RunEventPayloadProps) {
  if (isTransparentLogPayload(payload)) {
    return (
      <div className="pl-[calc(8ch+10ch+2rem)] pt-2 space-y-3">
        {renderSummary(payload.summary)}
        {payload.sections.map((section, index) => (
          <div key={`${section.title}-${index}`} className="rounded-md border border-neutral-800 bg-neutral-950/80">
            <div className="flex items-center justify-between gap-3 border-b border-neutral-800 px-3 py-2">
              <div className="flex items-center gap-2">
                <span className="text-neutral-100">{section.title}</span>
                <span className="rounded-full border border-neutral-700 px-1.5 py-0.5 text-[10px] text-neutral-400">
                  {section.count ?? section.items.length}
                </span>
              </div>
              {section.artifact_path ? (
                <span className="text-[10px] text-neutral-500 break-all">{section.artifact_path}</span>
              ) : null}
            </div>
            <div className="space-y-2 px-3 py-2">
              {section.items.length === 0 ? (
                <div className="rounded border border-dashed border-neutral-800 px-2 py-2 text-[11px] text-neutral-500">
                  No items
                </div>
              ) : (
                section.items.map((item, itemIndex) => (
                  <ItemCard key={buildItemKey(item, itemIndex)} item={item} sectionType={section.type} />
                ))
              )}
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <pre className="text-neutral-600 pl-[calc(8ch+10ch+2rem)] whitespace-pre-wrap break-all">
      {JSON.stringify(payload ?? {}, null, 2)}
    </pre>
  );
}

function renderSummary(summary: Record<string, unknown>) {
  const entries = Object.entries(summary).filter(([, value]) => value !== null && value !== undefined && value !== "");
  if (entries.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded border border-neutral-800 bg-neutral-900/70 px-2 py-1">
          <div className="text-[10px] uppercase tracking-wide text-neutral-500">{formatLabel(key)}</div>
          <div className="text-[11px] text-neutral-200">{formatValue(value)}</div>
        </div>
      ))}
    </div>
  );
}

function ItemCard({ item, sectionType }: { item: Record<string, unknown>; sectionType: string }) {
  const title = resolveItemTitle(item, sectionType);
  const summary = firstText(item.summary, item.detail);
  const reason = firstText(item.reason);
  const keywords = toStringArray(item.keywords);
  const clusterSourceNames = toStringArray(item.source_names);
  const nestedTitles = toNestedTitles(item.items);
  const url = firstText(item.url);

  return (
    <div className="rounded border border-neutral-800 bg-neutral-900/60 px-3 py-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[12px] text-neutral-100 break-words">{title}</div>
          {summary ? <div className="mt-1 text-[11px] text-neutral-400 break-words">{summary}</div> : null}
          {reason ? <div className="mt-1 text-[11px] text-amber-300 break-words">{reason}</div> : null}
        </div>
        {url ? (
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="shrink-0 text-[10px] text-sky-400 hover:text-sky-300"
          >
            open
          </a>
        ) : null}
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {META_KEYS.map((key) => renderMeta(key, item[key]))}
        {clusterSourceNames.map((name) => (
          <span key={`source-${name}`} className={metaPillClassName("emerald")}>
            {name}
          </span>
        ))}
        {keywords.map((keyword) => (
          <span key={`keyword-${keyword}`} className={metaPillClassName("violet")}>
            {keyword}
          </span>
        ))}
        {nestedTitles.map((nestedTitle) => (
          <span key={`nested-${nestedTitle}`} className={metaPillClassName("slate")}>
            {nestedTitle}
          </span>
        ))}
      </div>
    </div>
  );
}

function renderMeta(label: string, value: unknown) {
  const text = formatMetaValue(value);
  if (!text) {
    return null;
  }
  return (
    <span key={label} className={metaPillClassName("default")}>
      {formatLabel(label)}: {text}
    </span>
  );
}

function metaPillClassName(tone: "default" | "emerald" | "violet" | "slate") {
  return cn(
    "rounded-full border px-2 py-0.5 text-[10px]",
    tone === "emerald" && "border-emerald-900/70 bg-emerald-950/40 text-emerald-300",
    tone === "violet" && "border-violet-900/70 bg-violet-950/40 text-violet-300",
    tone === "slate" && "border-slate-800 bg-slate-950/50 text-slate-300",
    tone === "default" && "border-neutral-700 bg-neutral-950 text-neutral-400",
  );
}

function resolveItemTitle(item: Record<string, unknown>, sectionType: string) {
  if (sectionType === "candidate_clusters") {
    return firstText(item.cluster_id, item.title) ?? "Cluster";
  }
  return firstText(item.title, item.event_title) ?? "Untitled";
}

function toNestedTitles(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => {
      if (!isRecord(item)) {
        return "";
      }
      return firstText(item.title, item.event_title) ?? "";
    })
    .filter(Boolean);
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item ?? "").trim()).filter(Boolean);
}

function formatMetaValue(value: unknown) {
  if (value === null || value === undefined) {
    return "";
  }
  if (Array.isArray(value)) {
    return toStringArray(value).join(", ");
  }
  if (typeof value === "object") {
    return "";
  }
  return String(value).trim();
}

function formatValue(value: unknown) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).join(", ");
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  return String(value);
}

function formatLabel(value: string) {
  return value.replace(/_/g, " ");
}

function buildItemKey(item: Record<string, unknown>, index: number) {
  return [
    firstText(item.cluster_id, item.title, item.event_title),
    firstText(item.external_id, item.url),
    String(index),
  ]
    .filter(Boolean)
    .join("-");
}

function firstText(...values: unknown[]) {
  for (const value of values) {
    const text = typeof value === "string" ? value.trim() : "";
    if (text) {
      return text;
    }
  }
  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isTransparentLogPayload(value: PayloadValue): value is TransparentLogPayload {
  return (
    isRecord(value) &&
    value.kind === "transparent_log" &&
    isRecord(value.summary) &&
    Array.isArray(value.sections)
  );
}
