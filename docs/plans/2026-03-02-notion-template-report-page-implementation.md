# Notion-Template Report Detail Page Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild `/reports/[id]` so its primary structure is rendered from `report.content` (the same template content exported to Notion), while adding outline navigation and collapsible event/meta interactions.

**Architecture:** Keep `report.content` as source-of-truth for the document skeleton and layer structured enhancements from `report.events`, `report.global_tldr`, and `report.topics`. Split implementation into parser utilities, focused presentational components, then page integration with fallback to current grouped article view when content is unavailable.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind CSS v4, Vitest, Testing Library.

---

## Execution Rules

- Follow `@test-driven-development` for every task.
- Use `@frontend-design` principles while preserving existing app visual language.
- Run `@verification-before-completion` checks before claiming completion.
- Keep scope DRY/YAGNI: no backend or sink changes in this plan.

### Task 1: Add report content parser and template mapping primitives

**Files:**
- Create: `frontend/src/lib/report-content-parser.ts`
- Create: `frontend/src/lib/report-content-parser.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import { extractOutline, parseReportContent } from "@/lib/report-content-parser";

const SAMPLE = `# AI Daily Report — 2026-03-02\n\n## 全局总结与锐评\n总结：A\n锐评：B\n\n## 正文\n## 概览\n- [Item](https://example.com) #1\n\n---\n## Event A #1\nSource：One line\n关键词：\`a\`\n相关链接：\n- https://example.com`;

describe("report-content-parser", () => {
  it("parses sections and event index from template content", () => {
    const parsed = parseReportContent(SAMPLE);
    expect(parsed.sections.length).toBeGreaterThan(3);
    expect(parsed.sections.find((s) => s.kind === "event")?.eventIndex).toBe(1);
  });

  it("extracts heading outline for navigation", () => {
    const parsed = parseReportContent(SAMPLE);
    const outline = extractOutline(parsed.sections);
    expect(outline.map((i) => i.title)).toContain("全局总结与锐评");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/lib/report-content-parser.test.ts`  
Expected: FAIL with module/function not found.

**Step 3: Write minimal implementation**

```ts
export type ParsedSection = {
  id: string;
  level: 1 | 2;
  title: string;
  kind: "normal" | "meta" | "summary" | "overview" | "event";
  eventIndex: number | null;
  lines: string[];
};

export function parseReportContent(content: string): { sections: ParsedSection[] } {
  // line-based parser for # / ## headings and --- separators
  // classify section kind by heading text and capture "#<number>" from event headings
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/lib/report-content-parser.test.ts`  
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/lib/report-content-parser.ts frontend/src/lib/report-content-parser.test.ts
git commit -m "feat: add report content parser for notion-template rendering"
```

### Task 2: Build document renderer with collapsible meta/event blocks

**Files:**
- Create: `frontend/src/components/report/ReportDocument.tsx`
- Create: `frontend/src/components/report/ReportDocument.test.tsx`

**Step 1: Write the failing test**

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { ReportDocument } from "@/components/report/ReportDocument";

it("collapses runtime meta by default and toggles event sections", () => {
  render(
    <ReportDocument
      content="# T\n\n## 全局总结与锐评\nA\n\n## 正文\n\n---\n## Event A #1\nBody"
      events={[]}
      globalTldr=""
      topics={[]}
    />
  );

  expect(screen.getByRole("button", { name: /运行元信息/i })).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(screen.getByRole("button", { name: /Event A #1/i }));
  expect(screen.getByText("Body")).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/components/report/ReportDocument.test.tsx`  
Expected: FAIL with missing component.

**Step 3: Write minimal implementation**

```tsx
export function ReportDocument(props: ReportDocumentProps) {
  // parse content
  // render heading hierarchy as document blocks
  // runtime meta section: collapsed by default
  // event sections: expandable details
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/components/report/ReportDocument.test.tsx`  
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/components/report/ReportDocument.tsx frontend/src/components/report/ReportDocument.test.tsx
git commit -m "feat: add notion-style report document renderer"
```

### Task 3: Build outline navigation with active heading state

**Files:**
- Create: `frontend/src/hooks/use-active-heading.ts`
- Create: `frontend/src/components/report/ReportOutline.tsx`
- Create: `frontend/src/components/report/ReportOutline.test.tsx`

**Step 1: Write the failing test**

```tsx
import { render, screen } from "@testing-library/react";
import { ReportOutline } from "@/components/report/ReportOutline";

it("renders heading anchors for parsed outline items", () => {
  render(
    <ReportOutline
      items={[
        { id: "summary", title: "全局总结与锐评", level: 2 },
        { id: "event-1", title: "Event A #1", level: 2 },
      ]}
      activeId="summary"
      onNavigate={() => {}}
    />
  );

  expect(screen.getByRole("link", { name: "全局总结与锐评" })).toHaveAttribute("href", "#summary");
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/components/report/ReportOutline.test.tsx`  
Expected: FAIL with missing hook/component.

**Step 3: Write minimal implementation**

```tsx
export function ReportOutline({ items, activeId, onNavigate }: Props) {
  return items.map((item) => (
    <a key={item.id} href={`#${item.id}`} onClick={(e) => { e.preventDefault(); onNavigate(item.id); }}>
      {item.title}
    </a>
  ));
}
```

```ts
export function useActiveHeading(ids: string[]): string {
  // IntersectionObserver-based active section tracking with safe fallback
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/components/report/ReportOutline.test.tsx`  
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/hooks/use-active-heading.ts frontend/src/components/report/ReportOutline.tsx frontend/src/components/report/ReportOutline.test.tsx
git commit -m "feat: add report outline navigation and active heading hook"
```

### Task 4: Add right meta panel for event/topic enhancement

**Files:**
- Create: `frontend/src/components/report/ReportMetaPanel.tsx`
- Create: `frontend/src/components/report/ReportMetaPanel.test.tsx`

**Step 1: Write the failing test**

```tsx
import { render, screen } from "@testing-library/react";
import { ReportMetaPanel } from "@/components/report/ReportMetaPanel";

it("shows event count, source count and topic chips", () => {
  render(
    <ReportMetaPanel
      eventCount={3}
      sourceCount={2}
      topics={[{ name: "agent", weight: 3 }, { name: "safety", weight: 2 }]}
      onTopicSelect={() => {}}
    />
  );

  expect(screen.getByText("3 events")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "agent" })).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/components/report/ReportMetaPanel.test.tsx`  
Expected: FAIL with missing component.

**Step 3: Write minimal implementation**

```tsx
export function ReportMetaPanel({ eventCount, sourceCount, topics, onTopicSelect }: Props) {
  // stat blocks + clickable topic chips
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/components/report/ReportMetaPanel.test.tsx`  
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/components/report/ReportMetaPanel.tsx frontend/src/components/report/ReportMetaPanel.test.tsx
git commit -m "feat: add report meta panel for notion-template detail page"
```

### Task 5: Integrate new report detail layout and fallback behavior

**Files:**
- Modify: `frontend/src/app/reports/[id]/page.tsx`
- Create: `frontend/src/app/reports/[id]/page.test.tsx`

**Step 1: Write the failing test**

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import ReportDetailPage from "@/app/reports/[id]/page";
import { getArticleById, getReportById } from "@/lib/api";

vi.mock("next/navigation", () => ({ useParams: () => ({ id: "report-1" }) }));
vi.mock("@/lib/api", () => ({ getReportById: vi.fn(), getArticleById: vi.fn() }));

it("renders document from report.content and outline", async () => {
  vi.mocked(getReportById).mockResolvedValue({
    id: "report-1",
    title: "AI Daily",
    content: "# AI Daily\\n\\n## 全局总结与锐评\\nA",
    events: [],
    topics: [],
    tldr: [],
    article_ids: [],
    article_count: 0,
    time_period: "daily",
    depth: "deep",
    report_date: "2026-03-02",
    user_id: null,
    global_tldr: "",
    metadata: {},
    report_type: "deep",
    published_to: [],
    created_at: "2026-03-02T00:00:00Z",
  } as never);

  render(<ReportDetailPage />);

  await waitFor(() => expect(screen.getByText("全局总结与锐评")).toBeInTheDocument());
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/app/reports/[id]/page.test.tsx`  
Expected: FAIL with old page structure assertions unmet.

**Step 3: Write minimal implementation**

```tsx
return (
  <div className="grid gap-8 lg:grid-cols-[220px_minmax(0,1fr)_240px]">
    <ReportOutline ... />
    <ReportDocument ... />
    <ReportMetaPanel ... />
  </div>
);
```

- If `report.content` empty: keep existing grouped `ArticleCard` fallback.
- Mobile behavior: outline hidden behind toggle panel; meta panel rendered after document.

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/app/reports/[id]/page.test.tsx`  
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/app/reports/[id]/page.tsx frontend/src/app/reports/[id]/page.test.tsx
git commit -m "feat: align report detail page with notion export template"
```

### Task 6: End-to-end verification for frontend scope

**Files:**
- Modify (if needed): `frontend/src/components/report/*.tsx`
- Modify (if needed): `frontend/src/app/reports/[id]/page.tsx`

**Step 1: Add/adjust failing assertions for regression gaps**

```tsx
it("falls back to grouped view when report.content is empty", async () => {
  // mock empty content and assert fallback container text exists
});
```

**Step 2: Run targeted tests to verify failures are real**

Run: `cd frontend && npm run test -- src/lib/report-content-parser.test.ts src/components/report/ReportDocument.test.tsx src/components/report/ReportOutline.test.tsx src/components/report/ReportMetaPanel.test.tsx src/app/reports/[id]/page.test.tsx`  
Expected: FAIL only on newly added failing assertions.

**Step 3: Implement minimal fixes**

```tsx
// patch fallback condition and mobile rendering edge cases
const hasTemplateContent = Boolean(report.content?.trim());
```

**Step 4: Run full verification**

Run: `cd frontend && npm run test`  
Expected: PASS.

Run: `cd frontend && npm run lint`  
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/app/reports/[id]/page.tsx frontend/src/components/report frontend/src/lib/report-content-parser.ts frontend/src/app/reports/[id]/page.test.tsx frontend/src/lib/report-content-parser.test.ts
 git commit -m "test: verify notion-template report detail interactions and fallback"
```
