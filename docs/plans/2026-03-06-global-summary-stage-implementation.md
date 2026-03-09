# Global Summary Stage Implementation Plan

**Goal:** 在事件中心流水线中新增显式 `global_summary` 阶段，用 LLM/Agent 对聚合后事件生成全局摘要，并让 replay、renderer、orchestrator 都消费这一阶段的结果。

**Architecture:** 以“独立 stage + 独立 artifact + 兼容 fallback”的方式推进。首版先引入 `GlobalSummary` 对象与 replay/renderer/orchestrator 集成，保留 renderer 规则摘要仅作 fallback；随后再补齐 routing schema 与 monitor override 的完整支持。

**Tech Stack:** Python 3.12、asyncio、现有 provider registry、routing profile、Markdown renderer、pytest、replay CLI

---

## Implementation Notes

- 继续沿用事件中心主链路：`window -> filter -> candidate_cluster -> event_extract -> aggregate -> global_summary -> render -> report`
- 语义总结优先由 LLM/Agent 完成，规则仅做字段校验、fallback 和格式化。
- 第一版不扩大数据库 schema；`global_summary` 先通过 `Report.metadata` 与 replay artifact 承载。

---

### Task 1: Add `GlobalSummary` model and stage helper

**Files:**
- Create: `backend/app/processors/global_summary.py`
- Modify: `backend/app/processors/event_models.py`
- Test: `backend/tests/processors/test_global_summary.py`

**Step 1: Write failing tests**

覆盖：

- `build_global_summary_fallback(events)` 在空输入时返回空摘要
- `run_global_summary_stage(...)` 成功时返回 `GlobalSummary`
- provider 失败时会退回 heuristic fallback

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest -q tests/processors/test_global_summary.py`

**Step 3: Write minimal implementation**

- 在 `event_models.py` 新增 `GlobalSummary`
- 在 `global_summary.py` 提供：
  - `build_global_summary_payload(events: list[dict]) -> dict`
  - `build_global_summary_fallback(events: list[dict]) -> str`
  - `run_global_summary_stage(...) -> tuple[GlobalSummary, str]`

**Step 4: Re-run focused tests**

Run: `cd backend && uv run pytest -q tests/processors/test_global_summary.py`

---

### Task 2: Add provider + prompts for `global_summary`

**Files:**
- Create: `backend/app/providers/global_summary.py`
- Modify: `backend/app/providers/registry.py`
- Create: `backend/app/prompts/agent/global_summary.md`
- Create: `backend/app/prompts/llm/global_summary.md`
- Test: `backend/tests/providers/test_global_summary_provider.py`

**Step 1: Write failing tests**

覆盖：

- provider 注册到 `stage=\"global_summary\"`
- prompt payload 基于聚合事件压缩版，而非 report markdown
- 空输出时 helper 触发 fallback

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest -q tests/providers/test_global_summary_provider.py`

**Step 3: Write minimal implementation**

- 参照 `report.py` 实现一个轻量版 `global_summary` provider
- 输出字段至少包含 `global_tldr` 和 `summary_metrics`

**Step 4: Re-run focused tests**

Run: `cd backend && uv run pytest -q tests/providers/test_global_summary_provider.py tests/processors/test_global_summary.py`

---

### Task 3: Extend routing schema and config compatibility

**Files:**
- Modify: `backend/app/routing/schema.py`
- Modify: `backend/app/routing/loader.py`
- Modify: `backend/app/schemas/monitor.py`
- Test: `backend/tests/routing/test_routing_loader.py`
- Test: `backend/tests/scheduler/test_orchestrator_routing_overrides.py`

**Step 1: Write failing tests**

覆盖：

- `RoutingStages` 新增 `global_summary`
- 未配置时使用兼容默认值
- monitor override 可单独覆盖 `global_summary`

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest -q tests/routing/test_routing_loader.py tests/scheduler/test_orchestrator_routing_overrides.py -k global_summary`

**Step 3: Write minimal implementation**

- 在 schema/loader 中加入 `global_summary`
- 缺省 route 可先与 `report` 保持同类 provider 组合

**Step 4: Re-run focused tests**

Run: `cd backend && uv run pytest -q tests/routing/test_routing_loader.py tests/scheduler/test_orchestrator_routing_overrides.py -k global_summary`

---

### Task 4: Integrate `global_summary` into replay

**Files:**
- Modify: `backend/scripts/replay_monitor_after_window.py`
- Modify: `backend/tests/scripts/test_replay_monitor_after_window.py`

**Step 1: Write failing tests**

覆盖：

- 新增 artifact `06_global_summary.json`
- `stop_after=global_summary` 落盘并退出
- `resume_from=global_summary` 复用上游 `aggregate` 产物
- `metrics.json` 新增 `global_summary_provider_used` / `global_summary_chars` / `global_summary_fallback_used`

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest -q tests/scripts/test_replay_monitor_after_window.py -k global_summary`

**Step 3: Write minimal implementation**

- 新增 artifact 常量与序列化 helper
- 在 `aggregate` 后执行 `global_summary`
- 扩展 CLI 的 `--stop-after` / `--resume-from`

**Step 4: Re-run focused tests**

Run: `cd backend && uv run pytest -q tests/scripts/test_replay_monitor_after_window.py`

---

### Task 5: Make renderer consume external summary first

**Files:**
- Modify: `backend/app/renderers/daily.py`
- Test: `backend/tests/renderers/test_daily_renderer.py`

**Step 1: Write failing tests**

覆盖：

- `render_daily_report(..., global_summary=\"...\")` 优先使用外部摘要
- 未传入时仍保留旧 fallback

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest -q tests/renderers/test_daily_renderer.py -k global_summary`

**Step 3: Write minimal implementation**

- 给 `render_daily_report` 增加可选参数
- metadata 中记录 `global_tldr` 来源

**Step 4: Re-run focused tests**

Run: `cd backend && uv run pytest -q tests/renderers/test_daily_renderer.py -k global_summary`

---

### Task 6: Integrate orchestrator without full production rewrite

**Files:**
- Modify: `backend/app/scheduler/orchestrator.py`
- Test: `backend/tests/scheduler/test_orchestrator_e2e.py`

**Step 1: Write failing tests**

覆盖：

- orchestrator 在 `build_daily_events(...)` 后调用 `global_summary`
- 持久化到 report metadata 的 `global_tldr` 来源于新 stage
- report stage 只接收已经生成的 `global_tldr`

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest -q tests/scheduler/test_orchestrator_e2e.py -k global_summary`

**Step 3: Write minimal implementation**

- 新增 orchestrator helper
- 在不改数据库 schema 的前提下，把摘要落到 `Report.metadata`

**Step 4: Re-run focused tests**

Run: `cd backend && uv run pytest -q tests/scheduler/test_orchestrator_e2e.py -k global_summary`

---

### Task 7: Run regression slice on event-centric path

**Files:**
- Existing tests only

**Step 1: Run targeted regression**

```bash
cd backend && uv run pytest -q \
  tests/processors/test_candidate_cluster.py \
  tests/processors/test_event_extract.py \
  tests/processors/test_global_summary.py \
  tests/providers/test_global_summary_provider.py \
  tests/renderers/test_daily_renderer.py \
  tests/scripts/test_replay_monitor_after_window.py \
  tests/scheduler/test_orchestrator_e2e.py \
  tests/scheduler/test_orchestrator_routing_overrides.py
```

**Step 2: Run one frozen replay**

```bash
cd backend && uv run python scripts/replay_monitor_after_window.py \
  --export-dir ../test_data/<dataset> \
  --output-dir ../test_data/<dataset>/_replay_global_summary \
  --pipeline-mode rule \
  --stop-after global_summary
```

**Step 3: Validate artifacts**

确认存在：

- `03_candidate_clusters.json`
- `04_event_extract_output.json`
- `05_aggregated_events.json`
- `06_global_summary.json`
- `metrics.json`

---

## Rollout Order

1. 先补模型与 helper，避免 renderer/orchestrator 同时漂移。
2. 再接 provider 与 routing，确保 `global_summary` 是显式 stage。
3. 然后改 replay，先在固定基线上验证摘要质量。
4. 最后再接 renderer/orchestrator，而不是先碰生产大链路。

---

## Success Criteria

- `global_summary` 成为独立可测试模块
- replay 可单独停在 `global_summary`
- renderer 不再主导全局摘要语义
- orchestrator/report metadata 使用显式 `global_summary` 结果
