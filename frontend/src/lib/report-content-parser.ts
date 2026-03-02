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
const SUMMARY_HINT = "全局总结与锐评";
const OVERVIEW_HINT = "概览";

function normalize(text: string): string {
  return String(text ?? "").trim();
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
  if (title.includes(SUMMARY_HINT)) return "summary";
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
      const title = normalize(headingMatch[2]);
      current = {
        id: createSectionId(title, idCounts),
        level,
        title,
        kind: classifyTitle(title),
        eventIndex: parseEventIndex(title),
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
