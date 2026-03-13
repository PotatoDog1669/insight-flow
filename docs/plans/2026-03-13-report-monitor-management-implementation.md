# Report Monitor Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add stable monitor ownership to reports, show that ownership in report/archive UIs, support archive filtering by monitor, and allow deleting reports from the report page and archive/report list.

**Architecture:** Persist `monitor_id` and `monitor_name` inside `reports.metadata` when a monitor-generated report is created, then surface those fields through the existing report APIs. Extend the report filters payload with monitor options, add a delete endpoint, and wire the frontend list/detail views to render monitor attribution, filter by monitor, and delete in-place.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Pydantic, pytest, Next.js, React, TypeScript, Vitest, Testing Library

---

## Implementation Notes

- Follow `@test-driven-development`: write failing tests first for backend and frontend behavior.
- Keep P0 concise: no Alembic migration, use `reports.metadata`.
- Do not disturb unrelated dirty workspace files.
- Before claiming success, run `@verification-before-completion`.

### Task 1: Add failing backend API tests for report monitor attribution and deletion

**Files:**
- Modify: `backend/tests/test_api_contract_v1.py`
- Modify: `backend/tests/test_api_persistence_v1.py`

**Step 1: Write the failing tests**

```python
def test_reports_list_and_detail_expose_monitor_fields(client) -> None:
    response = client.get("/api/v1/reports")
    assert response.status_code == 200
    assert response.json()[0]["monitor_name"] == "Agent News"


def test_report_filters_include_monitor_options(client) -> None:
    response = client.get("/api/v1/reports/filters")
    assert response.status_code == 200
    assert response.json()["monitors"][0]["name"] == "Agent News"


def test_delete_report_removes_row(client, seeded_report_id) -> None:
    response = client.delete(f"/api/v1/reports/{seeded_report_id}")
    assert response.status_code == 204
    assert client.get(f"/api/v1/reports/{seeded_report_id}").status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest -q tests/test_api_contract_v1.py tests/test_api_persistence_v1.py -k 'monitor_fields or monitor_options or delete_report'`
Expected: FAIL because report schemas and delete endpoint do not exist yet.

**Step 3: Commit**

```bash
git add backend/tests/test_api_contract_v1.py backend/tests/test_api_persistence_v1.py
git commit -m "test: cover report monitor attribution and deletion"
```

### Task 2: Implement backend report schema, filter, and delete behavior

**Files:**
- Modify: `backend/app/schemas/report.py`
- Modify: `backend/app/api/v1/reports.py`
- Modify: `backend/app/scheduler/orchestrator.py`

**Step 1: Write minimal implementation**

```python
class ReportFilterMonitorOption(BaseModel):
    id: uuid.UUID
    name: str


class ReportResponse(BaseModel):
    monitor_id: uuid.UUID | None = None
    monitor_name: str = ""
```

```python
@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(...):
    ...
```

```python
metadata_={
    ...,
    "monitor_id": str(monitor_id) if monitor_id else None,
    "monitor_name": monitor.name,
}
```

**Step 2: Run tests to verify they pass**

Run: `cd backend && uv run pytest -q tests/test_api_contract_v1.py tests/test_api_persistence_v1.py -k 'monitor_fields or monitor_options or delete_report'`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/app/schemas/report.py backend/app/api/v1/reports.py backend/app/scheduler/orchestrator.py
git commit -m "feat: expose report monitor attribution and delete API"
```

### Task 3: Add failing frontend tests for monitor display, archive filter, and delete actions

**Files:**
- Modify: `frontend/src/app/page.test.tsx`
- Create: `frontend/src/app/library/page.test.tsx`
- Modify: `frontend/src/app/reports/[id]/page.test.tsx`
- Modify: `frontend/src/lib/api.test.ts`

**Step 1: Write the failing tests**

```tsx
it("renders monitor label on report cards", async () => {
  expect(screen.getByText("所属任务")).toBeInTheDocument();
});

it("filters archive reports by monitor", async () => {
  await user.selectOptions(screen.getByLabelText("任务主题"), "monitor-1");
  expect(screen.queryByText("Report B")).not.toBeInTheDocument();
});

it("deletes a report from detail page and redirects", async () => {
  await user.click(screen.getByRole("button", { name: /删除报告/i }));
  expect(mockDeleteReport).toHaveBeenCalledWith("report-1");
});
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- src/app/page.test.tsx src/app/library/page.test.tsx src/app/reports/[id]/page.test.tsx src/lib/api.test.ts`
Expected: FAIL because monitor fields and delete/report filter behavior are not wired yet.

**Step 3: Commit**

```bash
git add frontend/src/app/page.test.tsx frontend/src/app/library/page.test.tsx frontend/src/app/reports/[id]/page.test.tsx frontend/src/lib/api.test.ts
git commit -m "test: cover report monitor display and deletion"
```

### Task 4: Implement frontend API types and UI behavior

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/ReportCard.tsx`
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/app/library/page.tsx`
- Modify: `frontend/src/app/reports/[id]/page.tsx`

**Step 1: Add API support**

```ts
export interface Report {
  monitor_id: string | null;
  monitor_name: string;
}

export interface ReportFilters {
  monitors: { id: string; name: string }[];
}

export const deleteReport = (reportId: string) =>
  fetchAPI<void>(`/api/v1/reports/${reportId}`, { method: "DELETE" });
```

**Step 2: Update report cards**

```tsx
{report.monitor_name && <span>所属任务: {report.monitor_name}</span>}
```

**Step 3: Update archive page**

```tsx
const [monitorFilter, setMonitorFilter] = useState("all");
const filters = await getReportFilters();
...
report.monitor_id === monitorFilter
```

**Step 4: Update detail page**

```tsx
<span>所属任务：{report.monitor_name}</span>
<Button onClick={handleDelete}>删除报告</Button>
router.push("/library")
```

**Step 5: Run tests to verify they pass**

Run: `cd frontend && npm test -- src/app/page.test.tsx src/app/library/page.test.tsx src/app/reports/[id]/page.test.tsx src/lib/api.test.ts`
Expected: PASS

**Step 6: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/ReportCard.tsx frontend/src/app/page.tsx frontend/src/app/library/page.tsx frontend/src/app/reports/[id]/page.tsx
git commit -m "feat: add report monitor display, filtering, and delete actions"
```

### Task 5: Run integrated verification

**Files:**
- No code changes required

**Step 1: Run backend verification**

Run: `cd backend && uv run pytest -q tests/test_api_contract_v1.py tests/test_api_persistence_v1.py`
Expected: PASS

**Step 2: Run frontend verification**

Run: `cd frontend && npm test -- src/app/page.test.tsx src/app/library/page.test.tsx src/app/reports/[id]/page.test.tsx src/lib/api.test.ts`
Expected: PASS

**Step 3: Run any focused build/type check available for touched surfaces**

Run: `cd frontend && npm run test -- src/components/ReportCard.test.tsx`
Expected: PASS if test exists, otherwise skip and record that it does not exist.
