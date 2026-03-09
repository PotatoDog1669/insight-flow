# 🔍 LexDeepResearch

**自动化信息获取与深度研究平台** — 让你把注意力放在创造，而非信息获取。

LexDeepResearch 面向 AI 从业者和研究人员，自动采集全球 AI 前沿资讯，智能筛选、结构化加工，并落盘至你偏好的知识管理工具中。

## ✨ 核心特性

- **深度浏览能力**：基于自研 deepbrowse 浏览器 Agent，突破纯 RSS/API 方案的信息覆盖限制
- **多源采集**：GitHub Trending、Hugging Face、30+ 技术博客、arXiv、X、Reddit 等
- **智能加工**：AI 初筛 → 摘要生成 → 关键词提取 → 去重 → 智能打分
- **分层输出**：L1 速览 / L2 日报 / L3 周报 / L4 深度报告
- **多端落盘**：Notion、Obsidian、飞书、本地 Markdown

## 🛠 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12+ · FastAPI · SQLAlchemy |
| 前端 | Next.js 14 · React 18 · TailwindCSS |
| 数据库 | PostgreSQL 16 · Redis 7 |
| 浏览器引擎 | deepbrowse (自研) + Playwright |
| LLM | litellm (多模型适配) |
| 部署 | Docker Compose |

## 🚀 快速开始

### 前置条件

- Python 3.12+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL 16 & Redis 7（或使用 Docker Compose 启动）

### 本地开发

```bash
# 1. 克隆仓库
git clone <repo-url> && cd LexDeepResearch

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key 等配置
# 若需要 Notion 落盘，请至少配置:
# NOTION_API_KEY=secret_xxx
# 若需要 Codex Agent 加工，可配置:
# CODEX_AUTH_MODE=api_key
# CODEX_API_KEY=sk_xxx
# 或
# CODEX_AUTH_MODE=oauth
# CODEX_OAUTH_TOKEN=<oauth access token>

# 3. 使用 Docker Compose 启动基础服务
docker compose up -d postgres redis

# 4. 启动后端
cd backend
pip install -e ".[dev]"
PYTHONPATH=. alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 5. 启动前端
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000 查看前端，http://localhost:8000/docs 查看 API 文档。

> 首次启动后端时，系统会自动同步 `source_presets.yaml` 的全部预设源（upsert）、创建默认用户，并补齐默认订阅关系（含系统源 GitHub Trending / Hugging Face Daily Papers）。

### 一键本地开发（推荐）

```bash
# 仅首次
make backend-deps
make backend-browser-deps   # 可选：安装 Playwright Chromium（用于无 RSS 博客浏览器采集，如 Anthropic）
make frontend-deps

# 每次开发
make dev-local
```

#### 正常启停（保留数据库数据）

```bash
# 启动（推荐日常使用）
make dev-local

# 停止（在 dev-local 终端 Ctrl+C 后执行）
docker compose down   # 不带 -v，保留 pgdata
```

> 不要在日常重启时使用 `docker compose down -v`，它会删除数据库 volume（`pgdata`），导致已创建的 monitor、provider 配置等数据丢失。

> `scripts/dev-local.sh` 在检测到数据库密码不匹配（`InvalidPasswordError`）时，也会自动执行一次 `docker compose down -v` 重建本地库。请保持 `.env` 中 `DB_PASSWORD` 稳定，避免意外清库。

常用快捷命令：

```bash
make infra-up        # 启动 postgres + redis
make migrate         # 运行数据库迁移
make sync-sources    # 将 source_presets.yaml 全量同步到数据库（upsert）
make test-all        # 后端测试 + 前端 lint/build
make profile-gen     # 从 presets 生成缺失的 P0 site profile
make profile-check   # 校验全部 profile + P0 覆盖
make smoke-e2e       # 本地确定性 E2E 冒烟（不依赖外网）
make run-mvp-codex-notion # 4 源最小链路(OpenAI/Anthropic/GitHub/HF) -> Notion
make infra-down      # 停止 docker 服务
```

### 运行日志落盘（用于排障）

- 每次 monitor run 的阶段事件会落盘到 `output/logs/`。
- 文件命名：
  - `run_<timestamp>.jsonl`：机器可读（结构化 JSON 行）
  - `run_<timestamp>.log`：人类可读（可直接 `tail -f` 排障）
- `jsonl` 每行一条结构化事件（JSON），包含：
  - `created_at`, `run_id`, `monitor_id`, `task_id`, `source_id`
  - `stage`, `event_type`, `level`, `message`, `payload`
- `log` 行格式示例：
  - `context run=<run_id> monitor=- task=<task_id> source=<source_id>`
  - `2026-03-05T00:55:12.808568+08:00 INFO  stage=collect event=source_started message="[Seed Source] collect started" payload={"provider":"huggingface","source_name":"Seed Source"}`
- `report` 阶段会额外记录：
  - `input_content_chars`, `prompt_content_chars`, `output_content_chars`
  - `input_events`, `output_heading3_count`, `provider`

可结合 `/api/v1/monitors/{monitor_id}/runs` 返回的 `run_id` 直接定位对应日志文件。

Notion 落盘需在 `.env` 中配置 `NOTION_API_KEY`，并在 `NOTION_DATABASE_ID` 或 `NOTION_PARENT_PAGE_ID` 二选一。
Codex Agent 支持两种认证：
- `CODEX_AUTH_MODE=api_key` + `CODEX_API_KEY`
- `CODEX_AUTH_MODE=oauth` + `CODEX_OAUTH_TOKEN`

## 📁 项目结构

```
LexDeepResearch/
├── .spec/              # 产品与技术文档 (.spec/spec-index.md / core/product-requirements-spec.md / core/technical-architecture-spec.md)
├── backend/            # 后端服务 (Python/FastAPI)
├── frontend/           # 前端 (Next.js)
├── agents/             # 浏览器 Agent 模块 (deepbrowse / browser-use / codex 等)
├── docs/               # Mintlify 文档站点
├── docker-compose.yml  # 本地开发编排
└── .github/workflows/  # CI/CD
```

## 📖 文档

详细技术文档请参阅 [`.spec/core/technical-architecture-spec.md`](./.spec/core/technical-architecture-spec.md)，产品需求请参阅 [`.spec/core/product-requirements-spec.md`](./.spec/core/product-requirements-spec.md)。文档索引见 [`.spec/spec-index.md`](./.spec/spec-index.md)。

## 📄 License

Private — All rights reserved.
