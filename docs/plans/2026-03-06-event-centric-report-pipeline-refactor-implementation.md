# Event-Centric Report Pipeline Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将当前“文章级加工 -> 规则聚合 -> 报告渲染”的主链路，重构为“文章筛选 -> 候选事件召回 -> 事件级提炼 -> 全局摘要 -> 报告渲染”的事件中心流水线，同时尽量复用现有 routing、replay、持久化与发布基础设施。

**Architecture:** 采用渐进式重构而不是推倒重写。P0 首先保留 `window_filter`、`filter`、`report`、`publish` 现有边界，在 `filter` 之后插入“候选事件召回”，并将现有 `keywords` 的职责从“单篇文章提炼”迁移为“事件组提炼”；`renderer` 改为消费事件对象，`report` 继续负责全局摘要补强。P1 再视稳定性决定是否把 `keywords` 正式拆成新的 `event_extract` routing stage。

**Tech Stack:** Python 3.12、asyncio、SQLAlchemy、现有 provider routing、Markdown renderer、pytest、`replay_monitor_after_window.py`、固定测试基线包

---

## Implementation Notes

- 执行时强制使用 `@test-driven-development`：所有重构都以固定基线回放和新增单测作为护栏。
- 完成前强制使用 `@verification-before-completion`：必须拿固定导出目录跑阶段回放与定向 pytest。
- P0 **不做 Alembic 迁移**：数据库仍以 `articles` 为主持久化单元，事件级结果先落在运行时对象与 `Report.metadata`。
- P0 **不改 `report.article_ids` 含义**：仍保留文章 ID 列表，保证现有详情页、落盘与追溯能力不坏。
- P0 **不新增 routing stage 名称**：优先复用现有 `filter / keywords / report` 三阶段，避免同步改动 schema、配置、provider 注册与前端配置页面。

---

## Phase Summary

- **P0 必做：** 引入事件对象、候选召回、事件级提炼、renderer 输入重构、replay 产物升级。
- **P1 可延后：** 将 `keywords` 正式改名为 `event_extract`，为同事件判定单独加 provider stage。
- **暂不做：** 新增事件表、长周期事件追踪、知识图谱落库。

---

### Task 1: Freeze the baseline and add event-centric fixtures

**Files:**
- Modify: `backend/tests/processors/test_pipeline.py`
- Modify: `backend/tests/renderers/test_daily_renderer.py`
- Modify: `backend/tests/scripts/test_replay_monitor_after_window.py`
- Create: `backend/tests/fixtures/event_pipeline/README.md`

**Step 1: Write the failing tests**

```python
def test_pipeline_returns_event_level_artifacts_metadata() -> None:
    result = run_pipeline_fixture(...)
    assert "candidate_clusters" in result
    assert "events" in result


def test_daily_renderer_accepts_event_objects() -> None:
    report = render_daily_report(events=[sample_event()], context=sample_context())
    assert report.metadata["events"][0]["event_title"] == "OpenAI 发布 GPT-5"
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest -q tests/processors/test_pipeline.py tests/renderers/test_daily_renderer.py tests/scripts/test_replay_monitor_after_window.py`
Expected: FAIL because current pipeline/render output is still article-centric.

**Step 3: Add fixture documentation**

```markdown
固定使用 `/Users/leo/workspace/Lexmount/LexDeepResearch/test_data/monitor_d57ca87c-d31d-4ca9-a5ad-2766215c4b3b/saved_report_7cab1763-b3ed-490f-8ef8-7de10a79a7f7`
作为事件中心重构期间的统一回放基线。
```

**Step 4: Re-run tests to confirm only the new expectations fail**

Run: `cd backend && uv run pytest -q tests/processors/test_pipeline.py tests/renderers/test_daily_renderer.py -k event`
Expected: FAIL only on newly added event-centric assertions.

**Step 5: Commit**

```bash
git add backend/tests/processors/test_pipeline.py backend/tests/renderers/test_daily_renderer.py backend/tests/scripts/test_replay_monitor_after_window.py backend/tests/fixtures/event_pipeline/README.md
git commit -m "test: freeze event-centric pipeline baseline"
```

---

### Task 2: Introduce explicit event pipeline models

**Files:**
- Create: `backend/app/processors/event_models.py`
- Modify: `backend/app/processors/pipeline.py`
- Test: `backend/tests/processors/test_pipeline.py`

**Step 1: Write the failing tests**

```python
from app.processors.event_models import CandidateCluster, EventExtractionInput, ProcessedEvent


def test_processed_event_keeps_article_lineage() -> None:
    event = ProcessedEvent(
        event_id="openai-gpt5",
        title="OpenAI 发布 GPT-5",
        article_ids=["a1", "a2"],
        source_links=["https://openai.com/blog/gpt-5"],
    )
    assert event.article_ids == ["a1", "a2"]
    assert event.source_links == ["https://openai.com/blog/gpt-5"]
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest -q tests/processors/test_pipeline.py -k processed_event_keeps_article_lineage`
Expected: FAIL with `ModuleNotFoundError` or missing symbol.

**Step 3: Write minimal implementation**

```python
@dataclass(slots=True)
class CandidateCluster:
    cluster_id: str
    articles: list[RawArticle]
    source_ids: list[str]


@dataclass(slots=True)
class ProcessedEvent:
    event_id: str
    title: str
    summary: str
    detail: str
    article_ids: list[str]
    source_links: list[str]
    category: str | None = None
    keywords: list[str] = field(default_factory=list)
    importance: str = "normal"
```

**Step 4: Update pipeline type hints**

```python
class PipelineOutput:
    events: list[ProcessedEvent]
    article_stage_trace: dict[str, dict]
    event_stage_trace: dict[str, dict]
```

**Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest -q tests/processors/test_pipeline.py -k processed_event_keeps_article_lineage`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/processors/event_models.py backend/app/processors/pipeline.py backend/tests/processors/test_pipeline.py
git commit -m "feat: add event-centric pipeline models"
```

---

### Task 3: Downgrade rule aggregation into candidate retrieval only

**Files:**
- Create: `backend/app/processors/candidate_cluster.py`
- Modify: `backend/app/processors/event_aggregator.py`
- Modify: `backend/app/processors/pipeline.py`
- Test: `backend/tests/processors/test_candidate_cluster.py`
- Modify: `backend/tests/renderers/test_daily_renderer.py`

**Step 1: Write the failing tests**

```python
from app.collectors.base import RawArticle
from app.processors.candidate_cluster import build_candidate_clusters


def test_candidate_cluster_groups_similar_articles_without_merging_output_fields() -> None:
    articles = [
        RawArticle(external_id="a1", title="OpenAI 发布 GPT-5", url="https://openai.com/blog/gpt-5", content="..."),
        RawArticle(external_id="a2", title="GPT-5 正式上线", url="https://news.site/gpt-5", content="..."),
    ]
    clusters = build_candidate_clusters(articles)
    assert len(clusters) == 1
    assert len(clusters[0].articles) == 2
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest -q tests/processors/test_candidate_cluster.py`
Expected: FAIL because module does not exist.

**Step 3: Write minimal implementation**

```python
def build_candidate_clusters(articles: list[RawArticle]) -> list[CandidateCluster]:
    # Reuse conservative token/time heuristics from event_aggregator,
    # but output clusters instead of final merged events.
    ...
```

**Step 4: Replace hard-final merge usage**

```python
# old
events = aggregate_events(raw_events)

# new
candidate_clusters = build_candidate_clusters(filtered_articles)
```

**Step 5: Run focused tests**

Run: `cd backend && uv run pytest -q tests/processors/test_candidate_cluster.py tests/renderers/test_daily_renderer.py -k cluster`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/processors/candidate_cluster.py backend/app/processors/event_aggregator.py backend/app/processors/pipeline.py backend/tests/processors/test_candidate_cluster.py backend/tests/renderers/test_daily_renderer.py
git commit -m "feat: add candidate clustering stage"
```

---

### Task 4: Move semantic extraction from article-level to event-group-level

**Files:**
- Modify: `backend/app/processors/pipeline.py`
- Create: `backend/app/processors/event_extract.py`
- Modify: `backend/app/prompts/agent/keywords.md`
- Modify: `backend/app/prompts/llm/keywords.md`
- Test: `backend/tests/processors/test_pipeline.py`
- Create: `backend/tests/processors/test_event_extract.py`
- Modify: `backend/tests/providers/test_keywords_content_prep.py`

**Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_keywords_stage_extracts_one_event_per_cluster(monkeypatch):
    output = await extract_events_from_clusters([sample_cluster_with_two_articles()])
    assert len(output) == 1
    assert output[0].article_ids == ["a1", "a2"]
    assert "GPT-5" in output[0].title
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest -q tests/processors/test_event_extract.py`
Expected: FAIL because extraction still expects single article payload.

**Step 3: Write minimal implementation**

```python
async def extract_events_from_clusters(clusters: list[CandidateCluster], ...) -> list[ProcessedEvent]:
    payload = {
        "primary_article": select_primary_article(cluster),
        "supporting_articles": cluster.articles[1:],
    }
    result, provider = await run_keywords_stage(payload=payload)
    return [ProcessedEvent(...)]
```

**Step 4: Keep routing compatibility**

```python
# P0 compatibility choice:
# continue using routing_profile.stages.keywords,
# but change the payload contract from single article to clustered event input.
```

**Step 5: Run focused tests**

Run: `cd backend && uv run pytest -q tests/processors/test_event_extract.py tests/processors/test_pipeline.py tests/providers/test_keywords_content_prep.py`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/processors/pipeline.py backend/app/processors/event_extract.py backend/app/prompts/agent/keywords.md backend/app/prompts/llm/keywords.md backend/tests/processors/test_event_extract.py backend/tests/processors/test_pipeline.py backend/tests/providers/test_keywords_content_prep.py
git commit -m "feat: extract events from candidate clusters"
```

---

### Task 5: Refactor renderer and orchestrator to consume processed events

**Files:**
- Modify: `backend/app/renderers/daily.py`
- Modify: `backend/app/renderers/base.py`
- Modify: `backend/app/scheduler/orchestrator.py`
- Modify: `backend/app/processors/content_quality_gate.py`
- Test: `backend/tests/renderers/test_daily_renderer.py`
- Modify: `backend/tests/scheduler/test_orchestrator_e2e.py`
- Modify: `backend/tests/scheduler/test_orchestrator_routing_overrides.py`

**Step 1: Write the failing tests**

```python
def test_daily_renderer_does_not_build_events_from_articles_anymore() -> None:
    event = sample_processed_event()
    report = DailyRenderer().render_sync([event], sample_context())
    assert report.metadata["events"][0]["article_ids"] == ["a1", "a2"]


@pytest.mark.asyncio
async def test_orchestrator_passes_events_into_renderer_and_report_stage(...) -> None:
    ...
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest -q tests/renderers/test_daily_renderer.py tests/scheduler/test_orchestrator_e2e.py`
Expected: FAIL because renderer still expects `ProcessedArticle`.

**Step 3: Write minimal implementation**

```python
async def render(self, events: list[ProcessedEvent], context: RenderContext) -> Report:
    global_tldr = _build_global_tldr(events)
    content = render_daily_report(events=events, context=context)
    return Report(..., metadata={"events": events, "global_tldr": global_tldr})
```

**Step 4: Move quality gate to event level**

```python
def apply_event_quality_gate(event: ProcessedEvent) -> ProcessedEvent:
    ...
```

**Step 5: Run focused tests**

Run: `cd backend && uv run pytest -q tests/renderers/test_daily_renderer.py tests/scheduler/test_orchestrator_e2e.py tests/scheduler/test_orchestrator_routing_overrides.py`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/renderers/daily.py backend/app/renderers/base.py backend/app/scheduler/orchestrator.py backend/app/processors/content_quality_gate.py backend/tests/renderers/test_daily_renderer.py backend/tests/scheduler/test_orchestrator_e2e.py backend/tests/scheduler/test_orchestrator_routing_overrides.py
git commit -m "refactor: render reports from processed events"
```

---

### Task 6: Upgrade replay artifacts and diagnostics to the new event flow

**Files:**
- Modify: `backend/scripts/replay_monitor_after_window.py`
- Modify: `test_data/README.md`
- Modify: `.spec/plans/active/2026-03-06-report-quality-modular-replay-implementation.md`
- Test: `backend/tests/scripts/test_replay_monitor_after_window.py`

**Step 1: Write the failing tests**

```python
def test_replay_persists_candidate_clusters_and_event_outputs(tmp_path) -> None:
    result = run_replay(...)
    assert (output_dir / "03_candidate_clusters.json").exists()
    assert (output_dir / "04_event_extract_output.json").exists()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest -q tests/scripts/test_replay_monitor_after_window.py -k candidate_clusters`
Expected: FAIL because replay still emits article-centric intermediates.

**Step 3: Write minimal implementation**

```python
ARTIFACTS = {
    "clusters": "03_candidate_clusters.json",
    "events": "04_event_extract_output.json",
    "render": "07_rendered_report.md",
}
```

**Step 4: Update docs**

```markdown
新的阶段化回放目录以事件为中心：
- `03_candidate_clusters.json`
- `04_event_extract_output.json`
- `05_aggregated_events.json`（若保留兼容别名）
```

**Step 5: Run focused tests**

Run: `cd backend && uv run pytest -q tests/scripts/test_replay_monitor_after_window.py`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/scripts/replay_monitor_after_window.py backend/tests/scripts/test_replay_monitor_after_window.py test_data/README.md .spec/plans/active/2026-03-06-report-quality-modular-replay-implementation.md
git commit -m "refactor: align replay artifacts with event-centric pipeline"
```

---

### Task 7: End-to-end verification on the frozen dataset

**Files:**
- Modify: `backend/tests/scheduler/test_orchestrator_e2e.py`
- Modify: `backend/tests/renderers/test_daily_renderer.py`
- Modify: `backend/tests/processors/test_pipeline.py`

**Step 1: Add final assertions**

```python
def test_event_centric_pipeline_reduces_duplicate_processing(...) -> None:
    result = replay_fixture(...)
    assert result["metrics"]["candidate_cluster_count"] <= result["metrics"]["filtered_article_count"]
    assert result["metrics"]["event_count"] <= result["metrics"]["candidate_cluster_count"]
```

**Step 2: Run targeted verification**

Run:

```bash
cd backend && uv run pytest -q \
  tests/processors/test_pipeline.py \
  tests/processors/test_event_extract.py \
  tests/processors/test_candidate_cluster.py \
  tests/renderers/test_daily_renderer.py \
  tests/scripts/test_replay_monitor_after_window.py \
  tests/scheduler/test_orchestrator_e2e.py \
  tests/scheduler/test_orchestrator_routing_overrides.py
```

Expected: PASS

**Step 3: Run frozen replay end-to-end**

Run:

```bash
cd backend && uv run python scripts/replay_monitor_after_window.py \
  --export-dir /Users/leo/workspace/Lexmount/LexDeepResearch/test_data/monitor_d57ca87c-d31d-4ca9-a5ad-2766215c4b3b/saved_report_7cab1763-b3ed-490f-8ef8-7de10a79a7f7 \
  --pipeline-mode rule
```

Expected:
- 成功输出最终报告
- 中间产物为事件中心结构
- 重复事件数低于当前基线

**Step 4: Commit**

```bash
git add backend/tests/processors/test_pipeline.py backend/tests/renderers/test_daily_renderer.py backend/tests/scheduler/test_orchestrator_e2e.py
git commit -m "test: verify event-centric report pipeline end to end"
```

---

## Recommended Execution Order

1. Task 1–2：先把“事件对象”立住，避免后续边改边猜。
2. Task 3：先把规则聚合降级为候选召回，缩小语义任务边界。
3. Task 4：把 `keywords` 改造成事件级提炼，这是本次重构的核心。
4. Task 5：再切 renderer / orchestrator，避免前后接口同时漂移。
5. Task 6–7：最后补 replay 和端到端验证，确保以后调质量仍可基于固定基线。

## Out of Scope

- 不新增 `events` 数据表
- 不修改前端 API 响应结构
- 不在本次重构中做知识图谱、事件时间线或跨日报事件延续
- 不在 P0 中拆出新的 routing stage schema 名称

## Risks and Guardrails

- **风险 1：** `keywords` 阶段 payload 改变后，现有 provider prompt 可能输出不稳  
  **护栏：** 先在测试里固定 cluster 输入与期望输出，再改 prompt。

- **风险 2：** renderer / report / replay 同时改动，容易出现接口漂移  
  **护栏：** 先定义 `ProcessedEvent`，所有边界都围绕它对齐。

- **风险 3：** 候选召回过宽导致 token 爆炸，过窄导致同事件拆散  
  **护栏：** 规则只做“保守召回”，宁可多给 LLM 一点候选，也不直接做最终裁决。

- **风险 4：** 内容质量门禁仍停留在文章级，导致事件级 detail 退化  
  **护栏：** Task 5 明确将 quality gate 迁到事件层。

Plan complete and saved to `docs/plans/2026-03-06-event-centric-report-pipeline-refactor-implementation.md`. Two execution options:

1. **Subagent-Driven (this session)** - 我在当前会话里按任务逐个推进、逐个验收  
2. **Parallel Session (separate)** - 新开一个会话，按 `executing-plans` 工作流批量执行

Which approach?
