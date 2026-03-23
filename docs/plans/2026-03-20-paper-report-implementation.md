# Paper Report Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a first-class `paper` report flow that generates one digest report plus linked detailed paper notes, and publish the result cleanly to product surfaces and Obsidian.

**Architecture:** Extend the current report-type contract from `daily / weekly / research` to include `paper`, keep task creation simple by exposing only `paper`, and implement paper digest plus note generation inside the existing scheduler/orchestrator flow. Reuse the current report table and `metadata` for P0 relationships instead of introducing new tables.

**Tech Stack:** FastAPI, SQLAlchemy models, Pydantic, Jinja2 templates, Next.js, TypeScript, pytest, React Testing Library

---

### Task 1: Lock the `paper` report contract in backend and frontend tests

**Files:**
- Modify: `backend/tests/scheduler/test_orchestrator_e2e.py`
- Modify: `backend/tests/test_sources_api.py`
- Modify: `frontend/src/app/monitors/page.test.tsx`
- Modify: `frontend/src/app/reports/[id]/page.test.tsx`
- Modify: `frontend/src/app/page.test.tsx`
- Modify: `frontend/src/app/library/page.test.tsx`

**Step 1: Write the failing API and UI contract tests**

Add coverage that verifies:

- `paper` is accepted as a report type in backend request and response shapes
- the monitor form exposes `paper`
- report list and report detail pages can render `paper`
- `paper` reports do not inherit the daily-only title assumptions

**Step 2: Run test to verify it fails**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/scheduler/test_orchestrator_e2e.py backend/tests/test_sources_api.py -q
cd frontend && npm test -- src/app/monitors/page.test.tsx src/app/reports/[id]/page.test.tsx src/app/page.test.tsx src/app/library/page.test.tsx
```

Expected:

- backend and frontend tests fail because `paper` is not part of the current contract

**Step 3: Commit**

```bash
git add backend/tests/scheduler/test_orchestrator_e2e.py backend/tests/test_sources_api.py frontend/src/app/monitors/page.test.tsx frontend/src/app/reports/[id]/page.test.tsx frontend/src/app/page.test.tsx frontend/src/app/library/page.test.tsx
git commit -m "test: define paper report contract"
```

### Task 2: Extend report-type contracts and labels to include `paper`

**Files:**
- Modify: `backend/app/schemas/report.py`
- Modify: `backend/app/schemas/monitor.py`
- Modify: `backend/app/schemas/user.py`
- Modify: `backend/app/models/report.py`
- Modify: `backend/app/models/monitor.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/monitors/page.tsx`
- Modify: `frontend/src/app/reports/[id]/page.tsx`
- Modify: `frontend/src/components/ReportCard.tsx`
- Modify: `frontend/src/components/ReportCover.tsx`
- Test: `frontend/src/app/monitors/page.test.tsx`
- Test: `frontend/src/app/reports/[id]/page.test.tsx`

**Step 1: Implement the minimal contract update**

Update all typed report-type unions and labels to include `paper`.

Keep the task-facing UX simple:

- users can choose `paper`
- users cannot choose a separate detailed-note task type

Update model comments to reflect the new report type.

**Step 2: Run targeted tests**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/scheduler/test_orchestrator_e2e.py backend/tests/test_sources_api.py -q
cd frontend && npm test -- src/app/monitors/page.test.tsx src/app/reports/[id]/page.test.tsx
```

Expected:

- tests pass for the type contract and visible labels

**Step 3: Commit**

```bash
git add backend/app/schemas/report.py backend/app/schemas/monitor.py backend/app/schemas/user.py backend/app/models/report.py backend/app/models/monitor.py frontend/src/lib/api.ts frontend/src/app/monitors/page.tsx frontend/src/app/reports/[id]/page.tsx frontend/src/components/ReportCard.tsx frontend/src/components/ReportCover.tsx
git commit -m "feat: add paper report type contract"
```

### Task 3: Add paper digest and note templates

**Files:**
- Modify: `backend/app/templates/manifest.yaml`
- Create: `backend/app/templates/reports/paper/v1.md.j2`
- Create: `backend/app/templates/reports/paper/note/v1.md.j2`
- Create: `backend/app/templates/sinks/notion/reports/paper/v1.md.j2`
- Create: `backend/app/templates/sinks/notion/reports/paper/note/v1.md.j2`
- Create: `backend/tests/template_engine/test_paper_templates.py`

**Step 1: Write the failing template tests**

Cover:

- digest template renders `本期导读`
- digest template renders short-note sections with figure and detail-link slots
- note template renders the full reading-report sections
- notion sink templates can render digest and note modes without falling back

**Step 2: Run test to verify it fails**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/template_engine/test_paper_templates.py -q
```

Expected:

- FAIL because the paper templates do not exist yet

**Step 3: Implement the templates**

Use one shared report type namespace, `paper`, and separate digest vs note rendering by version or metadata-driven context. Keep the digest concise and the note more complete.

**Step 4: Run the template tests**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/template_engine/test_paper_templates.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/templates/manifest.yaml backend/app/templates/reports/paper backend/app/templates/sinks/notion/reports/paper backend/tests/template_engine/test_paper_templates.py
git commit -m "feat: add paper report templates"
```

### Task 4: Build paper report assembly primitives

**Files:**
- Create: `backend/app/renderers/paper.py`
- Create: `backend/app/papers/reporting.py`
- Create: `backend/tests/renderers/test_paper_renderer.py`

**Step 1: Write the failing renderer tests**

Cover:

- digest assembly builds one report with per-paper short notes
- digest metadata stores `paper_mode="digest"`
- selected papers are marked for detailed note generation
- note assembly builds one independent detailed report payload with `paper_mode="note"`

**Step 2: Run test to verify it fails**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/renderers/test_paper_renderer.py -q
```

Expected:

- FAIL because no paper renderer or reporting helpers exist yet

**Step 3: Implement the minimal reporting layer**

Implement:

- digest context assembly
- detailed-note context assembly
- metadata helpers for:
  - `paper_mode`
  - `parent_report_id`
  - `paper_slug`
  - `paper_identity`
  - `paper_note_links`

Prefer deterministic helpers over LLM calls in this layer. The model output should be treated as input data, not as the renderer itself.

**Step 4: Run the renderer tests**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/renderers/test_paper_renderer.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/renderers/paper.py backend/app/papers/reporting.py backend/tests/renderers/test_paper_renderer.py
git commit -m "feat: add paper report assembly"
```

### Task 5: Wire `paper` generation into the scheduler

**Files:**
- Modify: `backend/app/scheduler/orchestrator.py`
- Modify: `backend/app/api/v1/reports.py`
- Modify: `backend/tests/scheduler/test_orchestrator_e2e.py`

**Step 1: Write the failing scheduler test**

Cover:

- a `paper` monitor run builds one main digest report
- selected papers also produce independent note reports
- note links are attached back onto the digest metadata
- publishing still runs through the existing sink pipeline

**Step 2: Run test to verify it fails**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/scheduler/test_orchestrator_e2e.py -q
```

Expected:

- FAIL because `paper` has no scheduler branch yet

**Step 3: Implement the scheduler branch**

Add a dedicated `paper` branch in the report-building flow. The implementation should:

- gather paper-oriented candidates from the processed article set
- accept model ranking output
- build the digest first
- build detailed note reports second
- keep all generated reports inside the existing publish pipeline

For P0, keep relationships in `metadata` rather than adding a new relational table.

**Step 4: Run the scheduler tests**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/scheduler/test_orchestrator_e2e.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/scheduler/orchestrator.py backend/app/api/v1/reports.py backend/tests/scheduler/test_orchestrator_e2e.py
git commit -m "feat: generate paper digests and note reports"
```

### Task 6: Prevent paper reports from being normalized into daily-report structure in the frontend

**Files:**
- Modify: `frontend/src/lib/report-content-parser.ts`
- Modify: `frontend/src/components/report/ReportDocument.tsx`
- Modify: `frontend/src/app/reports/[id]/page.tsx`
- Modify: `frontend/src/lib/report-content-parser.test.ts`
- Modify: `frontend/src/app/reports/[id]/page.test.tsx`

**Step 1: Write the failing frontend behavior tests**

Cover:

- `paper` digest content is rendered as authored
- `paper` note content is rendered as authored
- daily canonicalization remains limited to daily-like reports

**Step 2: Run test to verify it fails**

Run:
```bash
cd frontend && npm test -- src/lib/report-content-parser.test.ts src/app/reports/[id]/page.test.tsx
```

Expected:

- FAIL because paper reports currently pass through the same normalization path

**Step 3: Implement the minimal fix**

Gate canonicalization on report type or explicit metadata so `paper` digest and note reports preserve their own structure.

**Step 4: Run the frontend tests**

Run:
```bash
cd frontend && npm test -- src/lib/report-content-parser.test.ts src/app/reports/[id]/page.test.tsx
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add frontend/src/lib/report-content-parser.ts frontend/src/components/report/ReportDocument.tsx frontend/src/app/reports/[id]/page.tsx frontend/src/lib/report-content-parser.test.ts frontend/src/app/reports/[id]/page.test.tsx
git commit -m "fix: preserve paper report structure in frontend"
```

### Task 7: Add paper-aware Obsidian publishing

**Files:**
- Modify: `backend/app/sinks/obsidian.py`
- Create: `backend/tests/sinks/test_obsidian_paper_publish.py`

**Step 1: Write the failing sink test**

Cover:

- digest reports publish to a dated digest path
- note reports publish to a stable per-paper path
- repeated note publish reuses the same file path based on `paper_identity`
- digest content links to note files with predictable relative paths

**Step 2: Run test to verify it fails**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/sinks/test_obsidian_paper_publish.py -q
```

Expected:

- FAIL because the current sink writes every report directly to `vault_path/<title>.md`

**Step 3: Implement the sink behavior**

Add path-selection logic:

- digest: `DailyPapers/<report-date>-论文推荐.md`
- note: `DailyPapers/Papers/<paper-slug>.md`

Use stable identity order:

1. arXiv id
2. DOI
3. normalized title slug

Do not break non-paper report publishing.

**Step 4: Run the sink tests**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/sinks/test_obsidian_paper_publish.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/sinks/obsidian.py backend/tests/sinks/test_obsidian_paper_publish.py
git commit -m "feat: add paper-aware obsidian publishing"
```

### Task 8: Document and verify the end-to-end paper flow

**Files:**
- Modify: `README.md`
- Create: `docs/plans/2026-03-20-paper-report-design.md`
- Test: `backend/tests/renderers/test_paper_renderer.py`
- Test: `backend/tests/scheduler/test_orchestrator_e2e.py`
- Test: `backend/tests/sinks/test_obsidian_paper_publish.py`
- Test: `frontend/src/lib/report-content-parser.test.ts`
- Test: `frontend/src/app/monitors/page.test.tsx`

**Step 1: Update docs**

Describe:

- what `paper` means in the product
- that daily and weekly share the same skeleton
- that detailed notes are derived outputs, not a separate monitor type

**Step 2: Run the verification suite**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/renderers/test_paper_renderer.py backend/tests/scheduler/test_orchestrator_e2e.py backend/tests/sinks/test_obsidian_paper_publish.py -q
cd frontend && npm test -- src/lib/report-content-parser.test.ts src/app/monitors/page.test.tsx src/app/reports/[id]/page.test.tsx
```

Expected:

- all targeted backend and frontend tests pass

**Step 3: Run broader project verification**

Run:
```bash
./.venv/bin/python -m pytest backend/tests -q
cd frontend && npm run lint && npm run build
```

Expected:

- no regressions related to report type contracts, rendering, or publishing

**Step 4: Commit**

```bash
git add README.md docs/plans/2026-03-20-paper-report-design.md
git commit -m "docs: describe paper reporting flow"
```
