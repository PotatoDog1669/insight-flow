# Archive Delete Confirmation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the archive monitor filter into the tab toolbar, keep delete only on the archive page, and require confirmation before archive deletion.

**Architecture:** Reuse the existing `ReportCard` optional delete API and narrow its usage to the archive page only. Archive delete flow wraps the existing `deleteReport` call with a native confirmation check, while discover and report detail stop rendering delete controls entirely.

**Tech Stack:** Next.js, React, TypeScript, Vitest, Testing Library

---

### Task 1: Add failing tests for archive-only delete behavior

**Files:**
- Modify: `frontend/src/app/library/page.test.tsx`
- Modify: `frontend/src/app/page.test.tsx`
- Modify: `frontend/src/app/reports/[id]/page.test.tsx`

**Step 1: Write the failing tests**

```tsx
it("does not delete when archive confirmation is cancelled", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(false);
  ...
  expect(mockedDeleteReport).not.toHaveBeenCalled();
});

it("does not render delete controls on discover cards", async () => {
  expect(screen.queryByRole("button", { name: /删除报告/i })).not.toBeInTheDocument();
});

it("does not render a delete action on report detail", async () => {
  expect(screen.queryByRole("button", { name: /删除报告/i })).not.toBeInTheDocument();
});
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- src/app/page.test.tsx src/app/library/page.test.tsx 'src/app/reports/[id]/page.test.tsx'`
Expected: FAIL because delete is still available outside archive and archive delete has no confirmation.

### Task 2: Implement archive-only delete and toolbar layout

**Files:**
- Modify: `frontend/src/app/library/page.tsx`
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/app/reports/[id]/page.tsx`

**Step 1: Add minimal implementation**

```tsx
if (!window.confirm("确认删除这份报告吗？")) return;
```

```tsx
<div className="mb-8 flex ... justify-between ...">
  <div>{TIME_TABS ...}</div>
  <div><label>任务主题</label><select ... /></div>
</div>
```

```tsx
<ReportCard report={report} index={i} />
```

**Step 2: Run tests to verify they pass**

Run: `cd frontend && npm test -- src/app/page.test.tsx src/app/library/page.test.tsx 'src/app/reports/[id]/page.test.tsx' src/lib/api.test.ts`
Expected: PASS

### Task 3: Run focused verification

**Files:**
- No code changes required

**Step 1: Run focused frontend verification**

Run: `cd frontend && npm test -- src/app/page.test.tsx src/app/library/page.test.tsx 'src/app/reports/[id]/page.test.tsx' src/lib/api.test.ts`
Expected: PASS
