import { describe, expect, it } from "vitest";

import { canonicalizeReportContent, extractOutline, parseReportContent } from "@/lib/report-content-parser";

const SAMPLE = `## 概览
- Event A [↗](https://example.com) [#1](#event-1)

---
## Event A #1
Source：One line
关键词：\`a\`
相关链接：
- https://example.com`;

describe("report-content-parser", () => {
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
});
