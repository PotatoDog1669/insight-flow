import { describe, expect, it } from "vitest";

import {
  canonicalizeReportContent,
  extractOutline,
  normalizePaperDigestContent,
  parseReportContent,
} from "@/lib/report-content-parser";

const SAMPLE = `## 概览
- Event A [↗](https://example.com) [#1](#event-1)

---
## Event A #1
Source：One line
关键词：\`a\`
相关链接：
- https://example.com`;

describe("report-content-parser", () => {
  it("ignores yaml frontmatter and parses the authored digest body", () => {
    const parsed = parseReportContent(`---
date: 2026-03-20
keywords:
  - gui agent
tags:
  - daily-papers
---

# 2026-03-20 论文推荐

## 总结
本期聚焦 GUI 评测。

## Safety

### 1. Paper A

**核心方法**

方法段落`);

    expect(parsed.sections.map((section) => section.title)).toEqual([
      "2026-03-20 论文推荐",
      "总结",
      "Safety",
    ]);
    expect(parsed.sections[2]?.lines.join("\n")).toContain("**核心方法**");
  });

  it("parses sections and event index from template content", () => {
    const parsed = parseReportContent(SAMPLE);
    expect(parsed.sections.map((section) => section.title)).toEqual([
      "概览",
      "Event A #1",
    ]);
    expect(parsed.sections.map((section) => section.level)).toEqual([2, 2]);
    expect(parsed.sections.find((section) => section.kind === "event")?.eventIndex).toBe(1);
    expect(parsed.sections.find((section) => section.kind === "event")?.id).toBe("event-1");
  });

  it("extracts heading outline for navigation", () => {
    const parsed = parseReportContent(SAMPLE);
    const outline = extractOutline(parsed.sections);
    expect(outline).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ title: "概览", level: 2 }),
        expect.objectContaining({ title: "Event A #1", kind: "event", eventIndex: 1 }),
      ])
    );
  });

  it("keeps indented pseudo headings as content", () => {
    const parsed = parseReportContent(`# Root\n    ## not a heading\n## Real Heading`);
    expect(parsed.sections.map((section) => section.title)).toEqual(["Root", "Real Heading"]);
    expect(parsed.sections[0]?.lines).toContain("    ## not a heading");
  });

  it("does not classify non-event suffix headings as events", () => {
    const parsed = parseReportContent("## Version #2026");
    expect(parsed.sections[0]?.kind).toBe("normal");
    expect(parsed.sections[0]?.eventIndex).toBeNull();
  });

  it("normalizes markdown links in heading titles", () => {
    const parsed = parseReportContent("## [Event A](https://example.com/a) #1");
    expect(parsed.sections[0]?.title).toBe("Event A #1");
    expect(parsed.sections[0]?.kind).toBe("event");
    expect(parsed.sections[0]?.eventIndex).toBe(1);
  });

  it("deduplicates section ids for repeated headings", () => {
    const parsed = parseReportContent("## 概览\n## 概览");
    expect(parsed.sections.map((section) => section.id)).toEqual(["概览", "概览-2"]);
  });

  it("canonicalizes overview-first content when event headings are not anchor-compatible", () => {
    const nonCanonical = `## 概览

## 详细事件报告

### 模型发布

#### 1. [Event A](https://example.com/a)
> A summary`;

    const normalized = canonicalizeReportContent(
      nonCanonical,
      [
        {
          event_id: "event-a",
          index: 1,
          title: "Event A",
          category: "模型发布",
          one_line_tldr: "A summary",
          detail: "A detail",
          keywords: [],
          entities: [],
          metrics: [],
          source_links: ["https://example.com/a"],
          source_count: 1,
          source_name: "Source A",
          published_at: null,
        },
      ],
      "今日摘要"
    );

    expect(normalized).toContain("## 摘要");
    expect(normalized).toContain("## 概览");
    expect(normalized).toContain("## [A summary](https://example.com/a) #1");
    expect(normalized).toContain("[#1](#event-1)");
  });

  it("drops deprecated digest detail-note lines instead of patching them back in", () => {
    const normalized = normalizePaperDigestContent(
      `---
date: 2026-03-20
---

# Paper Digest

### 1. Nemotron-Cascade 2
**核心方法**

值得重点关注

- 详细笔记：见关联阅读笔记`,
      {
        paper_mode: "digest",
        paper_note_links: [{ report_id: "note-1", title: "Nemotron-Cascade 2" }],
      }
    );

    expect(normalized).toContain("**核心方法**");
    expect(normalized).not.toContain("详细笔记");
    expect(normalized).not.toContain("/reports/note-1");
  });

  it("normalizes legacy paper digest headings and section labels for display", () => {
    const normalized = normalizePaperDigestContent(
      `# GUI 智能体的评测、安全与长程记忆

## 今日锐评

这是一段旧总结。

## Safety

### 1. Paper A

**锐评**

先看评测再看攻击面。`,
      {
        paper_mode: "digest",
      },
      "2026-03-22"
    );

    expect(normalized).toContain("# 2026-03-22 论文推荐");
    expect(normalized).toContain("## 总结");
    expect(normalized).toContain("**阅读建议**");
    expect(normalized).not.toContain("## 今日锐评");
    expect(normalized).not.toContain("**锐评**");
  });
});
