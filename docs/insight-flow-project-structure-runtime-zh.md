# Insight Flow 项目结构与运行逻辑（中文详版）

> 面向对象：内部研发、测试、运维同学
> 
> 目标：建立对 Insight Flow 从“启动”到“单次 monitor 任务完成”的可执行心智模型，便于开发、联调与排障。

## 1) 项目概览与技术栈

Insight Flow 是一个“持续采集 + 结构化处理 + 报告生成 + 多渠道发布”的信息监控平台。核心运行场景是：

1. 持续采集多个信息源（RSS、站点、GitHub Trending、Hugging Face 等）。
2. 对原始内容做窗口过滤、关键词/摘要处理与事件聚合。
3. 生成日报/周报/研究报告并发布到目标 sink（database/notion/obsidian/rss）。
4. 在前端查看 monitor、run、事件日志与报告归档。

当前代码中的主要技术栈：

- 后端：Python 3.12+、FastAPI、SQLAlchemy Async、Alembic、APScheduler、Structlog
- 数据层：PostgreSQL 16、Redis 7（基础设施）
- 前端：Next.js 16 + React 19 + TypeScript + ESLint + Vitest
- 调用路径：前端统一通过 `frontend/src/lib/api.ts` 调后端 `/api/v1/*`
- 本地编排：Makefile + `scripts/bootstrap.sh` / `scripts/dev-local.sh` / `docker-compose.yml`

说明：品牌名为 **Insight Flow**；代码内仍有少量历史标识（如数据库名 `lexdeepresearch`、部分默认文案）属于当前实现现状。

## 2) 仓库目录结构（backend/frontend/agents/docs/scripts）与职责

### 2.1 根目录关键模块

```text
backend/   后端服务与调度主链路
frontend/  管理界面（监控、报告、配置）
agents/    浏览器 Agent 相关目录（当前 deepbrowse 仍是占位）
docs/      文档站内容与设计/计划文档
scripts/   启动、诊断、自检脚本
output/    运行日志与调试产物（task events + run artifacts）
```

### 2.2 backend/（核心运行目录）

`backend/app/` 下的职责分层：

- `main.py`：FastAPI 入口，挂载 lifespan、CORS、API router、健康检查
- `api/`：HTTP 接口，`api/router.py` 统一注册 `/api/v1` 路由
- `scheduler/`：调度与执行主链路
  - `scheduler.py`：APScheduler 定时触发入口
  - `monitor_runner.py`：monitor run 准备与执行封装
  - `orchestrator.py`：采集/处理/持久化/报告/发布编排核心
  - `task_events.py`：事件写库 + 文件日志落盘
- `collectors/`：采集器实现与预置 source 同步依赖
- `processors/`：过滤、关键词、全局摘要、报告阶段能力
- `renderers/`：日报/报告渲染
- `sinks/`：发布目标（database/notion/obsidian/rss）
- `models/`：ORM 模型（`collect_tasks`、`task_events`、`reports` 等）

### 2.3 frontend/

- `src/lib/api.ts` 是前端 API 封装入口：
  - `runMonitor`、`getMonitorRuns`、`getMonitorRunEvents`、`cancelMonitorRun`
  - `getReports`、`getReportById`
  - `getDestinations`、`updateDestination`
- API 基址：`const API_BASE = process.env.NEXT_PUBLIC_API_URL || ""`
  - 本地浏览器默认同源
  - docker-compose 下由环境变量指向 `http://backend:8000`

### 2.4 agents/

- 当前 `agents/deepbrowse/README.md` 明确该目录为占位目录，实际代码待集成。
- 可视为浏览器采集能力的扩展位（当前仓库内主运行链路不依赖此目录直接执行）。

### 2.5 docs/

- 文档站与补充文档目录。
- `docs/zh` 为中文主文档结构；`docs/en` 为镜像结构。

### 2.6 scripts/

- `bootstrap.sh`：首次依赖安装与环境修复
- `dev-local.sh`：本地一键启动（infra + migrate + backend + frontend）
- `doctor.sh`：环境诊断（命令、端口、venv、docker 等）

## 3) 启动链路（bootstrap / dev-local / docker-compose）

### 3.1 首次初始化：`make bootstrap`

实际执行 `scripts/bootstrap.sh`，关键步骤：

1. 校验命令：`python3`、`npm`、`docker`
2. 如无 `.env` 则由 `.env.example` 复制
3. 创建/修复 `.venv`
4. `pip install -U pip setuptools wheel`（带索引 fallback）
5. 安装后端依赖：`pip install -e ".[dev]"`
6. 安装前端依赖：优先 `npm ci`，失败时回退 `npm install`

### 3.2 日常本地开发：`make dev-local`

实际执行 `scripts/dev-local.sh`，链路如下：

1. 读取 `.env` 并导出 `DB_PASSWORD`、`DATABASE_URL`
2. `docker compose up -d postgres redis`
3. 循环探活 Postgres（最多 60 秒）
4. 运行 Alembic 迁移（失败重试；若 `InvalidPasswordError`，脚本会自动 `docker compose down -v` 后重建）
5. 启动后端：`uvicorn app.main:app --reload --port 8000`
6. 启动前端：`npm run dev`（3000）

### 3.3 全 Docker 开发：`make dev-docker`

执行 `docker compose up --build`，服务关系：

- `backend`：端口 `8000:8000`，依赖 `postgres`、`redis`
- `frontend`：端口 `3000:3000`，依赖 `backend`
- `postgres`：`postgres:16-alpine`，DB `lexdeepresearch`
- `redis`：`redis:7-alpine`

## 4) 后端运行逻辑（FastAPI lifespan、路由注册、scheduler、monitor API）

### 4.1 FastAPI 生命周期（`backend/app/main.py`）

应用启动时（非 pytest 环境）：

1. `bootstrap_runtime_data()`：初始化默认用户与预置 source/订阅
2. `init_scheduler()`：注册并启动 APScheduler

应用关闭时（非 pytest 环境）：

- `shutdown_scheduler()` 优雅关闭调度器

额外行为：

- CORS 放行本地 3000/3001
- API 主前缀：`app.include_router(api_router, prefix="/api")`
- 健康检查：`GET /health` 返回 `{status: "ok", service: "Insight Flow"}`

### 4.2 路由注册（`backend/app/api/router.py`）

`/api/v1` 下挂载：

- sources、monitors、articles、reports、users、tasks、destinations、providers、feed

重点监控接口在 `backend/app/api/v1/monitors.py`。

### 4.3 scheduler（`backend/app/scheduler/scheduler.py`）

- `init_scheduler()` 读取 `settings.daily_collect_time`，注册 `daily_collect` cron 任务。
- `daily_collect_and_report()` 会拉取 `enabled=true` 的 monitor，逐个 `run_monitor_once(..., trigger_type="scheduled")`。
- `weekly_report()` 当前是 `TODO: P1 实现`，尚未落地。

### 4.4 monitor API（`backend/app/api/v1/monitors.py`）

关键接口与用途：

- `POST /api/v1/monitors/{monitor_id}/run`：手动触发 run（后台执行）
- `GET /api/v1/monitors/{monitor_id}/runs`：run 摘要（source_total/source_done/source_failed）
- `POST /api/v1/monitors/{monitor_id}/runs/{run_id}/cancel`：请求取消
- `GET /api/v1/monitors/{monitor_id}/runs/{run_id}/events`：按时间升序返回事件流

代码中标注为 “P1 预留” 但接口已可用：

- `GET /api/v1/monitors/{id}/logs`
- `PATCH /api/v1/monitors/{id}`
- `DELETE /api/v1/monitors/{id}`

## 5) 任务执行主链路（run monitor -> prepare task -> execute orchestrator -> collect/process/persist/report/publish）

下面是一次手动运行的主路径（函数级别）：

1. `POST /api/v1/monitors/{id}/run`
2. `prepare_monitor_run(...)`（`monitor_runner.py`）
3. `BackgroundTasks` 调用 `_background_execute_monitor(...)`
4. `execute_monitor_pipeline(...)`（`monitor_runner.py`）
5. `Orchestrator.run_daily_pipeline(...)` -> `_run_daily_pipeline(...)`

### 5.1 prepare 阶段（monitor_runner）

- 清理过期事件：`cleanup_expired_task_events(retention_days=7)`
- 更新 monitor 的 `last_run/updated_at`
- 创建 monitor 级 `collect_tasks` 记录（`source_id=None`，`status=running`）
- 写入 `task_events`：`run_started`

### 5.2 orchestrator 执行阶段（_run_daily_pipeline）

1. 计算窗口：`window_start/window_end/window_hours`
2. 加载 source：`_load_subscribed_sources`
   - 优先 monitor 指定 source
   - 无订阅时 fallback 到最近更新的 enabled source（最多 10）
3. 为每个 source 创建 task 行（初始 `pending`）
4. 并发采集：`collect_source`（支持 `fallback_chain`）
5. 窗口过滤：`_filter_raw_articles_by_window`
6. 处理流水线：`_process_source_articles`
   - filter -> candidate_cluster -> keywords
7. 持久化文章：`_persist_processed_articles`（按 `source_id + external_id` upsert）
8. 报告与发布：`_render_and_persist_reports` -> `_publish_report_rows`

### 5.3 取消与失败策略

- run 取消：主 task 状态进入 `cancelling`，orchestrator 轮询 `_is_monitor_run_cancelling`
- 取消时会调用 `_finalize_cancelled_run` 或 `_mark_source_cancelled`
- source 失败时会 `_cancel_unfinished_sources_after_failure`
- monitor 级 task 最终状态：`success / partial_success / failed / cancelled`

## 6) 报告生成与发布逻辑（daily/research paths, sinks）

### 6.1 报告分支

在 `_render_and_persist_reports(...)` 中按 `report_type` 分流：

- `daily`、`weekly`：
  - 统一走事件聚合 + `run_global_summary_stage` + `render_daily_report`
  - 再进入 report provider（`_run_report_with_retry`）生成最终正文
- `research`：
  - 走 `_build_research_reports`
  - 选择研究目标事件 `_select_research_target_event`
  - 构造 `ResearchJob` 后调用 `get_agent(...).run(job)`

说明：周报定时任务本身仍是 P1/TODO，但 `report_type="weekly"` 在当前报告渲染路径内可被处理。

### 6.2 发布分支（sinks）

`_publish_report_rows(...)` 逻辑：

1. 解析发布目标：`_resolve_publish_targets(...)`
   - 始终确保 `database` 在目标列表中
2. 对每个 target 取 sink：`get_sink(target)`
3. 构建 sink 配置：`_build_sink_config(...)`
   - database：`report_id`
   - notion：database/page/api key（支持用户覆盖）
   - obsidian：vault_path
   - rss：feed_url/site_url/feed_title/max_items
4. 调用 `sink.publish(rendered, config)`
5. 落库 `published_to` + `publish_trace`

失败处理：

- `database` 默认失败策略为 `abort`
- 其他 sink 默认 `continue`
- 整体状态可能变为 `partial_success`

RSS 对外接口：`GET /api/v1/feed.xml`（`backend/app/api/v1/feed.py`）。

## 7) 事件日志与排障（task_events, output/logs）

### 7.1 task_events 表

模型：`backend/app/models/task_event.py`（表名 `task_events`）

核心字段：

- `run_id`：同一次 run 的聚合标识
- `monitor_id` / `task_id` / `source_id`
- `stage`：collect/process/persist/report/publish/monitor_run 等
- `level`：info/warning/error
- `event_type`：阶段内事件名（如 `run_started`、`publish_failed`）
- `payload`：结构化上下文
- `created_at`

### 7.2 文件日志落盘

`append_task_event(...)` 除了写数据库，还会写文件到：

- `output/logs/run_*.jsonl`（机器可读）
- `output/logs/run_*.log`（人类可读）

命名由北京时间时间戳生成（`Asia/Shanghai`）。

### 7.3 透明调试产物（run_artifacts）

orchestrator 会把关键阶段内容落到：

- `output/run_artifacts/{run_id}/source_{source_id}/01_collect_raw_items.json`
- `.../02_window_kept.json`
- `.../02_window_dropped.json`
- `.../03_pipeline_filter_kept.json`
- `.../03_pipeline_filter_dropped.json`
- `.../04_candidate_clusters.json`
- `.../05_keywords_output.json`

这些文件用于复盘“为什么某条内容被过滤/保留”。

### 7.4 排障入口建议

优先排障顺序：

1. `GET /api/v1/monitors/{id}/runs` 看 run 总体状态
2. `GET /api/v1/monitors/{id}/runs/{run_id}/events` 看阶段事件
3. 查看 `output/logs/run_*.log` 定位失败阶段
4. 查看 `output/run_artifacts/{run_id}/...` 核对输入输出

## 8) 常用命令与排障建议

### 8.1 常用命令（Makefile）

```bash
make bootstrap        # 初始化/修复依赖
make doctor           # 环境诊断
make infra-up         # 仅启动 postgres + redis
make migrate          # 执行 Alembic 迁移
make dev-local        # 本地一键启动
make dev-docker       # Docker 一键启动
make backend          # 仅启动后端
make frontend         # 仅启动前端
make sync-sources     # 同步预置信息源
make test-backend     # 后端测试
make lint-frontend    # 前端 lint
make build-frontend   # 前端 build
make test-all         # 后端测试 + 前端 lint/build
```

### 8.2 高频问题与建议

1. **run 一直没有产出**
   - 先看 `runs` 摘要是否停在 `running/cancelling`
   - 再看 `events` 是否卡在 collect 或 process

2. **显示 No subscribed sources**
   - 说明当前 run 可用 source 为空；检查 monitor 的 `source_ids` 与 source `enabled`

3. **发布失败（publish_failed）**
   - 检查目标 sink 是否存在、是否启用、配置是否完整（Notion/Obsidian/RSS）

4. **本地迁移失败 + 密码不一致**
   - `dev-local.sh` 已内置自动重建流程；仍失败时手动执行：
     - `docker compose down -v`
     - `make infra-up && make migrate`

5. **前端请求异常**
   - 检查 `NEXT_PUBLIC_API_URL`
   - 本地浏览器直连建议保持同源或明确指向后端地址

---

如果要新增运行阶段或 sink，建议优先对齐三个位置：

1. `orchestrator.py` 阶段事件（便于观测）
2. `task_events.py` 日志格式（便于排障）
3. `frontend/src/lib/api.ts` 类型与接口（便于前端消费）
