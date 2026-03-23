# Monitor Agent Implementation Design

**Date:** 2026-03-23
**Status:** Draft
**Scope:** P0 Monitor Agent 的后端模块、API、前端页面与状态管理落位设计

---

## 1. Goal

在不修改现有 Monitor 核心数据模型的前提下，把 Monitor Agent 作为一层创建体验增强能力接入现有代码库。

目标不是重写 monitor 系统，而是复用现有：

- `POST /api/v1/monitors`
- `GET /api/v1/sources`
- 首页 `/`
- 现有 monitor/source/provider 数据结构

---

## 2. Current Code Anchors

当前实现中，与本功能直接相关的落点已经存在：

- 后端路由入口在 [backend/app/api/router.py](/Users/leo/workspace/Lexmount/insight-flow/backend/app/api/router.py)
- monitor API 在 [backend/app/api/v1/monitors.py](/Users/leo/workspace/Lexmount/insight-flow/backend/app/api/v1/monitors.py)
- monitor schema 在 [backend/app/schemas/monitor.py](/Users/leo/workspace/Lexmount/insight-flow/backend/app/schemas/monitor.py)
- source API 在 [backend/app/api/v1/sources.py](/Users/leo/workspace/Lexmount/insight-flow/backend/app/api/v1/sources.py)
- 当前首页在 [frontend/src/app/page.tsx](/Users/leo/workspace/Lexmount/insight-flow/frontend/src/app/page.tsx)
- 当前侧边栏在 [frontend/src/components/Sidebar.tsx](/Users/leo/workspace/Lexmount/insight-flow/frontend/src/components/Sidebar.tsx)
- 前端 API 封装在 [frontend/src/lib/api.ts](/Users/leo/workspace/Lexmount/insight-flow/frontend/src/lib/api.ts)

P0 设计应尽量贴着这些现有边界落地。

---

## 3. Backend Design

### 3.1 Module Layout

建议新增目录：

```text
backend/app/generators/
  monitor_agent.py
  monitor_agent_runtime.py
  monitor_agent_tools.py
  monitor_conversation_store.py
  monitor_generator.py
  source_catalog.py
  schedule_recommender.py
  source_catalog_metadata.yaml
```

职责划分：

- `monitor_agent.py`
  - 应用服务入口
  - 组织一次 `/monitors/agent` 请求
  - 管理会话读取、agent 调用、结果封装

- `monitor_agent_runtime.py`
  - 初始化 LangChain `create_agent`
  - 注册 tools
  - 定义 structured output
  - 屏蔽 LLM provider 细节

- `monitor_agent_tools.py`
  - 放所有 `@tool` / tool schema
  - 不直接处理 HTTP

- `monitor_conversation_store.py`
  - conversation state interface
  - In-memory TTL 实现
  - Redis TTL 实现

- `monitor_generator.py`
  - 组装 draft
  - 编译 `MonitorCreate`
  - 调用 validator

- `source_catalog.py`
  - 从 `sources` 表加载候选
  - 融合 metadata
  - 暴露检索与 shared source 查询

- `schedule_recommender.py`
  - 统一生成 `time_period + custom_schedule`

### 3.2 API Shape

P0 建议先把 agent endpoint 放在现有 monitor router 内，而不是新开 router。

即新增到 [backend/app/api/v1/monitors.py](/Users/leo/workspace/Lexmount/insight-flow/backend/app/api/v1/monitors.py)：

- `POST /api/v1/monitors/agent`

原因：

- 这是 monitor 创建流程的增强入口
- 避免新增新的资源命名空间
- 与现有 `POST /api/v1/monitors` 形成明显对应

### 3.3 Schema Placement

建议新增独立 schema 文件：

```text
backend/app/schemas/monitor_agent.py
```

包含：

- `MonitorAgentRequest`
- `MonitorAgentClarifyResponse`
- `MonitorAgentDraftResponse`
- `MonitorDraft`
- `DraftSection`
- `DraftItem*`

不要把这些类型继续塞进 [backend/app/schemas/monitor.py](/Users/leo/workspace/Lexmount/insight-flow/backend/app/schemas/monitor.py)，否则 monitor 持久化 contract 和 agent 展示 contract 会混在一起。

建议的 schema 分层：

```python
class MonitorAgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None


class MonitorAgentClarifyResponse(BaseModel):
    mode: Literal["clarify"]
    conversation_id: str
    message: str
    missing_or_conflicting_fields: list[str] = Field(default_factory=list)


class MonitorAgentDraftResponse(BaseModel):
    mode: Literal["draft"]
    conversation_id: str
    message: str | None = None
    draft: MonitorDraft
    monitor_payload: MonitorCreate
    inferred_fields: list[str] = Field(default_factory=list)
```

建议点：

- `monitor_payload` 直接使用 `MonitorCreate`，不要再定义一份近似 schema
- `conversation_id` 在响应中始终返回，避免前端分支判断
- `inferred_fields` 直接跟随 draft 返回，前端可用于提示“哪些内容是系统推断”

### 3.4 Conversation Store Design

建议定义统一接口：

```python
class MonitorConversationStore(Protocol):
    async def load(self, conversation_id: str) -> MonitorConversationState | None: ...
    async def save(self, state: MonitorConversationState) -> None: ...
    async def create(self) -> MonitorConversationState: ...
```

P0 实现：

- `InMemoryMonitorConversationStore`
- `RedisMonitorConversationStore`

选择策略：

- 本地开发默认内存版
- 正式部署优先 Redis 版

建议补充一个 factory：

```python
def build_monitor_conversation_store() -> MonitorConversationStore: ...
```

由配置决定返回：

- memory store
- redis store

这样 API 层不需要知道底层存储实现。

### 3.5 Source Catalog Metadata

P0 建议把补充 metadata 放成 YAML 文件，而不是数据库表。

建议文件：

```text
backend/app/generators/source_catalog_metadata.yaml
```

原因：

- 当前只是推荐层增强，不是核心业务数据
- 变更频率低
- 不引入 migration
- 便于人工维护

加载流程：

```text
sources table
  + source_catalog_metadata.yaml
  -> source_catalog.py
  -> normalized catalog entries
```

### 3.6 Compiler / Validator Boundary

P0 必须把这两层分开：

- `compile_monitor_payload(draft) -> MonitorCreate`
- `validate_monitor_payload(payload) -> normalized payload or errors`

`validate_monitor_payload()` 应复用当前后端真实约束：

- `window_hours: 1..168`
- `max_items/max_results: 1..200`
- `keywords/expanded_keywords <= 20`
- `source_ids` 必须是有效 UUID 且存在于库内

这层不要依赖 LLM。

### 3.7 Backend Request Flow

建议一次 `POST /api/v1/monitors/agent` 的后端调用链固定为：

```text
FastAPI route
  -> MonitorAgentService.handle_message()
  -> conversation_store.load_or_create()
  -> monitor_agent_runtime.invoke()
  -> monitor_generator.build_draft()
  -> monitor_generator.compile_monitor_payload()
  -> monitor_generator.validate_monitor_payload()
  -> conversation_store.save()
  -> response schema
```

建议把 `MonitorAgentService` 作为真正的编排入口，而不是让 route 里直接拼各种函数。

### 3.8 Suggested Backend Interfaces

```python
class MonitorAgentService:
    async def handle_message(self, request: MonitorAgentRequest) -> MonitorAgentClarifyResponse | MonitorAgentDraftResponse: ...


class MonitorAgentRuntime:
    async def invoke(
        self,
        *,
        message: str,
        state: MonitorConversationState,
    ) -> AgentPlan: ...


class MonitorGenerator:
    async def build_draft(
        self,
        *,
        plan: DraftPlan,
        state: MonitorConversationState,
    ) -> MonitorDraft: ...

    async def compile_monitor_payload(self, draft: MonitorDraft) -> MonitorCreate: ...

    async def validate_monitor_payload(self, payload: MonitorCreate) -> tuple[bool, list[str], MonitorCreate | None]: ...
```

边界要求：

- runtime 不直接读 DB
- generator 不直接处理 HTTP
- route 不直接操作 LangChain agent

---

## 4. Frontend Design

### 4.1 Page Ownership

P0 首页仍然使用 [frontend/src/app/page.tsx](/Users/leo/workspace/Lexmount/insight-flow/frontend/src/app/page.tsx) 作为入口页，但内容从“最近报告列表页”切成“Monitor Agent 首页”。

首页的职责将变成：

- 发起 agent 对话
- 展示 clarify / draft
- 编辑 draft
- 调用现有 `createMonitor()`
- 在页面下半部分保留最近报告概览

### 4.2 Suggested Component Split

建议新增组件目录：

```text
frontend/src/components/monitor-agent/
  AgentHero.tsx
  AgentComposer.tsx
  AgentMessageList.tsx
  ClarifyBubble.tsx
  MonitorDraftCard.tsx
  DraftSectionCard.tsx
  DraftEditableList.tsx
  DraftSchedulePicker.tsx
  DraftScopeEditor.tsx
```

职责：

- `AgentHero`
  - 欢迎语
  - 快捷 prompt 标签

- `AgentComposer`
  - 输入框
  - 发送状态

- `AgentMessageList`
  - 展示用户消息、clarify、draft 返回

- `MonitorDraftCard`
  - 展示草案主体
  - 管理局部编辑事件

- `DraftScopeEditor`
  - 编辑 `window_hours`
  - 编辑少量 `max_items/max_results`

建议再加两个非常小的纯展示组件：

- `InferenceNotice.tsx`
  - 显示“以下内容由系统自动补全”
- `AgentErrorBanner.tsx`
  - 显示 agent 请求失败或会话失效

### 4.3 Frontend API Layer

所有接口仍应经由 [frontend/src/lib/api.ts](/Users/leo/workspace/Lexmount/insight-flow/frontend/src/lib/api.ts)。

建议新增：

- `sendMonitorAgentMessage()`
- `MonitorAgentRequest`
- `MonitorAgentResponse`
- `MonitorDraft*` 类型

不要在页面组件里直接 `fetch("/api/v1/monitors/agent")`。

建议直接在 [frontend/src/lib/api.ts](/Users/leo/workspace/Lexmount/insight-flow/frontend/src/lib/api.ts) 中增加：

```ts
export interface MonitorAgentRequest {
  message: string;
  conversation_id?: string;
}

export type MonitorAgentResponse =
  | MonitorAgentClarifyResponse
  | MonitorAgentDraftResponse;

export const sendMonitorAgentMessage = (body: MonitorAgentRequest) =>
  fetchAPI<MonitorAgentResponse>("/api/v1/monitors/agent", {
    method: "POST",
    body: JSON.stringify(body),
  });
```

这样首页和未来可能的次级入口都能复用。

### 4.4 Frontend State Model

首页建议维持单页局部状态，不必引入全局 store。

建议状态结构：

```tsx
type MonitorAgentPageState = {
  conversationId?: string;
  messages: AgentMessage[];
  activeDraft?: DraftEditingState;
  submitting: boolean;
  saving: boolean;
  error?: string;
};
```

P0 没必要引入额外状态库，因为：

- 交互只发生在首页
- 生命周期短
- 刷新恢复不是 P0 必选

建议补一个更具体的消息结构：

```tsx
type AgentMessage =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; kind: "clarify"; text: string }
  | { id: string; role: "assistant"; kind: "draft"; draft: DraftEditingState };
```

这样 `AgentMessageList` 就不需要猜每条 assistant message 的类型。

### 4.5 Save Flow

保存链路应保持简单：

```text
effective draft
  -> compile on backend response
  -> frontend edits update effective draft
  -> frontend submits monitor_payload
  -> existing createMonitor()
```

P0 不建议再新增一个 agent confirm endpoint。

理由：

- 现有 `createMonitor()` 已存在
- draft 已经返回 `monitor_payload`
- 少一个接口，就少一个状态同步点

如果后续需要“服务端重新编译后再确认保存”，再加 `POST /api/v1/monitors/agent/confirm`。

### 4.6 Draft Edit Sync Strategy

P0 建议采用**前端编辑，本地形成 effective draft，保存时直接提交当前 payload** 的策略。

即：

```text
raw draft from backend
  + local user_edits
  -> effective draft
  -> derive monitor_payload in page state
  -> createMonitor()
```

建议原因：

- 页面交互更顺滑
- 减少每次编辑都回源后端的请求
- P0 编辑项有限，前端可控

约束：

- 前端对数值编辑也必须做基础边界限制
- 最终仍以后端 `POST /api/v1/monitors` 的校验为准

### 4.7 Sidebar And Homepage Migration

P0 前端改造涉及两个明显的现有文件：

- [frontend/src/components/Sidebar.tsx](/Users/leo/workspace/Lexmount/insight-flow/frontend/src/components/Sidebar.tsx)
- [frontend/src/app/page.tsx](/Users/leo/workspace/Lexmount/insight-flow/frontend/src/app/page.tsx)

建议迁移规则：

- `/` 导航文案从“报告”改为“首页”
- `/library` 导航文案从“归档”改为“报告”
- 首页仍保留一个“最近报告”区块，避免首页彻底失去内容感

---

## 5. Suggested File-Level Changes

### 5.1 Backend

- Modify: [backend/app/api/v1/monitors.py](/Users/leo/workspace/Lexmount/insight-flow/backend/app/api/v1/monitors.py)
- Add: [backend/app/schemas/monitor_agent.py](/Users/leo/workspace/Lexmount/insight-flow/backend/app/schemas/monitor_agent.py)
- Add: [backend/app/generators/monitor_agent.py](/Users/leo/workspace/Lexmount/insight-flow/backend/app/generators/monitor_agent.py)
- Add: [backend/app/generators/monitor_agent_runtime.py](/Users/leo/workspace/Lexmount/insight-flow/backend/app/generators/monitor_agent_runtime.py)
- Add: [backend/app/generators/monitor_agent_tools.py](/Users/leo/workspace/Lexmount/insight-flow/backend/app/generators/monitor_agent_tools.py)
- Add: [backend/app/generators/monitor_conversation_store.py](/Users/leo/workspace/Lexmount/insight-flow/backend/app/generators/monitor_conversation_store.py)
- Add: [backend/app/generators/monitor_generator.py](/Users/leo/workspace/Lexmount/insight-flow/backend/app/generators/monitor_generator.py)
- Add: [backend/app/generators/source_catalog.py](/Users/leo/workspace/Lexmount/insight-flow/backend/app/generators/source_catalog.py)
- Add: [backend/app/generators/schedule_recommender.py](/Users/leo/workspace/Lexmount/insight-flow/backend/app/generators/schedule_recommender.py)
- Add: [backend/app/generators/source_catalog_metadata.yaml](/Users/leo/workspace/Lexmount/insight-flow/backend/app/generators/source_catalog_metadata.yaml)

### 5.2 Frontend

- Modify: [frontend/src/app/page.tsx](/Users/leo/workspace/Lexmount/insight-flow/frontend/src/app/page.tsx)
- Modify: [frontend/src/components/Sidebar.tsx](/Users/leo/workspace/Lexmount/insight-flow/frontend/src/components/Sidebar.tsx)
- Modify: [frontend/src/lib/api.ts](/Users/leo/workspace/Lexmount/insight-flow/frontend/src/lib/api.ts)
- Add: [frontend/src/components/monitor-agent](/Users/leo/workspace/Lexmount/insight-flow/frontend/src/components/monitor-agent)
- Add tests under:
  - [frontend/src/app/page.test.tsx](/Users/leo/workspace/Lexmount/insight-flow/frontend/src/app/page.test.tsx)
  - [frontend/src/components](/Users/leo/workspace/Lexmount/insight-flow/frontend/src/components)

### 5.3 Suggested Delivery Slices

为了避免一次性改动过大，建议按下面的切片推进：

1. `schemas + service skeleton`
2. `source catalog + metadata`
3. `runtime + tools`
4. `agent endpoint`
5. `frontend api types`
6. `homepage shell + message flow`
7. `draft card + editing`
8. `save flow + polish`

这样每一层都可以单独验证，不会在最后一层才发现前面边界错了。

---

## 6. Data Flow

```text
User input on /
  -> sendMonitorAgentMessage()
  -> POST /api/v1/monitors/agent
  -> monitor_agent service
  -> runtime + tools + compiler + validator
  -> clarify or draft response
  -> page state update
  -> user edits draft
  -> createMonitor(monitor_payload)
  -> POST /api/v1/monitors
```

---

## 7. Error Handling Design

### 7.1 Backend

- tool failure: log and degrade
- LLM failure: return recoverable error
- validation failure: do not emit invalid draft silently

### 7.2 Frontend

- agent request failure：显示重试提示，不丢当前输入
- draft save failure：保留 draft，不清空卡片
- conversation expired：提示“会话已过期，请重新生成”

---

## 8. Testing Design

### 8.1 Backend

建议新增：

- service unit tests
- compiler / validator unit tests
- API contract tests for `/api/v1/monitors/agent`

重点验证：

- clarify upper bound = 3
- draft payload always valid
- UUID mapping uses real source IDs
- shared source registry missing时的降级策略

建议拆成三层：

- route tests
  - endpoint 返回 `clarify` / `draft` 的 schema 是否正确
- service tests
  - stop policy、conversation state、fallback 是否正确
- compiler tests
  - draft 到 `MonitorCreate` 的映射是否正确

### 8.2 Frontend

重点验证：

- 首页可发送 message
- clarify 与 draft 两种响应都能渲染
- draft 编辑会更新待保存 payload
- 保存失败不会丢失当前 draft
- 侧边栏名称切换正确

建议组件测试重点覆盖：

- `AgentComposer`
  - Enter / 提交按钮 / loading 态
- `MonitorDraftCard`
  - section 渲染、删除项、编辑 scope
- `AgentMessageList`
  - clarify / draft 两种 assistant 消息渲染

---

## 9. Rollout Recommendation

P0 实施顺序建议：

1. 后端 schema + compiler/validator
2. source catalog + metadata
3. agent runtime + `/monitors/agent`
4. 前端首页改造
5. draft 卡片编辑
6. 指标与日志补齐

原因：

- compiler/validator 是整个链路的地基
- 如果先做 UI，再补 compiler，很容易出现“展示能跑，创建不稳定”

---

## 10. Recommendation

实现层最重要的不是“把 agent 接进来”，而是把职责切整齐：

- 首页负责交互
- API 层负责 contract
- runtime 负责理解和调用 tool
- generator 负责 draft 和 payload
- validator 负责兜底约束

这套边界一旦清楚，后面无论换 prompt、换模型、还是升级到 LangGraph，成本都会低很多。
