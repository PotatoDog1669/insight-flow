# Report Type & Template Unification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace `depth` with `report_type` across backend/frontend and make monitor scheduling/template behavior consistent with `daily|weekly|custom + report_type`.

**Architecture:** Migrate schema first (`reports`, `monitors`, user settings), then switch backend contracts and runtime flow to `report_type`, and finally align frontend form/filter/rendering behavior. Use template engine as canonical report content output contract (`daily|weekly|research`) and treat schedule cadence separately (`daily|weekly|custom`). Keep each change set small and verified with targeted tests before broad regression runs.

**Tech Stack:** FastAPI, SQLAlchemy (async), Alembic, Pydantic, pytest, Next.js, TypeScript, Vitest.

---

### Task 1: Template Engine Contract Switch (`depth` -> `report_type`)

**Files:**
- Modify: `backend/app/template_engine/resolver.py`
- Modify: `backend/app/template_engine/renderer.py`
- Modify: `backend/app/templates/manifest.yaml`
- Create: `backend/app/templates/reports/daily/v1.md.j2`
- Create: `backend/app/templates/reports/weekly/v1.md.j2`
- Create: `backend/app/templates/reports/research/v1.md.j2`
- Test: `backend/tests/template_engine/test_template_renderer.py`

**Step 1: Write the failing test**

```python
def test_resolve_report_template_path_by_report_type() -> None:
    ref = resolve_report_template(report_type="daily", version="v1")
    assert ref.key == "daily/v1"
    assert "templates/reports/daily" in str(ref.path)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/python -m pytest tests/template_engine/test_template_renderer.py::test_resolve_report_template_path_by_report_type -v`
Expected: FAIL because `resolve_report_template()` still requires `time_period` and `depth`.

**Step 3: Write minimal implementation**

```python
def resolve_report_template(*, report_type: str, version: str = "v1") -> TemplateRef:
    safe_report_type = _safe_segment(report_type, field="report_type")
    safe_version = _safe_segment(version, field="version")
    path = _safe_join(TEMPLATE_ROOT, "reports", safe_report_type, f"{safe_version}.md.j2")
    _assert_exists(path)
    return TemplateRef(namespace="reports", key=f"{safe_report_type}/{safe_version}", path=path)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/python -m pytest tests/template_engine/test_template_renderer.py -v`
Expected: PASS, no `depth` references in template resolver tests.

**Step 5: Commit**

```bash
git add backend/app/template_engine/resolver.py backend/app/template_engine/renderer.py backend/app/templates/manifest.yaml backend/app/templates/reports/daily/v1.md.j2 backend/app/templates/reports/weekly/v1.md.j2 backend/app/templates/reports/research/v1.md.j2 backend/tests/template_engine/test_template_renderer.py
git commit -m "refactor: switch template engine to report_type contract"
```

### Task 2: DB Migration + Model Layer (`reports` and `monitors`)

**Files:**
- Create: `backend/alembic/versions/20260302_0005_report_type_replace_depth.py`
- Modify: `backend/app/models/report.py`
- Modify: `backend/app/models/monitor.py`
- Test: `backend/tests/test_api_persistence_v1.py`

**Step 1: Write the failing test**

```python
def test_create_monitor_persists_report_type(client: TestClient, db_session_factory) -> None:
    response = client.post("/api/v1/monitors", json={...,"time_period":"custom","report_type":"research","source_ids":[...]})
    assert response.status_code == 201
    assert response.json()["report_type"] == "research"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_api_persistence_v1.py::test_create_monitor_persists_report_type -v`
Expected: FAIL because monitor model/schema still expose `depth`.

**Step 3: Write minimal implementation**

```python
# Report model
report_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="daily / weekly / research")

# Monitor model
report_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="daily / weekly / research")
```

Migration backfill rules:
- reports: `weekly -> weekly`, else `daily`
- monitors: `daily -> daily`, `weekly -> weekly`, `custom -> daily`
- drop old `depth` columns

**Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_api_persistence_v1.py -v`
Expected: PASS for persistence behavior with new field.

**Step 5: Commit**

```bash
git add backend/alembic/versions/20260302_0005_report_type_replace_depth.py backend/app/models/report.py backend/app/models/monitor.py backend/tests/test_api_persistence_v1.py
git commit -m "feat: migrate reports and monitors from depth to report_type"
```

### Task 3: Backend Schemas and API Contracts

**Files:**
- Modify: `backend/app/schemas/report.py`
- Modify: `backend/app/schemas/monitor.py`
- Modify: `backend/app/schemas/user.py`
- Modify: `backend/app/api/v1/reports.py`
- Modify: `backend/app/api/v1/monitors.py`
- Modify: `backend/app/api/v1/users.py`
- Test: `backend/tests/test_api_contract_v1.py`

**Step 1: Write the failing test**

```python
def test_reports_contract_filters_by_report_type(client: TestClient) -> None:
    response = client.get("/api/v1/reports", params={"report_type": "daily"})
    assert response.status_code == 200
    assert all(item["report_type"] == "daily" for item in response.json())
```

**Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_api_contract_v1.py::test_reports_contract_filters_by_report_type -v`
Expected: FAIL because query param and response field are still `depth`-based.

**Step 3: Write minimal implementation**

```python
class ReportResponse(BaseModel):
    report_type: Literal["daily", "weekly", "research"]

@router.get("")
async def list_reports(report_type: str | None = Query(default=None), ...):
    if report_type:
        stmt = stmt.where(Report.report_type == report_type)
```

Monitor validation behavior:
- `time_period="daily"` => force `report_type="daily"`
- `time_period="weekly"` => force `report_type="weekly"`
- `time_period="custom"` => require explicit `report_type`

User settings:
- `default_depth` -> `default_report_type`

**Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_api_contract_v1.py -v`
Expected: PASS for monitor/report/user contracts.

**Step 5: Commit**

```bash
git add backend/app/schemas/report.py backend/app/schemas/monitor.py backend/app/schemas/user.py backend/app/api/v1/reports.py backend/app/api/v1/monitors.py backend/app/api/v1/users.py backend/tests/test_api_contract_v1.py
git commit -m "feat: update backend api contracts to report_type"
```

### Task 4: Runtime Generation Flow Uses `report_type`

**Files:**
- Modify: `backend/app/scheduler/monitor_runner.py`
- Modify: `backend/app/scheduler/orchestrator.py`
- Modify: `backend/app/scheduler/scheduler.py`
- Test: `backend/tests/scheduler/test_orchestrator_e2e.py`
- Test: `backend/tests/scheduler/test_scheduler_monitor_runs.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_custom_monitor_run_uses_selected_report_type(...):
    # setup monitor: time_period=custom, report_type=research
    # trigger run
    # assert persisted report.report_type == "research"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/python -m pytest tests/scheduler/test_orchestrator_e2e.py::test_custom_monitor_run_uses_selected_report_type -v`
Expected: FAIL because orchestrator currently persists fixed report flavor.

**Step 3: Write minimal implementation**

```python
result = await orchestrator.run_daily_pipeline(..., report_type=monitor.report_type)
# orchestrator chooses template/render path by report_type and persists report.report_type
```

Keep scheduler cadence:
- daily monitors in daily job
- weekly monitors in weekly job
- custom monitors by cron string

**Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/python -m pytest tests/scheduler/test_orchestrator_e2e.py tests/scheduler/test_scheduler_monitor_runs.py -v`
Expected: PASS for scheduled/manual + report_type routing.

**Step 5: Commit**

```bash
git add backend/app/scheduler/monitor_runner.py backend/app/scheduler/orchestrator.py backend/app/scheduler/scheduler.py backend/tests/scheduler/test_orchestrator_e2e.py backend/tests/scheduler/test_scheduler_monitor_runs.py
git commit -m "feat: route monitor runs by report_type and schedule policy"
```

### Task 5: Frontend API Types and Report UI

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/ReportCard.tsx`
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/app/library/page.tsx`
- Modify: `frontend/src/app/reports/[id]/page.tsx`
- Test: `frontend/src/app/reports/[id]/page.test.tsx`

**Step 1: Write the failing test**

```tsx
it("renders report type badge without depth mapping", async () => {
  // mock report_type: "research"
  // assert "Research" appears and no brief/deep badge logic is used
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/app/reports/[id]/page.test.tsx`
Expected: FAIL because UI still maps `depth` to `L1/L2`.

**Step 3: Write minimal implementation**

```ts
export interface Report {
  report_type: "daily" | "weekly" | "research";
}
```

```tsx
<Badge>{report.report_type}</Badge>
```

Update list/filter query params to use `report_type`.

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/app/reports/[id]/page.test.tsx`
Expected: PASS for new report-type display.

**Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/ReportCard.tsx frontend/src/app/page.tsx frontend/src/app/library/page.tsx frontend/src/app/reports/[id]/page.tsx frontend/src/app/reports/[id]/page.test.tsx
git commit -m "feat: align frontend reports ui and types with report_type"
```

### Task 6: Frontend Monitor Form (No `depth`, Custom Requires Template)

**Files:**
- Modify: `frontend/src/app/monitors/page.tsx`
- Modify: `frontend/src/app/monitors/page.test.tsx`

**Step 1: Write the failing test**

```tsx
it("requires report type when time period is custom", async () => {
  // open create modal, choose custom, no report_type selected
  // assert create button disabled
  // choose research and assert enabled
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/app/monitors/page.test.tsx`
Expected: FAIL because form still uses `depth`.

**Step 3: Write minimal implementation**

```tsx
const [reportType, setReportType] = useState<"daily" | "weekly" | "research" | "">("");
const effectiveReportType = timePeriod === "daily" ? "daily" : timePeriod === "weekly" ? "weekly" : reportType;
const canSubmit = !!name && selectedSources.length > 0 && !!effectiveReportType;
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/app/monitors/page.test.tsx`
Expected: PASS for custom template selection and submit validation.

**Step 5: Commit**

```bash
git add frontend/src/app/monitors/page.tsx frontend/src/app/monitors/page.test.tsx
git commit -m "feat: replace monitor depth with schedule-aware report_type selection"
```

### Task 7: Backward Compatibility Cleanup + Full Verification

**Files:**
- Modify: `backend/tests/test_api_persistence_sources_articles_tasks_v1.py`
- Modify: `backend/tests/e2e/test_notion_publish_path.py`
- Modify: `frontend/src/app/page.tsx` (if any final query cleanup remains)
- Modify: `frontend/src/app/library/page.tsx` (if any final query cleanup remains)

**Step 1: Write failing regression checks**

```python
def test_no_depth_in_reports_contract(...):
    payload = client.get("/api/v1/reports").json()[0]
    assert "depth" not in payload
```

**Step 2: Run to verify failures (if any remain)**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_api_contract_v1.py tests/test_api_persistence_sources_articles_tasks_v1.py tests/e2e/test_notion_publish_path.py -v`
Expected: FAIL until all depth references are removed.

**Step 3: Minimal cleanup implementation**

```python
# remove final depth assertions/usages and replace with report_type assertions
```

**Step 4: Run full impacted suites**

Run backend:
`cd backend && ../.venv/bin/python -m pytest tests/template_engine/test_template_renderer.py tests/test_api_contract_v1.py tests/test_api_persistence_v1.py tests/test_api_persistence_sources_articles_tasks_v1.py tests/scheduler/test_orchestrator_e2e.py tests/scheduler/test_scheduler_monitor_runs.py -q`

Run frontend:
`cd frontend && npm test -- src/app/monitors/page.test.tsx src/app/reports/[id]/page.test.tsx`

Expected: PASS, zero failures.

**Step 5: Commit**

```bash
git add backend/tests/test_api_persistence_sources_articles_tasks_v1.py backend/tests/e2e/test_notion_publish_path.py frontend/src/app/page.tsx frontend/src/app/library/page.tsx
git commit -m "test: finalize report_type migration and remove depth regressions"
```

### Task 8: Verification and Release Notes

**Files:**
- Modify: `README.md`
- Modify: `docs/guides/configure-sink.mdx` (if references depth)
- Create: `docs/plans/2026-03-02-report-type-template-unification-release-notes.md`

**Step 1: Write failing docs check**

```bash
rg -n "\\bdepth\\b" README.md docs backend/app frontend/src
```

**Step 2: Run to verify remaining references**

Run: `rg -n "\\bdefault_depth\\b|\\bdepth\\b" README.md docs backend/app frontend/src`
Expected: shows stale product/API references before cleanup.

**Step 3: Minimal documentation update**

```md
- Replace depth with report_type
- Document custom schedule + template selection behavior
- Document migration mapping for historical reports
```

**Step 4: Run final verification**

Run:
`cd backend && ../.venv/bin/python -m pytest -q`
`cd frontend && npm test`

Expected: PASS on both suites.

**Step 5: Commit**

```bash
git add README.md docs/guides/configure-sink.mdx docs/plans/2026-03-02-report-type-template-unification-release-notes.md
git commit -m "docs: publish report_type migration and scheduling-template semantics"
```

## Implementation Notes

- Follow `@superpowers:test-driven-development` for every task.
- Before any completion claim, run verification per `@superpowers:verification-before-completion`.
- Keep commits focused to one task each; avoid mixed backend/frontend commits unless unavoidable.
