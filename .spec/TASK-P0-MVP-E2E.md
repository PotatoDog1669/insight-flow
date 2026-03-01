# Task: P0 MVP 端到端交付拆解（基于 PRD + TEC + 当前代码现状）

## 1) 最终目标（Definition of Done）

围绕 `PRD.md` 与 `TEC.md` 的 P0 范围，交付一个**端到端可运行**的 MVP：

- 覆盖 P0 信息源（技术博客 + 开源社区，优先 RSS / API）。
- 完成“采集 -> 筛选加工 -> 报告生成 -> 落盘 -> Dashboard 查看”的闭环。
- 前后端使用真实数据流，不依赖页面内 mock 常量。
- 核心 API、数据持久化与关键路径测试可稳定通过。

---

## 2) 当前项目状态快照（2026-02-28）

### 已具备

- 后端已有 FastAPI 基础结构、模型定义、部分 DB 化接口（如 monitors/reports/users）。
- 前端已有 Dashboard 页面骨架（Discover / Library / Sources / Monitors）。
- 已有 API 合同测试与持久化测试雏形（`backend/tests`）。

### 主要缺口

- 多个核心模块仍未实现：collectors、processors、orchestrator、scheduler、sinks。
- `sources/articles/tasks` 仍有 mock 或空实现，未统一走数据库。
- 前端多个页面与组件仍使用本地 mock 数据。
- Alembic 迁移目录为空（仅 `.gitkeep`），Schema 演进链路未建立。
- 后端测试当前非全绿（本地执行结果：`4 failed, 4 passed`）。

---

## 3) 子任务拆解（主任务 -> 子任务）

### 子任务 1：建立可重复的开发/测试基线

**目标**  
让测试与本地运行不依赖“手工准备状态”，先把工程地基稳住。

**范围**  
- 统一测试数据库策略（测试默认 SQLite / 或测试专用 Postgres 容器）。
- 规范 `DATABASE_URL` / `.env` 覆盖优先级，避免测试误连本地生产库。
- 修复当前测试收集与运行路径差异（根目录 vs `backend/`）。

**完成标准**  
- `backend` 下单命令可稳定运行测试。
- 合同测试和持久化测试可在 CI/本地一致执行。

**依赖**  
无（第一优先级）。

---

### 子任务 2：补齐数据库迁移与初始化链路

**目标**  
将模型定义落地为可迁移、可回滚的数据库结构。

**范围**  
- 生成首个 Alembic 迁移，覆盖 `users/sources/user_subscriptions/articles/reports/collect_tasks/monitors`。
- 建立种子数据策略（默认用户、最小来源、示例报告，可区分 dev/test）。
- 对齐模型约束与索引（尤其唯一索引、查询索引）。

**完成标准**  
- `alembic upgrade head` 后数据库可直接支撑 API 运行。
- 新环境可一键初始化并得到可用最小数据集。

**依赖**  
子任务 1。

---

### 子任务 3：统一 API 持久化层（去 mock）

**目标**  
把 P0 相关 API 从内存 mock 统一到 DB 持久化。

**范围**  
- `sources`：列表/详情/创建/更新/删除改为 DB 驱动。
- `articles`：查询与详情改为 DB 驱动，保留过滤能力。
- `tasks`：实现任务列表、触发、详情，写入 `collect_tasks`。
- `reports/monitors/users`：校验并修复与测试不一致的行为。

**完成标准**  
- API 在服务重启后数据不丢失。
- 现有合同测试与持久化测试通过，并补齐新增接口测试。

**依赖**  
子任务 2。

---

### 子任务 4：实现 P0 采集器能力（可运行最小集）

**目标**  
实现 P0 所需的最小可用采集能力，优先可稳定执行。

**范围**  
- `RSSCollector`（两段式采集）：
  - 第 1 段：读取 RSS/Atom，只取条目元数据（title/link/published）。
  - 第 2 段：逐条访问 RSS 返回的文章链接，提取正文全文并写入 `raw_content`（不能只保留 feed 摘要）。
  - 提供正文提取降级链：`readability/trafilatura -> selectolax -> bs4`（任一可用即返回）。
- `GitHubTrendingCollector`（Daily Top10 + Repo 增强）：
  - 从 `https://github.com/trending?since=daily` 抓取当日 Top10 仓库（repo、stars today、language、description）。
  - 对每个 repo 做增强采集：
    - `GET /repos/{owner}/{repo}`（基础仓库元信息）
    - `GET /repos/{owner}/{repo}/readme`（简报输入）
    - `GET /repos/{owner}/{repo}/contents` 或 `git trees`（代码结构索引，深度分析输入）
  - 预留 MCP 通道：当 REST 信息不足时可补充 repo 语义上下文。
- `HuggingFaceCollector`（先聚焦 Daily Papers）：
  - 主入口：`GET /api/daily_papers`（支持 `p/limit/date/week/month/submitter/sort`）。
  - 增强入口：`GET /api/papers/{paperId}` 与 `GET /api/arxiv/{paperId}/repos`。
  - 回退入口：`GET /api/papers/search?q=&limit=`.
- `BlogScraperCollector`（无 RSS 站点）：
  - 使用浏览器 Agent 对目标站点做 DOM 模式挖掘（列表页模式 + 详情页模式）。
  - 每个站点维护 `site_profile`（列表选择器、详情选择器、正文清洗规则、发布时间规则）。
  - 站点间允许不同实现，不强行统一单规则。
- 模式沉淀为 Skill（P0 范围内先落最小版本）：
  - 将“站点模式挖掘流程”固化为可复用 skill（模板 + 检查清单 + 产物格式）。
  - 首批覆盖至少 2 个无 RSS blog，验证可复用性。

**完成标准**  
- RSS 来源入库时 `raw_content` 为详情页全文，不是 feed 摘要。
- GitHub Trending 能稳定产出当日 Top10，并附带 README 与代码结构索引。
- Hugging Face Daily Papers 可拉取成功，且至少打通 1 条增强链路（paper 详情或 repos 关联）。
- 至少 2 个无 RSS blog 完成 `site_profile` 与全文抓取。
- 单次采集具备超时、重试、错误记录与可观测日志。

**依赖**  
子任务 3。

---

### 子任务 5：实现 P0 加工流水线（筛选/摘要/关键词/去重/打分）

**目标**  
将原始条目加工为可用于日报展示的结构化信息。

**范围**  
- 实现 `filter/summarizer/keyword_extractor/dedup/scorer` 的最小生产版本。
- `ProcessingPipeline` 中串联 Step1 + Step2 并行加工 + Step3 合并结果。
- 支持无 LLM 降级策略（规则/模板），保证链路可用性。
- 明确 Brief/Deep 输入差异：
  - Brief：优先使用文章摘要或 GitHub README。
  - Deep：优先使用文章全文、仓库代码结构与关键文件内容。

**完成标准**  
- 输入原始文章后可产出 `processed` 状态条目并写回数据库。
- 具备去重窗口与评分阈值策略（可配置）。

**依赖**  
子任务 4。

---

### 子任务 6：打通编排与触发（manual + daily）

**目标**  
把“任务触发 -> 采集 -> 加工 -> 产出报告”连成后台可调度流水线。

**范围**  
- 实现 `Orchestrator.run_daily_pipeline`。
- 完成 `tasks/monitors run` 的真实任务状态流转（pending/running/success/failed）。
- `lifespan` 中接入 scheduler 初始化与优雅关闭。

**完成标准**  
- 手动触发可创建任务并看到状态推进。
- 每日定时任务可执行最小流程并产出报告草稿。

**依赖**  
子任务 5。

---

### 子任务 7：实现输出与落盘（P0 路径优先）

**目标**  
将加工结果稳定转换为可消费报告，并完成至少 1 条落盘通路。

**范围**  
- `L2 Daily` 与 `L1 Brief` 渲染器落地（P0 默认先 Daily+Brief）。
- `database sink` 完成 reports 入库；`notion/obsidian` 至少打通一条真实落盘。
- `published_to` 记录落盘结果与失败原因。

**完成标准**  
- 每日流程可生成报告并至少成功落盘 1 个目标。
- 前端可查询到报告内容和元数据。

**依赖**  
子任务 6。

---

### 子任务 8：前端去 mock 并接入真实 API

**目标**  
Dashboard 页面从展示假数据切换为真实后端数据。

**范围**  
- `Discover/Library/Sources/Monitors` 全部改为 API 驱动。
- 完成创建监控任务、手动触发、查看历史报告、查看来源状态。
- 增加 loading/error/empty 状态，避免“静态页伪完成”。

**完成标准**  
- 页面刷新后数据一致、可追溯。
- P0 核心操作可在 UI 完整走通。

**依赖**  
子任务 7。

---

### 子任务 9：验收与交付（E2E + 文档）

**目标**  
形成可复用的交付工件，确保团队可持续迭代。

**范围**  
- 补齐关键 E2E 验收脚本（至少 1 条从采集到报告查询的链路）。
- 更新 `README` / `docs` 的运行步骤、配置说明、已支持能力边界。
- 明确 P1/P2 预留点与当前不支持清单。
- 增补“站点模式挖掘 skill”使用文档与新增站点接入指南。

**完成标准**  
- 新成员可按文档在本地跑起并复现 P0 链路。
- 验收清单逐项可勾选。

**依赖**  
子任务 8。

---

## 4) 推荐执行顺序（里程碑）

- **M1 工程稳定**：子任务 1-3
- **M2 核心流水线可跑**：子任务 4-6
- **M3 产品可用交付**：子任务 7-9

---

## 5) 风险与控制

- **风险：外部信息源不稳定（反爬/限流）**  
  控制：采集器必须具备超时、重试、降级和错误落库。

- **风险：LLM 调用不稳定或成本失控**  
  控制：提供 rule-based fallback + 批处理 + 限流。

- **风险：前后端契约漂移**  
  控制：接口合同测试与前端 API 类型定义同步更新。

- **风险：本地环境与 CI 行为不一致**  
  控制：统一测试入口与最小依赖启动脚本。

---

## 6) 本任务输出物

- 主任务拆解文档：`/.spec/TASK-P0-MVP-E2E.md`
- 子任务 4 issue 模板：`/.spec/TASK-4-COLLECTORS-ISSUES.md`
- 预制来源目录：`/.spec/BLOG-SOURCE-PRESET-CATALOG.md`
- 机器可读来源清单：`/backend/app/collectors/source_presets.yaml`
- RSS 验证报告：`/.spec/RSS-VERIFICATION-2026-03-01.md`
