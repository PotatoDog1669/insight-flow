# Paper Content Quality Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the `paper` workflow so digest and note content are generated through dedicated paper-specific AI stages and render directly into higher-quality Obsidian-friendly markdown.

**Architecture:** Keep the existing collector, paper identity, report storage, and sink path model, but replace the current middle layer with two new AI stages: `paper_review` for digest-level ranking and editorial copy, and `paper_note` for selected-paper structured note generation. The scheduler should call these stages inside the existing `paper` report branch, then render one digest plus linked notes using thin templates and metadata-driven backfilling.

**Tech Stack:** FastAPI, Python 3.12, SQLAlchemy async session flow, Jinja2 templates, pytest, Next.js, TypeScript, React Testing Library

---

### Task 1: Extend routing and provider infrastructure for paper-specific stages

**Files:**
- Modify: `config.yaml`
- Modify: `backend/app/routing/schema.py`
- Modify: `backend/app/routing/loader.py`
- Modify: `backend/app/providers/registry.py`
- Modify: `backend/tests/routing/test_routing_loader.py`
- Modify: `backend/tests/providers/test_provider_registry.py`
- Modify: `backend/tests/prompts/test_prompt_registry.py`

**Step 1: Write the failing infrastructure tests**

Add coverage that verifies:

- routing profiles can load `paper_review` and `paper_note` stages
- the provider registry can resolve providers for those stages
- prompt registry can load `paper_review` and `paper_note` prompt files

**Step 2: Run tests to verify they fail**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/routing/test_routing_loader.py backend/tests/providers/test_provider_registry.py backend/tests/prompts/test_prompt_registry.py -q
```

Expected:

- FAIL because the routing schema, registry loader, and prompt coverage do not yet know about the paper-specific stages

**Step 3: Implement the infrastructure changes**

Update the routing model to add:

- `paper_review: StageRoute | None`
- `paper_note: StageRoute | None`

Load them from `config.yaml` with sensible defaults that mirror existing `llm_openai -> llm_codex` behavior.

Update the provider registry loader so it imports:

- `app.providers.paper_review`
- `app.providers.paper_note`

Do not expose these stages in monitor UI routing overrides for P0; keep them profile-driven only.

**Step 4: Run the infrastructure tests**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/routing/test_routing_loader.py backend/tests/providers/test_provider_registry.py backend/tests/prompts/test_prompt_registry.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add config.yaml backend/app/routing/schema.py backend/app/routing/loader.py backend/app/providers/registry.py backend/tests/routing/test_routing_loader.py backend/tests/providers/test_provider_registry.py backend/tests/prompts/test_prompt_registry.py
git commit -m "feat: add paper stage routing infrastructure"
```

### Task 2: Add `paper_review` prompts and providers

**Files:**
- Create: `backend/app/prompts/llm/paper_review.md`
- Create: `backend/app/providers/paper_review.py`
- Create: `backend/tests/providers/test_paper_review_provider.py`
- Create: `backend/tests/providers/test_paper_review_transport.py`

**Step 1: Write the failing provider tests**

Add coverage that verifies:

- the provider builds a prompt from a batch of paper candidates
- the provider normalizes a strict JSON response into digest-ready fields
- `llm_openai` and `llm_codex` transports both work for the new stage
- invalid or incomplete output raises a clear error instead of silently degrading

**Step 2: Run tests to verify they fail**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/providers/test_paper_review_provider.py backend/tests/providers/test_paper_review_transport.py -q
```

Expected:

- FAIL because no `paper_review` prompt or provider exists yet

**Step 3: Implement the prompt and providers**

Create a dedicated `paper_review` prompt that asks for:

- digest title
- digest summary
- ordered paper list
- recommendation level
- short editorial copy per paper
- note candidate decision

Implement `llm_openai` and `llm_codex` providers using the existing JSON transport helpers.

Normalize and validate:

- `recommendation` into a closed set such as `必读`, `值得看`, `可略读`
- `note_candidate` into `bool`
- list fields into bounded arrays
- text fields into predictable length limits

Keep the provider focused on contract construction and output normalization only.

**Step 4: Run the provider tests**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/providers/test_paper_review_provider.py backend/tests/providers/test_paper_review_transport.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/prompts/llm/paper_review.md backend/app/providers/paper_review.py backend/tests/providers/test_paper_review_provider.py backend/tests/providers/test_paper_review_transport.py
git commit -m "feat: add paper review provider"
```

### Task 3: Add `paper_note` prompts and providers

**Files:**
- Create: `backend/app/prompts/llm/paper_note.md`
- Create: `backend/app/providers/paper_note.py`
- Create: `backend/tests/providers/test_paper_note_provider.py`
- Create: `backend/tests/providers/test_paper_note_transport.py`

**Step 1: Write the failing provider tests**

Add coverage that verifies:

- the provider builds a prompt from one selected paper plus its source metadata
- the provider returns the note-specific structured sections
- transport integration works for both `llm_openai` and `llm_codex`
- malformed note payloads are rejected clearly

**Step 2: Run tests to verify they fail**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/providers/test_paper_note_provider.py backend/tests/providers/test_paper_note_transport.py -q
```

Expected:

- FAIL because no `paper_note` prompt or provider exists yet

**Step 3: Implement the prompt and providers**

Create a dedicated `paper_note` prompt that asks for:

- summary
- core contributions
- problem background
- method breakdown
- figure notes
- experiments
- strengths
- limitations
- related reading
- next steps

Use the same transport helpers and output-normalization pattern as other LLM-backed providers.

Keep the prompt grounded in available metadata and abstract-level evidence; do not imply fulltext access.

**Step 4: Run the provider tests**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/providers/test_paper_note_provider.py backend/tests/providers/test_paper_note_transport.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/prompts/llm/paper_note.md backend/app/providers/paper_note.py backend/tests/providers/test_paper_note_provider.py backend/tests/providers/test_paper_note_transport.py
git commit -m "feat: add paper note provider"
```

### Task 4: Add retry helpers and typed stage runners for `paper_review` and `paper_note`

**Files:**
- Create: `backend/app/processors/paper_review_stage.py`
- Create: `backend/app/processors/paper_note_stage.py`
- Create: `backend/tests/processors/test_paper_review_stage.py`
- Create: `backend/tests/processors/test_paper_note_stage.py`

**Step 1: Write the failing stage-runner tests**

Add coverage that verifies:

- the retry helper uses fallback providers after failures
- `ProviderUnavailableError` from `llm_openai` is re-raised consistently
- normalized outputs are returned together with provider names
- stage metrics are preserved in a simple shape for downstream metadata if needed later

**Step 2: Run tests to verify they fail**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/processors/test_paper_review_stage.py backend/tests/processors/test_paper_note_stage.py -q
```

Expected:

- FAIL because no stage runner helpers exist yet

**Step 3: Implement the stage helpers**

Mirror the existing `report_stage.py` and `global_summary.py` patterns:

- `run_paper_review_with_retry(...)`
- `run_paper_note_with_retry(...)`

Use routing profile providers and monitor overrides in the same style as the rest of the orchestrator.

Keep these helpers small and transport-agnostic.

**Step 4: Run the stage-runner tests**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/processors/test_paper_review_stage.py backend/tests/processors/test_paper_note_stage.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/processors/paper_review_stage.py backend/app/processors/paper_note_stage.py backend/tests/processors/test_paper_review_stage.py backend/tests/processors/test_paper_note_stage.py
git commit -m "feat: add paper stage runners"
```

### Task 5: Refactor paper rendering to consume stage payloads instead of generic article summaries

**Files:**
- Modify: `backend/app/renderers/paper.py`
- Modify: `backend/app/papers/reporting.py`
- Modify: `backend/app/templates/reports/paper/v1.md.j2`
- Modify: `backend/app/templates/reports/paper/note/v1.md.j2`
- Modify: `backend/app/templates/sinks/notion/reports/paper/v1.md.j2`
- Modify: `backend/app/templates/sinks/notion/reports/paper/note/v1.md.j2`
- Modify: `backend/tests/renderers/test_paper_renderer.py`
- Modify: `backend/tests/template_engine/test_paper_templates.py`

**Step 1: Write the failing renderer and template tests**

Add coverage that verifies:

- digest content now includes `## 分流表`
- digest entries render recommendation labels and richer editorial copy
- note rendering is driven by note-stage sections rather than generic fallback heuristics
- digest and note metadata preserve `paper_mode`, `paper_identity`, `paper_slug`, and note-link placeholders
- templates still render cleanly for Notion sink mode

**Step 2: Run tests to verify they fail**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/renderers/test_paper_renderer.py backend/tests/template_engine/test_paper_templates.py -q
```

Expected:

- FAIL because the renderer and templates still assume generic `ProcessedArticle` summary/detail-derived copy

**Step 3: Implement the rendering refactor**

Update `backend/app/papers/reporting.py` so it can:

- build digest reports from `paper_review` payloads
- build note reports from `paper_note` payloads
- preserve deterministic identity and linking helpers
- fall back conservatively only when stage payloads are missing

Update templates so they are mostly presentational:

- digest shows title, intro, triage table, then per-paper entries
- note shows structured reading-card sections

Keep the report body product-friendly first and Obsidian-friendly by default. Avoid sink-only markdown shape divergence.

**Step 4: Run the renderer and template tests**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/renderers/test_paper_renderer.py backend/tests/template_engine/test_paper_templates.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/renderers/paper.py backend/app/papers/reporting.py backend/app/templates/reports/paper/v1.md.j2 backend/app/templates/reports/paper/note/v1.md.j2 backend/app/templates/sinks/notion/reports/paper/v1.md.j2 backend/app/templates/sinks/notion/reports/paper/note/v1.md.j2 backend/tests/renderers/test_paper_renderer.py backend/tests/template_engine/test_paper_templates.py
git commit -m "feat: render paper reports from stage payloads"
```

### Task 6: Wire `paper_review` and `paper_note` into the scheduler

**Files:**
- Modify: `backend/app/scheduler/orchestrator.py`
- Modify: `backend/tests/scheduler/test_orchestrator_e2e.py`
- Modify: `backend/tests/scheduler/test_orchestrator_routing_overrides.py`

**Step 1: Write the failing scheduler tests**

Add coverage that verifies:

- a `paper` run calls `paper_review` before rendering the digest
- the digest order and recommendation labels come from the review payload
- only `note_candidate=true` papers invoke `paper_note`
- the resulting note report IDs are linked back into digest metadata and content
- paper-specific routes are loaded from the runtime routing profile

**Step 2: Run tests to verify they fail**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/scheduler/test_orchestrator_e2e.py backend/tests/scheduler/test_orchestrator_routing_overrides.py -q
```

Expected:

- FAIL because the current `paper` branch still renders directly from processed articles without stage-specific AI generation

**Step 3: Implement the scheduler changes**

In the `paper` branch:

- build a review payload from `ProcessedArticle` candidates
- call the `paper_review` stage through a new retry helper
- render the digest from the returned payload
- build note payloads only for selected papers
- call `paper_note` for each selected paper
- backfill note links and metadata

Keep persistence shape unchanged:

- one digest report row
- many note report rows
- `paper_mode` distinguishes them

**Step 4: Run the scheduler tests**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/scheduler/test_orchestrator_e2e.py backend/tests/scheduler/test_orchestrator_routing_overrides.py -q
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add backend/app/scheduler/orchestrator.py backend/tests/scheduler/test_orchestrator_e2e.py backend/tests/scheduler/test_orchestrator_routing_overrides.py
git commit -m "feat: generate paper content via dedicated stages"
```

### Task 7: Keep frontend rendering and content normalization aligned with the new markdown shape

**Files:**
- Modify: `frontend/src/lib/report-content-parser.ts`
- Modify: `frontend/src/lib/report-content-parser.test.ts`
- Modify: `frontend/src/app/reports/[id]/page.tsx`
- Modify: `frontend/src/app/reports/[id]/page.test.tsx`
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/app/page.test.tsx`
- Modify: `frontend/src/app/library/page.tsx`
- Modify: `frontend/src/app/library/page.test.tsx`
- Modify: `frontend/src/lib/paper-metadata.ts`
- Modify: `frontend/src/lib/paper-metadata.test.ts`

**Step 1: Write the failing frontend tests**

Add coverage that verifies:

- paper digests preserve authored markdown including `分流表`
- note-link patching still works with the richer digest structure
- note reports remain excluded from discovery and archive listing
- paper detail pages render the upgraded digest and note content without daily-report rewrites

**Step 2: Run tests to verify they fail**

Run:
```bash
cd frontend && npm test -- src/lib/report-content-parser.test.ts src/app/reports/[id]/page.test.tsx src/app/page.test.tsx src/app/library/page.test.tsx src/lib/paper-metadata.test.ts
```

Expected:

- FAIL because current parser assumptions are tied to the old digest structure

**Step 3: Implement the frontend alignment**

Update parsing and page rendering so that:

- paper content remains authored
- note link insertion remains robust
- richer metadata fields are tolerated safely

Do not re-canonicalize paper digest or note content into daily-report shapes.

**Step 4: Run the frontend tests**

Run:
```bash
cd frontend && npm test -- src/lib/report-content-parser.test.ts src/app/reports/[id]/page.test.tsx src/app/page.test.tsx src/app/library/page.test.tsx src/lib/paper-metadata.test.ts
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add frontend/src/lib/report-content-parser.ts frontend/src/lib/report-content-parser.test.ts frontend/src/app/reports/[id]/page.tsx frontend/src/app/reports/[id]/page.test.tsx frontend/src/app/page.tsx frontend/src/app/page.test.tsx frontend/src/app/library/page.tsx frontend/src/app/library/page.test.tsx frontend/src/lib/paper-metadata.ts frontend/src/lib/paper-metadata.test.ts
git commit -m "fix: preserve upgraded paper markdown in frontend"
```

### Task 8: Verify Obsidian publishing and end-to-end behavior

**Files:**
- Modify: `backend/app/sinks/obsidian.py`
- Modify: `backend/tests/sinks/test_obsidian_paper_publish.py`
- Modify: `README.md`

**Step 1: Write the failing sink and docs tests or assertions**

Add or extend coverage that verifies:

- digest publish still lands in `DailyPapers/<date>-论文推荐.md`
- note publish still lands in `DailyPapers/Papers/<paper-slug>.md`
- upgraded markdown bodies are written through without destructive sink rewriting

If `README.md` mentions the paper output shape, update it to reflect the new stage-driven workflow.

**Step 2: Run the sink tests to verify expectations**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/sinks/test_obsidian_paper_publish.py -q
```

Expected:

- PASS after sink behavior remains compatible with the upgraded content

**Step 3: Run focused end-to-end verification**

Run:
```bash
./.venv/bin/python -m pytest backend/tests/renderers/test_paper_renderer.py backend/tests/scheduler/test_orchestrator_e2e.py backend/tests/sinks/test_obsidian_paper_publish.py -q
cd frontend && npm test -- src/lib/report-content-parser.test.ts src/app/reports/[id]/page.test.tsx src/app/page.test.tsx src/app/library/page.test.tsx
```

Expected:

- PASS

**Step 4: Commit**

```bash
git add backend/app/sinks/obsidian.py backend/tests/sinks/test_obsidian_paper_publish.py README.md
git commit -m "docs: verify upgraded paper publishing flow"
```
