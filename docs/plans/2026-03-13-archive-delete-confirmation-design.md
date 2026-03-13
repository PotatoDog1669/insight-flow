# Archive Delete Confirmation Design

**Date:** 2026-03-13  
**Status:** Approved  
**Scope:** Archive toolbar placement refinement and delete-surface restriction

---

## 1. Goal

Refine the archive page so the monitor/theme filter sits on the same row as the time tabs, and restrict report deletion to the archive page with a confirmation step before deletion.

## 2. Product Decisions

- `任务主题` filter moves to the right side of the time filter tabs on the archive page.
- Report deletion is only available on the archive page.
- Discover/report list page must not expose delete.
- Report detail page must not expose delete.
- Deleting from archive requires explicit confirmation before the API call.

## 3. UI Design

### 3.1 Archive toolbar

- Use a single responsive toolbar row:
  - left: time period tabs
  - right: compact `任务主题` label + select
- On narrower widths, the row can wrap, but the filter remains visually attached to the tabs rather than appearing as a separate block below.

### 3.2 Delete action

- Keep the existing delete icon on archive report cards only.
- Clicking delete first shows confirmation.
- Cancel leaves the report list untouched.
- Confirm triggers deletion and removes the card from local state.

## 4. Behavior Rules

- `ReportCard` supports optional delete affordance.
- Archive passes `onDelete`.
- Discover does not pass `onDelete`.
- Report detail does not render any delete action.

## 5. Confirmation Strategy

- Use native `window.confirm` for this refinement.
- Reason:
  - smallest safe change
  - predictable behavior
  - no extra modal state or accessibility work for this iteration

## 6. Testing Strategy

- Archive page:
  - filter still works
  - cancellation prevents delete API call
  - confirmation triggers delete API call
- Discover page:
  - no delete action rendered
- Report detail page:
  - no delete button rendered

## 7. Non-Goals

- No custom modal/dialog in this iteration
- No backend changes
- No change to report detail metadata display
