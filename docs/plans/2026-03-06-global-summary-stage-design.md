# Global Summary Stage Design

**Goal:** 将当前散落在 renderer / report rewrite 中的“全局摘要”语义职责，抽成独立的 `global_summary` 阶段，使事件级提炼、全局总结、报告组装三件事边界清晰，并支持 replay 单独评测。

**Status:** Approved for next implementation slice

---

## 1. Context

当前事件中心流水线已经具备：

- `window -> filter -> candidate_cluster -> event_extract -> aggregate -> render`
- replay 可落盘 `candidate_cluster` 与 `event_extract` 中间产物
- renderer 可直接消费 `ProcessedEvent`

但“全局摘要”仍存在两个问题：

1. `/Users/leo/workspace/Lexmount/LexDeepResearch/backend/app/renderers/daily.py` 里的 `_build_global_tldr()` 仍是规则拼接，语义质量不稳定。
2. report stage 目前更像“润色/重写”，而不是明确接收事件级事实后生成全局摘要。

这会导致：

- 难以单独评估“总结能力”；
- renderer 继续承担语义理解职责；
- replay 仍缺少一个关键阶段的中间产物。

---

## 2. Design Principles

- **语义判断优先交给 LLM/Agent。** `global_summary` 的主输出应由模型生成，而不是规则拼接。
- **规则只做硬约束与 fallback。** 例如空输入处理、长度裁剪、字段校验、兜底摘要。
- **render 只负责组装，不再负责总结。** renderer 可保留兜底逻辑，但不再是主路径。
- **report stage 只做表达层润色。** 它不再承担第一次全局理解。
- **replay 必须支持单独停靠与恢复。** `global_summary` 必须成为可落盘、可复跑的显式阶段。

---

## 3. Options

### Option A：继续把摘要逻辑留在 renderer

**做法：**
- 保留 `_build_global_tldr(events)` 为主逻辑。
- report stage 只在最后改写一句话摘要。

**优点：**
- 改动最小。

**缺点：**
- 语义质量仍受规则上限限制。
- 无法独立测试“事件总结”能力。
- 与“语义职责交给 LLM”原则冲突。

**结论：** 不推荐。

### Option B：复用现有 report stage 兼任 global summary

**做法：**
- 不新增 routing stage。
- 先把事件列表送入 report provider，只取 `global_tldr`，再进入 renderer。

**优点：**
- 代码改动较少。
- 可复用现有 provider 和 prompt 基础设施。

**缺点：**
- `report` 与 `global_summary` 职责混在一起。
- replay 指标和中间产物语义不清晰。
- 后续若要分别调优“摘要”和“整稿重写”，会互相干扰。

**结论：** 可作为短期兼容方案，但不适合作为目标结构。

### Option C：新增显式 `global_summary` 阶段

**做法：**
- 在 `aggregate` 之后、`render` 之前新增独立阶段。
- 输入为聚合后的事件列表，输出为结构化 `GlobalSummary`。
- renderer 只消费 `events + global_summary` 组装报告。

**优点：**
- 模块边界清晰，最符合事件中心流水线。
- replay 可以单独评测总结质量。
- renderer/report 各司其职，后续更容易优化。

**缺点：**
- 需要扩展 routing schema、provider registry、replay artifact。

**结论：** 推荐方案。

---

## 4. Recommended Design

### 4.1 Pipeline Placement

目标主链路调整为：

`window -> filter -> candidate_cluster -> event_extract -> aggregate -> global_summary -> render -> report`

职责划分：

- `candidate_cluster`：弱规则召回候选同事件
- `event_extract`：LLM/Agent 逐事件提炼事实
- `aggregate`：仅做轻量报告级整理与索引
- `global_summary`：LLM/Agent 基于全部事件做全局总结
- `render`：组装 Markdown/metadata
- `report`：可选的文风润色或标题微调

### 4.2 Stage Contract

新增结构化输出对象：

```python
@dataclass(slots=True)
class GlobalSummary:
    global_tldr: str
    provider: str = ""
    fallback_used: bool = False
    prompt_metrics: dict[str, int | bool] = field(default_factory=dict)
```

P0 只要求：

- `global_tldr`：1~3 句全局摘要
- `provider`：实际 provider 名称
- `fallback_used`：是否走规则兜底
- `prompt_metrics`：输入/输出字符数等基础指标

P1 可扩展但先不做：

- `themes`
- `watchpoints`
- `uncertainties`

### 4.3 Routing & Provider

推荐为 routing 新增显式阶段：

- `RoutingStages.global_summary: StageRoute`

默认策略建议：

- primary: `llm_openai`
- fallback: `agent_codex`

原因：

- 该阶段是短文本总结，优先使用稳定、成本更低的 LLM；
- 复杂 case 再退到 agent。

如果 routing 配置暂时未扩展完成，可在第一版实现中先：

- 允许 `global_summary` 复用 `report` route 作为兼容 fallback；
- 但代码内仍保留独立 helper / artifact / metrics，避免职责重新混淆。

### 4.4 Prompt Payload

`global_summary` 输入不应是整篇 report 文本，而应是结构化事件列表压缩版：

```json
[
  {
    "index": 1,
    "category": "模型发布",
    "title": "OpenAI 发布 GPT-5",
    "summary": "更强推理与更低延迟。",
    "detail": "...",
    "source_count": 3,
    "importance": "high",
    "who": "OpenAI",
    "what": "发布 GPT-5",
    "when": "2026-03-06"
  }
]
```

约束：

- 使用聚合后的事件，而不是原始文章；
- `detail` 应截断，避免 prompt 膨胀；
- 模型只做总结，不再重新发明事件事实。

### 4.5 Renderer Responsibility

`render_daily_report(...)` 改为接受可选的 `global_summary` 输入：

```python
render_daily_report(
    events=aggregated_events,
    context=context,
    global_summary=summary.global_tldr,
)
```

renderer 只做：

- 模板组装
- category overview 规则分组
- metadata 写入

renderer 仍保留 `_build_global_tldr()`，但仅作为：

- stage provider 失败时的兜底；
- 老链路兼容；
- replay/测试的 fallback evidence

### 4.6 Replay Changes

replay 新增阶段：

- artifact: `06_global_summary.json`
- `--stop-after` 新选项：`global_summary`
- `--resume-from` 新选项：`global_summary`

metrics 至少新增：

- `global_summary_provider_used`
- `global_summary_chars`
- `global_summary_fallback_used`

这样可以单独比较：

- 事件提炼没变时，不同 global summary prompt 的效果差异；
- renderer/report 不变时，全局摘要是否改善。

---

## 5. Rule vs LLM Boundary

### 适合规则

- 空输入返回空摘要
- 长度裁剪
- provider 输出字段校验
- fallback 兜底
- metadata / artifact 序列化

### 适合 LLM/Agent

- 从多事件中提炼当天主线
- 识别跨事件共性趋势
- 判断哪些事件该进入全局一句话摘要
- 生成更自然的中文总结表达

---

## 6. Testing Strategy

### P0 单元测试

- `GlobalSummary` 输出结构是否稳定
- provider payload 是否基于聚合事件构造
- fallback 是否只在 provider 失败或空输出时触发

### P0 replay 测试

- `stop_after=global_summary` 会落 `06_global_summary.json`
- `resume_from=global_summary` 会复用上游事件产物
- metrics 正确记录 provider / fallback / chars

### P0 集成测试

- renderer 接收外部 `global_summary` 时不再调用主路径 heuristic
- orchestrator 将 `global_summary` 写入 report metadata

---

## 7. Migration Notes

- 第一阶段不直接切生产 orchestrator 到全事件中心持久化，只把 `global_summary` 插入现有报告生成链路。
- `_build_global_tldr()` 暂时保留，直到 `global_summary` 在 replay 基线上的质量稳定。
- 如果 routing/config 变更面过大，允许先以 helper 形式接入，再在下一步补齐 schema 与 monitor override。

---

## 8. Success Criteria

以下条件满足时，可认为该阶段落地成功：

- replay 中出现独立 `global_summary` artifact
- renderer 不再承担主路径语义总结
- report metadata 的 `global_tldr` 来自显式阶段而非 renderer 规则拼接
- 同一份 replay 基线上，可只重跑 `global_summary` 评估摘要质量
