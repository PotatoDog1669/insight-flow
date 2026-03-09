import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { ReportDocument } from "@/components/report/ReportDocument";

describe("ReportDocument", () => {
  it("collapses runtime meta by default and renders event sections", () => {
    render(
      <ReportDocument
        content={`# T
生成时间(UTC): 2026-03-02T00:00:00Z
样本输入数: 5

## 全局总结与锐评
A

## 正文

---
## Event A #1
Body`}
        events={[]}
        globalTldr=""
        topics={[]}
      />
    );

    const metaButton = screen.getByRole("button", { name: /运行元信息/i });
    expect(metaButton).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("样本输入数: 5")).not.toBeInTheDocument();

    fireEvent.click(metaButton);
    expect(metaButton).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("样本输入数: 5")).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: /Event A #1/i, level: 2 })).toBeInTheDocument();
    expect(screen.getByText("Body")).toBeInTheDocument();
  });

  it("renders all event sections provided in content", () => {
    const eventSections = Array.from({ length: 20 })
      .map((_, idx) => `---\n## Event ${idx + 1} #${idx + 1}\nBody ${idx + 1}`)
      .join("\n\n");
    render(
      <ReportDocument
        content={`# T\n\n## 正文\n\n${eventSections}`}
        events={[]}
        globalTldr=""
        topics={[]}
      />
    );

    expect(screen.getByRole("heading", { name: /Event 15 #15/i, level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Event 16 #16/i, level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Event 20 #20/i, level: 2 })).toBeInTheDocument();
    expect(screen.getByText("Body 20")).toBeInTheDocument();
  });

  it("normalizes markdown event headings and removes duplicated intro callout", () => {
    const { container } = render(
      <ReportDocument
        content={`# T

## 正文

---
## [Event A](https://example.com/a) #1
> first summary

> second summary

Body`}
        events={[]}
        globalTldr=""
        topics={[]}
      />
    );

    expect(screen.getByRole("heading", { name: "Event A #1", level: 2 })).toBeInTheDocument();
    expect(screen.getByText("first summary")).toBeInTheDocument();
    expect(screen.queryByText("second summary")).not.toBeInTheDocument();
    expect(container.querySelectorAll("blockquote")).toHaveLength(1);
  });

  it("treats #event links as in-page anchors instead of external links", () => {
    const scrollSpy = vi.fn();
    const replaceSpy = vi.spyOn(window.history, "replaceState");
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollSpy,
    });

    render(
      <ReportDocument
        content={`## 概览
- Event A [#1](#event-1)

---
## Event A #1
Body`}
        events={[]}
        globalTldr=""
        topics={[]}
      />
    );

    const jumpLink = screen.getByRole("link", { name: "#1" });
    expect(jumpLink).not.toHaveAttribute("target", "_blank");

    fireEvent.click(jumpLink);
    expect(scrollSpy).toHaveBeenCalledTimes(1);
    expect(replaceSpy).toHaveBeenCalledWith(null, "", "#event-1");

    replaceSpy.mockRestore();
  });

  it("canonicalizes legacy polished content to overview + event anchors when events exist", () => {
    render(
      <ReportDocument
        content={`# AI Daily Report — 2026-03-05

## 执行摘要
legacy summary

## 详细动态
legacy body`}
        events={[
          {
            event_id: "evt-1",
            index: 1,
            title: "Gemini 3.1 Flash-Lite: Built for intelligence at scale",
            category: "要闻",
            one_line_tldr: "Google 发布 Gemini 3.1 Flash-Lite，主打高性价比与低延迟。",
            detail: "详细分析内容。",
            keywords: [],
            entities: [],
            metrics: [],
            source_links: ["https://example.com/gemini"],
            source_count: 1,
            source_name: "Google",
            published_at: null,
          },
        ]}
        globalTldr="这是今日摘要。"
        topics={[]}
      />
    );

    expect(screen.getByRole("heading", { name: "摘要", level: 2 })).toBeInTheDocument();
    expect(screen.getByText("这是今日摘要。")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "概览", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "↗" })).toHaveAttribute("href", "https://example.com/gemini");
    expect(screen.getByRole("link", { name: "#1" })).toHaveAttribute("href", "#event-1");
    expect(screen.getByRole("heading", { name: /Google 发布 Gemini 3.1 Flash-Lite #1/i, level: 2 })).toBeInTheDocument();
    expect(screen.queryByText("执行摘要")).not.toBeInTheDocument();
  });
});
