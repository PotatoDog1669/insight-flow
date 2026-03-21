"use client";

import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

import type { ReportEvent, ReportTopic } from "@/lib/api";
import { canonicalizeReportContent, parseReportContent, type ParsedSection } from "@/lib/report-content-parser";

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
const SECTION_META_LINE_RE = /^(关键词|关键指标)\s*[:：]/i;

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

function isBlockquoteLine(line: string): boolean {
  return line.trimStart().startsWith(">");
}

function removeDuplicatedIntroCallout(lines: string[]): string[] {
  let cursor = 0;
  while (cursor < lines.length && !lines[cursor].trim()) {
    cursor += 1;
  }
  if (cursor >= lines.length || !isBlockquoteLine(lines[cursor])) {
    return lines;
  }

  let firstEnd = cursor;
  while (firstEnd < lines.length && isBlockquoteLine(lines[firstEnd])) {
    firstEnd += 1;
  }
  const firstBlockEnd = firstEnd;

  while (firstEnd < lines.length && !lines[firstEnd].trim()) {
    firstEnd += 1;
  }
  if (firstEnd >= lines.length || !isBlockquoteLine(lines[firstEnd])) {
    return lines;
  }

  let secondEnd = firstEnd;
  while (secondEnd < lines.length && isBlockquoteLine(lines[secondEnd])) {
    secondEnd += 1;
  }
  const trailing = lines.slice(secondEnd);
  if (trailing.length > 0 && trailing[0].trim()) {
    return [...lines.slice(0, firstBlockEnd), "", ...trailing];
  }
  return [...lines.slice(0, firstBlockEnd), ...trailing];
}

function sectionMarkdown(section: ParsedSection): string {
  const filteredLines = section.lines.filter((line) => !SECTION_META_LINE_RE.test(line.trim()));
  if (section.kind !== "event") {
    return filteredLines.join("\n");
  }
  return removeDuplicatedIntroCallout(filteredLines).join("\n");
}

const markdownComponents: Components = {
  p: ({ children }) => <p className="mt-4 text-sm leading-7 text-muted-foreground">{children}</p>,
  ul: ({ children }) => <ul className="mt-4 list-disc space-y-1 pl-6 text-sm leading-6 text-muted-foreground">{children}</ul>,
  ol: ({ children }) => <ol className="mt-4 list-decimal space-y-1 pl-6 text-sm leading-6 text-muted-foreground">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  a: ({ href, children }) => {
    const link = String(href ?? "").trim();
    if (link.startsWith("#")) {
      return (
        <a
          href={link}
          className="text-blue-600 hover:underline"
          onClick={(event) => {
            event.preventDefault();
            const targetId = link.slice(1);
            if (!targetId) return;
            const target = document.getElementById(targetId);
            if (target) {
              target.scrollIntoView({ behavior: "smooth", block: "start" });
            }
            if (typeof window !== "undefined") {
              window.history.replaceState(null, "", `#${targetId}`);
            }
          }}
        >
          {children}
        </a>
      );
    }
    if (link.startsWith("/")) {
      return (
        <a href={link} className="text-blue-600 hover:underline">
          {children}
        </a>
      );
    }
    return (
      <a href={link} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
        {children}
      </a>
    );
  },
  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
  blockquote: ({ children }) => (
    <blockquote className="mt-4 border-l-4 border-blue-500 bg-blue-50/50 dark:bg-blue-900/20 px-4 py-3 italic text-muted-foreground">
      {children}
    </blockquote>
  ),
  h3: ({ children }) => <h3 className="mt-6 text-lg font-medium tracking-tight text-foreground">{children}</h3>,
  hr: () => <hr className="my-6 border-border/60" />,
  code: ({ children }) => <code className="rounded bg-muted/50 px-1.5 py-0.5 text-xs font-mono">{children}</code>,
  table: ({ children }) => (
    <div className="mt-4 w-full overflow-auto">
      <table className="w-full text-sm text-left">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border-b border-border/60 px-4 py-2 font-medium">{children}</th>,
  td: ({ children }) => <td className="border-b border-border/60 px-4 py-2 text-muted-foreground">{children}</td>,
};

function headingClass(level: 1 | 2): string {
  return level === 1 ? "text-3xl font-bold tracking-tight" : "text-xl font-semibold tracking-tight";
}

export function ReportDocument({ content, events, globalTldr, topics }: ReportDocumentProps) {
  const effectiveContent = useMemo(
    () => canonicalizeReportContent(content, events, globalTldr),
    [content, events, globalTldr]
  );
  const parsed = useMemo(() => parseReportContent(effectiveContent), [effectiveContent]);
  const [metaExpanded, setMetaExpanded] = useState(false);

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
  if (!effectiveContent.trim()) {
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
        const HeadingTag = section.level === 1 ? "h1" : "h2";
        const bodyMarkdown = sectionMarkdown(section);

        if (isEvent) {
          return (
            <section key={section.id} id={section.id} className="space-y-3 mt-10">
              <HeadingTag className={headingClass(section.level)}>
                {section.title}
              </HeadingTag>

              <div id={`${section.id}-panel`} className="space-y-3 mt-4">

                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeSanitize]}
                  components={markdownComponents}
                >
                  {bodyMarkdown}
                </ReactMarkdown>
              </div>
            </section>
          );
        }

        return (
          <section key={section.id} id={section.id} className="space-y-3">
            <HeadingTag className={headingClass(section.level)}>{section.title}</HeadingTag>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeSanitize]}
              components={markdownComponents}
            >
              {bodyMarkdown}
            </ReactMarkdown>
            {section.kind === "summary" && globalTldr && !bodyMarkdown.trim() && (
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
                  className="flex w-full items-center justify-between text-left text-sm font-medium rounded-md px-2 py-1 hover:bg-muted/40 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-expanded={metaExpanded}
                  aria-controls={`${section.id}-runtime-meta`}
                  onClick={() => setMetaExpanded((prev) => !prev)}
                >
                  <span>运行元信息</span>
                  <span className="text-xs text-muted-foreground">{metaExpanded ? "Hide" : "Show"}</span>
                </button>
                {metaExpanded && (
                  <div id={`${section.id}-runtime-meta`} className="mt-3 space-y-1 text-xs text-muted-foreground">
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
