"use client";

import { useMemo, useState } from "react";

import type { ReportEvent, ReportTopic } from "@/lib/api";
import { parseReportContent, type ParsedSection } from "@/lib/report-content-parser";

interface ReportDocumentProps {
  content: string;
  events: ReportEvent[];
  globalTldr: string;
  topics: ReportTopic[];
}

interface RuntimeMetaSplit {
  metaLines: string[];
  contentLines: string[];
}

const RUNTIME_META_RE =
  /^(生成时间|样本输入数|加工后事件数|filter provider|keywords provider|report provider)/i;

function splitRuntimeMetaLines(lines: string[]): RuntimeMetaSplit {
  if (lines.length === 0) return { metaLines: [], contentLines: lines };
  let cursor = 0;
  while (cursor < lines.length) {
    const trimmed = lines[cursor].trim();
    if (!trimmed) {
      cursor += 1;
      continue;
    }
    if (!RUNTIME_META_RE.test(trimmed)) break;
    cursor += 1;
  }

  const metaLines = lines.slice(0, cursor).filter((line) => line.trim());
  if (metaLines.length < 2) return { metaLines: [], contentLines: lines };
  return {
    metaLines,
    contentLines: lines.slice(cursor),
  };
}

function renderInlineText(text: string, key: string) {
  const markdownLink = text.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)(.*)$/);
  if (markdownLink) {
    const [, label, href, suffix] = markdownLink;
    return (
      <span key={key}>
        <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
          {label}
        </a>
        {suffix}
      </span>
    );
  }

  if (/^https?:\/\//.test(text)) {
    return (
      <a key={key} href={text} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
        {text}
      </a>
    );
  }
  return <span key={key}>{text}</span>;
}

import React from "react";

function renderSectionBody(lines: string[], keyPrefix: string) {
  const nodes: React.JSX.Element[] = [];
  let listBuffer: string[] = [];

  const flushList = () => {
    if (listBuffer.length === 0) return;
    const listKey = `${keyPrefix}-list-${nodes.length}`;
    nodes.push(
      <ul key={listKey} className="list-disc space-y-1 pl-6 text-sm leading-6 text-muted-foreground">
        {listBuffer.map((item, idx) => (
          <li key={`${listKey}-${idx}`}>{renderInlineText(item, `${listKey}-item-${idx}`)}</li>
        ))}
      </ul>
    );
    listBuffer = [];
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      flushList();
      continue;
    }
    if (line.startsWith("- ")) {
      listBuffer.push(line.slice(2).trim());
      continue;
    }
    flushList();
    nodes.push(
      <p key={`${keyPrefix}-p-${nodes.length}`} className="text-sm leading-7 text-muted-foreground">
        {renderInlineText(line, `${keyPrefix}-p-inline-${nodes.length}`)}
      </p>
    );
  }
  flushList();
  return nodes;
}

function headingClass(level: 1 | 2): string {
  return level === 1 ? "text-3xl font-bold tracking-tight" : "text-xl font-semibold tracking-tight";
}

export function ReportDocument({ content, events, globalTldr, topics }: ReportDocumentProps) {
  const parsed = useMemo(() => parseReportContent(content), [content]);
  const [metaExpanded, setMetaExpanded] = useState(false);
  const [expandedEvents, setExpandedEvents] = useState<Record<string, boolean>>({});

  const eventByIndex = useMemo(() => {
    const map = new Map<number, ReportEvent>();
    for (const event of events) map.set(event.index, event);
    return map;
  }, [events]);

  const first = parsed.sections[0] ?? null;
  const metaSplit = useMemo(
    () => splitRuntimeMetaLines(first?.lines ?? []),
    [first?.lines]
  );

  const sections: ParsedSection[] = useMemo(() => {
    if (!first) return parsed.sections;
    return [
      { ...first, lines: metaSplit.contentLines },
      ...parsed.sections.slice(1),
    ];
  }, [first, metaSplit.contentLines, parsed.sections]);

  if (!content.trim()) {
    return (
      <div className="rounded-xl border border-dashed border-border/60 p-6 text-sm text-muted-foreground">
        Report content is empty.
      </div>
    );
  }

  return (
    <article className="space-y-8">
      {sections.map((section, idx) => {
        const isEvent = section.kind === "event";
        const eventData = section.eventIndex !== null ? eventByIndex.get(section.eventIndex) : undefined;
        const isEventExpanded = Boolean(expandedEvents[section.id]);
        const HeadingTag = section.level === 1 ? "h1" : "h2";

        if (isEvent) {
          return (
            <section key={section.id} id={section.id} className="rounded-xl border border-border/50 bg-card p-5">
              <HeadingTag className={headingClass(section.level)}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between text-left"
                  aria-expanded={isEventExpanded}
                  onClick={() => {
                    setExpandedEvents((prev) => ({ ...prev, [section.id]: !prev[section.id] }));
                  }}
                >
                  <span>{section.title}</span>
                  <span className="text-xs text-muted-foreground">{isEventExpanded ? "Collapse" : "Expand"}</span>
                </button>
              </HeadingTag>

              {isEventExpanded && (
                <div className="mt-4 space-y-3">
                  {eventData && (
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span>{eventData.source_count} sources</span>
                      {eventData.published_at && <span>{new Date(eventData.published_at).toLocaleDateString()}</span>}
                    </div>
                  )}
                  {renderSectionBody(section.lines, section.id)}
                  {eventData && eventData.keywords.length > 0 && (
                    <div className="flex flex-wrap gap-2 pt-1">
                      {eventData.keywords.slice(0, 8).map((keyword) => (
                        <span
                          key={`${section.id}-kw-${keyword}`}
                          className="rounded-md border border-border/50 bg-muted/40 px-2 py-0.5 text-xs text-muted-foreground"
                        >
                          {keyword}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </section>
          );
        }

        return (
          <section key={section.id} id={section.id} className="space-y-3">
            <HeadingTag className={headingClass(section.level)}>{section.title}</HeadingTag>
            {renderSectionBody(section.lines, section.id)}
            {section.kind === "summary" && globalTldr && (
              <div className="rounded-lg border border-border/60 bg-muted/30 p-4 text-sm leading-7 text-foreground">
                {globalTldr}
              </div>
            )}
            {section.kind === "overview" && topics.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {topics.map((topic) => (
                  <span
                    key={`${section.id}-topic-${topic.name}`}
                    className="rounded-md border border-border/50 bg-muted/40 px-2 py-0.5 text-xs text-muted-foreground"
                  >
                    {topic.name}
                  </span>
                ))}
              </div>
            )}
            {idx === 0 && metaSplit.metaLines.length > 0 && (
              <div className="rounded-lg border border-border/50 bg-muted/20 p-3">
                <button
                  type="button"
                  className="flex w-full items-center justify-between text-left text-sm font-medium"
                  aria-expanded={metaExpanded}
                  onClick={() => setMetaExpanded((prev) => !prev)}
                >
                  <span>运行元信息</span>
                  <span className="text-xs text-muted-foreground">{metaExpanded ? "Hide" : "Show"}</span>
                </button>
                {metaExpanded && (
                  <div className="mt-3 space-y-1 text-xs text-muted-foreground">
                    {metaSplit.metaLines.map((line, lineIdx) => (
                      <p key={`${section.id}-meta-${lineIdx}`}>{line}</p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>
        );
      })}
    </article>
  );
}
