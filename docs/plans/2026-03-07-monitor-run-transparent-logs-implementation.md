# Monitor Run Transparent Logs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让真实 Monitor Run 在 UI logs 中可追踪地展示“采集了哪些条目、窗口过滤后保留/丢弃了哪些、AI 筛选后保留/丢弃了哪些、候选聚类长什么样、最终报告事件是什么”，同时把完整明细落成 run artifacts。

**Architecture:** 采用“结构化事件 payload + 调试 artifacts”的混合方案。后端在 orchestrator 的 collect / window_filter / pipeline_filter / candidate_cluster / keywords / report_events / report 阶段追加结构化 `TaskEvent.payload`，前端将这些 payload 渲染成可读的调试卡片；完整列表则同步写入 `output/run_artifacts/<run_id>/...json`，避免 UI payload 失控。

**Tech Stack:** Python 3.12、asyncio、SQLAlchemy、FastAPI、React/Next.js、TypeScript、pytest、RTL

---

## Implementation Notes

- 执行时强制使用 `@test-driven-development`：后端 payload 结构与前端渲染都先补红测。
- 完成前强制使用 `@verification-before-completion`：至少跑后端日志回归和前端组件回归。
- 本次只记录调试需要的**结构化摘要字段**，**不把全文 raw content 塞进 UI logs**。
- artifact 文件保存完整条目清单，UI logs 只展示必要字段与 artifact 路径。
- 先保证真实 run 可观测，**不改 reports/articles 的主业务模型**。

---

### Task 1: Define structured transparent-log payloads

**Files:**
- Create: `backend/app/scheduler/run_debug.py`
- Modify: `backend/tests/scheduler/test_task_events_file_log.py`
- Modify: `backend/tests/processors/test_window_filter.py`

**Step 1: Write the failing tests**

```python
def test_build_article_log_items_keeps_safe_debug_fields() -> None:
    items = build_article_log_items([...])
    assert items[0]["title"] == "GPT-5.3 Instant"
    assert "content" not in items[0]


def test_build_window_filter_decision_payload_includes_kept_and_dropped_lists() -> None:
    payload = build_window_filter_payload(...)
    assert payload["sections"][0]["title"] == "Kept Items"
    assert payload["sections"][1]["title"] == "Dropped Items"
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest -q tests/processors/test_window_filter.py tests/scheduler/test_task_events_file_log.py -k 'log_items or window_filter_payload'`
Expected: FAIL because helpers do not exist.

**Step 3: Write minimal implementation**

```python
def build_article_log_items(...) -> list[dict]:
    ...

def build_window_filter_payload(...) -> dict:
    ...
```

**Step 4: Run focused tests**

Run: `cd backend && uv run pytest -q tests/processors/test_window_filter.py tests/scheduler/test_task_events_file_log.py -k 'log_items or window_filter_payload'`
Expected: PASS

---

### Task 2: Emit collect/window/pipeline transparency events in real runs

**Files:**
- Modify: `backend/app/scheduler/orchestrator.py`
- Modify: `backend/app/processors/pipeline.py`
- Test: `backend/tests/scheduler/test_orchestrator_e2e.py`
- Test: `backend/tests/scripts/test_replay_monitor_after_window.py`

**Step 1: Write the failing tests**

```python
async def test_monitor_run_events_include_collect_and_filter_item_details(...) -> None:
    events = await run_monitor(...)
    assert any(event["event_type"] == "source_collected_detail" for event in events)
    assert any(event["event_type"] == "pipeline_filter_completed" for event in events)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest -q tests/scheduler/test_orchestrator_e2e.py -k 'source_collected_detail or pipeline_filter_completed'`
Expected: FAIL because events are not emitted yet.

**Step 3: Write minimal implementation**

```python
await append_task_event(..., event_type="source_collected_detail", payload=...)
await append_task_event(..., event_type="pipeline_filter_completed", payload=...)
await append_task_event(..., event_type="candidate_cluster_completed", payload=...)
await append_task_event(..., event_type="keywords_completed", payload=...)
```

**Step 4: Run focused tests**

Run: `cd backend && uv run pytest -q tests/scheduler/test_orchestrator_e2e.py tests/scripts/test_replay_monitor_after_window.py -k 'filter_completed or candidate_cluster_completed or keywords_completed'`
Expected: PASS

---

### Task 3: Persist run artifacts for full debug trails

**Files:**
- Modify: `backend/app/scheduler/run_debug.py`
- Modify: `backend/app/scheduler/orchestrator.py`
- Test: `backend/tests/scheduler/test_task_events_file_log.py`

**Step 1: Write the failing test**

```python
def test_write_run_debug_artifact_creates_expected_json_path(tmp_path) -> None:
    path = write_run_debug_artifact(...)
    assert path.endswith("03_pipeline_filter_kept.json")
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest -q tests/scheduler/test_task_events_file_log.py -k run_debug_artifact`
Expected: FAIL because artifact writer does not exist.

**Step 3: Write minimal implementation**

```python
def write_run_debug_artifact(...) -> str:
    ...
```

**Step 4: Run focused tests**

Run: `cd backend && uv run pytest -q tests/scheduler/test_task_events_file_log.py -k run_debug_artifact`
Expected: PASS

---

### Task 4: Render structured payloads in the Monitor Run UI

**Files:**
- Create: `frontend/src/components/monitor/RunEventPayload.tsx`
- Create: `frontend/src/components/monitor/RunEventPayload.test.tsx`
- Modify: `frontend/src/app/monitors/page.tsx`
- Modify: `frontend/src/lib/api.ts`

**Step 1: Write the failing test**

```tsx
it("renders kept and dropped sections for transparent log payloads", () => {
  render(<RunEventPayload payload={samplePayload} />);
  expect(screen.getByText("Kept Items")).toBeInTheDocument();
  expect(screen.getByText("Dropped Items")).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- RunEventPayload`
Expected: FAIL because component does not exist.

**Step 3: Write minimal implementation**

```tsx
export function RunEventPayload({ payload }: Props) {
  if (!isTransparentPayload(payload)) return <pre>...</pre>;
  return ...
}
```

**Step 4: Wire page to use component**

```tsx
{hasPayload && <RunEventPayload payload={event.payload} />}
```

**Step 5: Run focused tests**

Run: `cd frontend && npm test -- RunEventPayload`
Expected: PASS

---

### Task 5: Verify end-to-end transparency on a real run

**Files:**
- No code changes required

**Step 1: Run backend regression**

Run: `cd backend && uv run pytest -q tests/processors/test_window_filter.py tests/scheduler/test_orchestrator_e2e.py tests/scheduler/test_task_events_file_log.py tests/processors/test_pipeline.py tests/routing/test_routing_loader.py`
Expected: PASS

**Step 2: Run frontend regression**

Run: `cd frontend && npm test -- RunEventPayload`
Expected: PASS

**Step 3: Trigger a real monitor run**

Run the monitor from UI or call the run endpoint, then inspect:
- `/api/v1/monitors/{monitor_id}/runs/{run_id}/events`
- `output/run_artifacts/<run_id>/`

Expected:
- collect/window/filter/cluster/keywords/report events all visible
- payload contains readable item lists
- artifact paths resolve to JSON files with complete details
