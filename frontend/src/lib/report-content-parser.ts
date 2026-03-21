import type { ReportEvent } from "@/lib/api";

export type ReportSectionKind = "normal" | "meta" | "summary" | "overview" | "event";

export interface ParsedSection {
  id: string;
  level: 1 | 2;
  title: string;
  kind: ReportSectionKind;
  eventIndex: number | null;
  lines: string[];
}

export interface ParsedReportContent {
  sections: ParsedSection[];
}

export interface OutlineItem {
  id: string;
  title: string;
  level: 1 | 2;
  kind: ReportSectionKind;
  eventIndex: number | null;
}

const HEADING_RE = /^(#{1,2})\s+(.+)$/;
const EVENT_INDEX_RE = /\s#(\d{1,3})\s*$/;
const MARKDOWN_LINK_RE = /\[([^\]]+)\]\(([^)]+)\)/g;
const SUMMARY_HINTS = ["全局总结与锐评", "摘要", "执行摘要"];
const OVERVIEW_HINT = "概览";
const CANONICAL_OVERVIEW_HEADING_RE = /^##\s*概览\s*$/m;
const CANONICAL_EVENT_HEADING_RE = /^##\s+.+\s#\d{1,3}\s*$/m;
const CATEGORY_ORDER = ["要闻", "模型发布", "开发生态", "产品应用", "技术与洞察", "行业动态", "前瞻与传闻", "其他"] as const;

function normalize(text: string): string {
  return String(text ?? "").trim();
}

function normalizeHeadingTitle(title: string): string {
  return normalize(title).replace(MARKDOWN_LINK_RE, "$1").replace(/\s+/g, " ");
}

function createSectionId(title: string, counts: Map<string, number>): string {
  const base =
    normalize(title)
      .toLowerCase()
      .replace(/[`*_#[\]()]/g, "")
      .replace(/[^\w\u4e00-\u9fff]+/g, "-")
      .replace(/^-+|-+$/g, "") || "section";
  const count = (counts.get(base) ?? 0) + 1;
  counts.set(base, count);
  return count === 1 ? base : `${base}-${count}`;
}

function classifyTitle(title: string): ReportSectionKind {
  if (EVENT_INDEX_RE.test(title)) return "event";
  if (SUMMARY_HINTS.some((hint) => title.includes(hint))) return "summary";
  if (title.includes(OVERVIEW_HINT)) return "overview";
  return "normal";
}

function parseEventIndex(title: string): number | null {
  const match = title.match(EVENT_INDEX_RE);
  if (!match) return null;
  const value = Number.parseInt(match[1], 10);
  return Number.isFinite(value) ? value : null;
}

export function parseReportContent(content: string): ParsedReportContent {
  const lines = String(content ?? "").replace(/\r\n/g, "\n").split("\n");
  const sections: ParsedSection[] = [];
  const idCounts = new Map<string, number>();
  let current: ParsedSection | null = null;

  const flush = () => {
    if (!current) return;
    sections.push(current);
    current = null;
  };

  for (const rawLine of lines) {
    const headingMatch = rawLine.match(HEADING_RE);
    if (headingMatch) {
      flush();
      const hashes = headingMatch[1];
      const level = hashes.length === 1 ? 1 : 2;
      const rawTitle = normalize(headingMatch[2]);
      const title = normalizeHeadingTitle(rawTitle);
      const kind = classifyTitle(rawTitle);
      const eventIndex = parseEventIndex(rawTitle);
      const sectionId =
        kind === "event" && eventIndex !== null
          ? `event-${eventIndex}`
          : createSectionId(title, idCounts);
      current = {
        id: sectionId,
        level,
        title,
        kind,
        eventIndex,
        lines: [],
      };
      continue;
    }

    if (normalize(rawLine) === "---") {
      continue;
    }

    if (!current) {
      continue;
    }
    current.lines.push(rawLine.trimEnd());
  }

  flush();
  return { sections };
}

export function extractOutline(sections: ParsedSection[]): OutlineItem[] {
  return sections.map((section) => ({
    id: section.id,
    title: section.title,
    level: section.level,
    kind: section.kind,
    eventIndex: section.eventIndex,
  }));
}

function containsCJK(text: string): boolean {
  return /[\u4e00-\u9fff]/.test(text);
}

function compactTitle(raw: string, maxLen = 96): string {
  return raw.replace(/\s+/g, " ").replace(/[。！？.!?]+$/g, "").trim().slice(0, maxLen);
}

function deriveDisplayTitle(event: ReportEvent): string {
  const explicit = compactTitle(String(event.event_title ?? ""));
  if (explicit) return explicit;

  const current = compactTitle(String(event.title ?? ""));
  if (current && containsCJK(current)) return current;

  const tldr = compactTitle(String(event.one_line_tldr ?? ""));
  if (tldr) {
    const firstClause = tldr.split(/[，,；;：:。！？!?]/)[0]?.trim() ?? "";
    if (firstClause.length >= 6) return firstClause.slice(0, 96);
    return tldr;
  }

  return current || "未命名事件";
}

function inferDisplayCategory(event: ReportEvent): string {
  const original = String(event.category || "").trim();
  if (CATEGORY_ORDER.includes(original as (typeof CATEGORY_ORDER)[number])) return original;
  return "其他";
}

function shouldCanonicalize(content: string, events: ReportEvent[]): boolean {
  if (events.length === 0) return false;
  const text = String(content ?? "").trim();
  if (!text) return true;
  const hasCanonicalOverview = CANONICAL_OVERVIEW_HEADING_RE.test(text);
  const hasCanonicalEventHeading = CANONICAL_EVENT_HEADING_RE.test(text);
  if (hasCanonicalOverview && hasCanonicalEventHeading) return false;
  if (hasCanonicalOverview && !hasCanonicalEventHeading) return true;
  if (text.includes("执行摘要") || text.includes("详细动态")) return true;
  if (text.startsWith("# AI Daily Report")) return true;
  if (text.startsWith("# AI 早报")) return true;
  return true;
}

function buildCanonicalContent(events: ReportEvent[], summary: string = ""): string {
  if (events.length === 0) return "";
  const sortedEvents = [...events].sort((a, b) => a.index - b.index);
  const grouped = new Map<string, ReportEvent[]>();
  for (const event of sortedEvents) {
    const category = inferDisplayCategory(event);
    const list = grouped.get(category) ?? [];
    list.push(event);
    grouped.set(category, list);
  }

  const lines: string[] = [];
  const summaryText = String(summary ?? "").trim();
  if (summaryText) {
    lines.push("## 摘要", "", summaryText, "");
  }
  lines.push("## 概览", "");
  for (const category of CATEGORY_ORDER) {
    const categoryEvents = grouped.get(category);
    if (!categoryEvents || categoryEvents.length === 0) continue;
    lines.push(`### ${category}`);
    for (const event of categoryEvents) {
      const title = deriveDisplayTitle(event);
      const firstLink = event.source_links?.[0] ?? "";
      const arrow = firstLink ? ` [↗](${firstLink})` : "";
      lines.push(`- ${title}${arrow} [#${event.index}](#event-${event.index})`);
    }
  }

  for (const event of sortedEvents) {
    const title = deriveDisplayTitle(event);
    const firstLink = event.source_links?.[0] ?? "";
    const heading = firstLink ? `## [${title}](${firstLink}) #${event.index}` : `## ${title} #${event.index}`;
    const detail = String(event.detail ?? "").trim();
    const oneLine = String(event.one_line_tldr ?? "").trim();
    lines.push("---", heading);
    if (oneLine && !detail.startsWith(">")) {
      lines.push(`> ${oneLine}`);
    }
    if (detail) {
      lines.push(detail);
    }
    if ((event.source_links ?? []).length > 0) {
      lines.push("", "相关链接：");
      for (const link of event.source_links) {
        lines.push(`- ${link}`);
      }
    }
  }

  return lines.join("\n");
}

export function canonicalizeReportContent(content: string, events: ReportEvent[], summary: string = ""): string {
  if (!shouldCanonicalize(content, events)) return content;
  return buildCanonicalContent(events, summary);
}

export function normalizePaperDigestContent(content: string, metadata: Record<string, unknown>): string {
  const paperMode = typeof metadata.paper_mode === "string" ? metadata.paper_mode : "";
  if (paperMode !== "digest") return content;

  const noteLinksByTitle = new Map<string, string>();
  const rawLinks = Array.isArray(metadata.paper_note_links) ? metadata.paper_note_links : [];
  for (const item of rawLinks) {
    if (!item || typeof item !== "object") continue;
    const value = item as Record<string, unknown>;
    const title = typeof value.title === "string" ? normalizeHeadingTitle(value.title) : "";
    const reportId = typeof value.report_id === "string" ? value.report_id : "";
    if (title && reportId) {
      noteLinksByTitle.set(title, reportId);
    }
  }

  const lines = String(content ?? "").replace(/\r\n/g, "\n").split("\n");
  let currentPaperTitle = "";

  return lines
    .flatMap((line) => {
      const headingMatch = line.match(/^###\s+\d+\.\s+(.+)$/);
      if (headingMatch) {
        currentPaperTitle = normalizeHeadingTitle(headingMatch[1]);
        return [line];
      }

      const trimmed = line.trim();
      if (trimmed.startsWith("- 为什么重要：")) {
        return [];
      }
      if (trimmed.startsWith("- 阅读建议：")) {
        return [];
      }
      if (!trimmed.startsWith("- 详细笔记：")) {
        return [line];
      }
      if (trimmed.includes("](/reports/")) {
        return [line];
      }

      const reportId = noteLinksByTitle.get(currentPaperTitle);
      if (!reportId) {
        return [];
      }
      return [`- 详细笔记：[查看详细笔记](/reports/${reportId})`];
    })
    .join("\n");
}
