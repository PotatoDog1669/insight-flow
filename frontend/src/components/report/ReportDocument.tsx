"use client";

import { Children, isValidElement, useMemo, useState, type ReactElement, type ReactNode } from "react";
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
  suppressFirstHeading?: boolean;
}

interface RuntimeMetaSplit {
  metaLines: string[];
  contentLines: string[];
}

interface HeadingStyleOptions {
  isEditorialGroup?: boolean;
}

const DUPLICATED_ARXIV_IMAGE_RE =
  /(https?:\/\/arxiv\.org\/html\/)(\d{4}\.\d{4,5}v\d+)\/\2\//i;
const RUNTIME_META_RE =
  /^(生成时间|样本输入数|加工后事件数|filter provider|keywords provider|report provider)/i;
const SECTION_META_LINE_RE = /^(关键词|关键指标)\s*[:：]/i;
const PAPER_META_LABELS = ["作者", "机构", "链接", "来源"] as const;
const PAPER_BODY_LABELS = ["核心方法", "对比方法 / Baselines", "借鉴意义"] as const;

function isElementWithChildren(node: ReactNode): node is ReactElement<{ children?: ReactNode }> {
  return isValidElement<{ children?: ReactNode }>(node);
}

function isElementWithSrc(node: ReactNode): node is ReactElement<{ src?: string }> {
  return isValidElement<{ src?: string }>(node);
}

function normalizeRenderableImageUrl(src: string): string {
  const value = src.trim();
  if (!value) return "";
  return value.replace(DUPLICATED_ARXIV_IMAGE_RE, "$1$2/");
}

function MarkdownImage({ src, alt }: { src?: string | null; alt?: string | null }) {
  const [failed, setFailed] = useState(false);
  const normalizedSrc = normalizeRenderableImageUrl(String(src ?? ""));

  if (!normalizedSrc) return null;
  if (failed) {
    return (
      <span className="mt-4 block rounded-xl border border-dashed border-border/60 bg-muted/20 px-4 py-6 text-center text-sm text-muted-foreground">
        图片加载失败
      </span>
    );
  }

  return (
    <img
      src={normalizedSrc}
      alt={String(alt ?? "")}
      className="mt-4 w-full rounded-xl border border-border/40 object-cover"
      onError={() => setFailed(true)}
    />
  );
}

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

function childText(children: ReactNode): string {
  return Children.toArray(children)
    .map((child) => {
      if (typeof child === "string") return child;
      if (isElementWithChildren(child)) return childText(child.props.children);
      return "";
    })
    .join("")
    .trim();
}

function splitMetadataLabel(children: ReactNode): {
  label: string | null;
  remainder: ReactNode[];
} {
  const nodes = Children.toArray(children);
  if (nodes.length === 0) return { label: null, remainder: nodes };

  const first = nodes[0];
  if (typeof first !== "string") {
    return { label: null, remainder: nodes };
  }

  for (const label of PAPER_META_LABELS) {
    const prefix = `${label}：`;
    if (!first.startsWith(prefix)) continue;
    const trailing = first.slice(prefix.length);
    const remainder = [...nodes.slice(1)];
    if (trailing) {
      remainder.unshift(trailing);
    }
    return { label: prefix, remainder };
  }

  return { label: null, remainder: nodes };
}

function splitBodyLabel(children: ReactNode): {
  label: ReactNode | null;
  labelText: string;
  remainder: ReactNode[];
} {
  const nodes = Children.toArray(children).filter((child) => !(typeof child === "string" && !child.trim()));
  if (nodes.length === 0) return { label: null, labelText: "", remainder: nodes };

  const first = nodes[0];
  if (!isElementWithChildren(first)) {
    return { label: null, labelText: "", remainder: nodes };
  }

  const labelText = Children.toArray(first.props.children).join("").trim();
  if (!PAPER_BODY_LABELS.includes(labelText as (typeof PAPER_BODY_LABELS)[number])) {
    return { label: null, labelText: "", remainder: nodes };
  }

  const remainder = [...nodes.slice(1)];
  const second = remainder[0];
  if (typeof second === "string" && second.startsWith("：")) {
    remainder[0] = second.slice(1);
    if (!String(remainder[0]).trim()) {
      remainder.shift();
    }
  }

  return { label: first, labelText, remainder };
}

function isImageOnlyParagraph(children: ReactNode): boolean {
  const nodes = Children.toArray(children).filter((child) => {
    return !(typeof child === "string" && !child.trim());
  });
  return (
    nodes.length === 1 &&
    isValidElement(nodes[0]) &&
    (nodes[0].type === MarkdownImage ||
      (typeof nodes[0].type === "string" && nodes[0].type === "img") ||
      (isElementWithSrc(nodes[0]) && typeof nodes[0].props.src === "string"))
  );
}

const markdownComponents: Components = {
  p: ({ children }) =>
    isImageOnlyParagraph(children) ? (
      <div className="mt-5">{children}</div>
    ) : (
      <p className="mt-4 text-sm leading-7 text-muted-foreground">{children}</p>
    ),
  ul: ({ children }) => <ul className="mt-4 space-y-1.5 pl-0 text-sm leading-6 text-muted-foreground">{children}</ul>,
  ol: ({ children }) => <ol className="mt-4 list-decimal space-y-1 pl-6 text-sm leading-6 text-muted-foreground">{children}</ol>,
  li: ({ children }) => {
    const { label, remainder } = splitMetadataLabel(children);
    if (!label) {
      const body = splitBodyLabel(children);
      if (body.label) {
        return (
          <li className="list-none rounded-xl border border-border/50 bg-muted/20 px-4 py-3 text-sm leading-7 text-muted-foreground shadow-sm">
            <span className="font-medium text-foreground">{body.label}</span>
            <span>：{body.remainder}</span>
          </li>
        );
      }
      return <li className="ml-5 list-disc">{children}</li>;
    }
    return (
      <li className="flex items-start gap-2 text-foreground/90">
        <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-foreground/35" aria-hidden="true" />
        <span className="min-w-0 leading-6">
          <strong className="font-semibold text-foreground">{label}</strong>
          {remainder}
        </span>
      </li>
    );
  },
  img: ({ src, alt }) => (
    // Render authored paper digest figures as standalone visual blocks.
    <MarkdownImage src={typeof src === "string" ? src : null} alt={typeof alt === "string" ? alt : null} />
  ),
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
  h3: ({ children }) => {
    const title = childText(children);
    const isPaperTitle = /^\d+\.\s+/.test(title);
    return (
      <h3
        className={
          isPaperTitle
            ? "mt-8 border-b border-border/50 pb-3 text-[1.35rem] font-semibold tracking-[-0.02em] text-foreground"
            : "mt-6 text-lg font-medium tracking-tight text-foreground"
        }
      >
        {children}
      </h3>
    );
  },
  hr: () => <hr className="my-8 h-px border-0 bg-gradient-to-r from-border/10 via-border/60 to-border/10" />,
  code: ({ children }) => <code className="rounded bg-muted/50 px-1.5 py-0.5 text-xs font-mono">{children}</code>,
  table: ({ children }) => (
    <div className="mt-4 w-full overflow-auto">
      <table className="w-full text-sm text-left">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border-b border-border/60 px-4 py-2 font-medium">{children}</th>,
  td: ({ children }) => <td className="border-b border-border/60 px-4 py-2 text-muted-foreground">{children}</td>,
};

function headingClass(level: 1 | 2, options: HeadingStyleOptions = {}): string {
  if (level === 1) return "text-3xl font-bold tracking-tight";
  if (options.isEditorialGroup) {
    return "text-[0.82rem] font-semibold uppercase tracking-[0.22em] text-muted-foreground";
  }
  return "text-xl font-semibold tracking-tight";
}

export function ReportDocument({ content, events, globalTldr, topics, suppressFirstHeading = false }: ReportDocumentProps) {
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
        const isEditorialGroup =
          section.level === 2 && section.kind !== "summary" && section.kind !== "overview" && section.kind !== "event";

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
            {!(suppressFirstHeading && idx === 0 && section.level === 1) && (
              <HeadingTag className={headingClass(section.level, { isEditorialGroup })}>{section.title}</HeadingTag>
            )}
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
