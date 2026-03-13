# Report Monitor Management Design

**Date:** 2026-03-13  
**Status:** Approved  
**Scope:** Report list/detail/archive monitor attribution, archive filtering, and report deletion

---

## 1. Goal

Make reports clearly attributable to the monitor that generated them, allow archive filtering by monitor, and add report deletion actions in both the report detail page and archive/report list surfaces.

## 2. Product Decisions

- `monitor` is the report's task theme and is the only new theme/filter dimension in this change.
- Both the report page and archive/report list need a delete action.
- Archive filtering should support:
  - existing time period filter
  - new monitor/theme filter
- Report cards and detail headers should display the owning monitor/theme.

## 3. P0 Scope

### 3.1 Backend

- Persist report ownership using report metadata:
  - `monitor_id`
  - `monitor_name`
- Extend report response schema with:
  - `monitor_id`
  - `monitor_name`
- Extend report list API query with optional `monitor_id`.
- Add `DELETE /api/v1/reports/{report_id}`.
- Extend report filter aggregation with monitor options for archive UI.

### 3.2 Frontend

- Report cards show the owning monitor/theme.
- Discover page cards show the monitor.
- Archive page:
  - shows monitor on each card
  - supports monitor dropdown filter
  - supports delete action
- Report detail page:
  - shows monitor in header meta
  - supports delete action
  - redirects after successful deletion

## 4. Data Design

### 4.1 Why metadata instead of schema migration

This is a P0 UI/API attribution requirement, but the repository guidance prefers keeping P0 changes concise. The existing `reports.metadata` JSON field already stores report-level derived information. Adding `monitor_id` and `monitor_name` there avoids an Alembic migration while still giving stable ownership for new reports.

### 4.2 Response contract

`ReportResponse` adds:

- `monitor_id: UUID | null`
- `monitor_name: str`

`ReportFiltersResponse` adds:

- `monitors: list[ReportFilterMonitorOption]`

Where each option contains:

- `id: UUID`
- `name: str`

## 5. Behavior Rules

### 5.1 New reports

- When a monitor run creates a report, orchestrator writes `monitor_id` and `monitor_name` into report metadata.
- APIs surface those fields directly.

### 5.2 Existing historical reports

- If metadata already has `monitor_id`/`monitor_name`, use it.
- If missing, API returns:
  - `monitor_id = null`
  - `monitor_name = ""`
- Archive monitor filter only lists reports with known monitor metadata.
- Historical reports without monitor attribution remain viewable and deletable.

### 5.3 Delete semantics

- Deleting a report removes the DB row only.
- It does not attempt to delete previously published Notion/other sink pages in this change.
- UI copy should keep this action explicit and local to LexDeepResearch.

## 6. UI Design

### 6.1 Report cards

- Add a low-emphasis line or badge group for `所属任务`.
- Keep the existing card as the navigation target.
- Delete action must not trigger card navigation.

### 6.2 Archive filters

- Keep the existing time tabs.
- Add a monitor select beside or below the tabs.
- Default is `全部任务`.

### 6.3 Report detail header

- Show `所属任务：{monitor_name}` near date/type/source meta.
- Add a delete button in the header actions area.

## 7. Error Handling

- Delete failure: show inline error message, keep current page state.
- Delete success on archive/list: remove the item from local state.
- Delete success on detail: navigate back to `/library`.
- Missing monitor attribution: hide the task label instead of showing placeholder junk.

## 8. Testing Strategy

- Backend API tests:
  - report list/detail include monitor attribution
  - filter aggregation includes monitor options
  - delete endpoint removes a report
- Frontend tests:
  - archive page filters by monitor
  - report cards render monitor label
  - detail page renders monitor label
  - delete actions call API and update navigation/state

## 9. Non-Goals

- No sink-side deletion or remote cleanup.
- No new standalone `monitor_id` DB column in `reports` for this task.
- No theme/topic filtering beyond monitor/task theme.
