import { describe, expect, it } from "vitest";

import { extractOutline, parseReportContent } from "@/lib/report-content-parser";

const SAMPLE = `# AI Daily Report — 2026-03-02

## 全局总结与锐评
总结：A
锐评：B

## 正文
## 概览
- [Item](https://example.com) #1

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
      "AI Daily Report — 2026-03-02",
      "全局总结与锐评",
      "正文",
      "概览",
      "Event A #1",
    ]);
    expect(parsed.sections.map((section) => section.level)).toEqual([1, 2, 2, 2, 2]);
    expect(parsed.sections.find((section) => section.kind === "event")?.eventIndex).toBe(1);
  });

  it("extracts heading outline for navigation", () => {
    const parsed = parseReportContent(SAMPLE);
    const outline = extractOutline(parsed.sections);
    expect(outline).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ title: "全局总结与锐评", level: 2 }),
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

  it("deduplicates section ids for repeated headings", () => {
    const parsed = parseReportContent("## 概览\n## 概览");
    expect(parsed.sections.map((section) => section.id)).toEqual(["概览", "概览-2"]);
  });
});
