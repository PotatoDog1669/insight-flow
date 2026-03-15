# Insight Flow

Insight Flow 是一个面向研究与信息监控场景的工作台，用来持续采集信息源、生成日报/周报/研究报告，并把结果同步到你配置的输出渠道。

当前仓库包含：

- `backend/`：FastAPI API、调度器、采集器、报告生成与落盘逻辑
- `frontend/`：Next.js 管理界面，覆盖报告、任务、信息源、模型配置和输出配置
- `agents/`：浏览器采集相关能力
- `docs/`：补充文档与设计记录

## 主要能力

- 统一管理信息源，支持 RSS、站点抓取、GitHub Trending、Hugging Face 等采集方式
- 创建监控任务，按 `daily`、`weekly`、`research` 生成报告
- 为 `filter`、`keywords`、`global_summary`、`report` 阶段配置 AI 路由
- 配置 `llm_openai` / `llm_codex` 模型连接参数并在线测试
- 将生成结果输出到 Notion、Obsidian 或 RSS
- 查看任务运行历史、事件日志和报告归档

## 环境要求

- Python 3.12+
- Node.js 18+
- Docker / Docker Compose

## 快速开始

首次初始化：

```bash
cp .env.example .env
make bootstrap
make doctor
```

日常启动开发环境：

```bash
make dev-local
```

说明：

- `make bootstrap`：首次执行，或依赖/虚拟环境损坏时再执行
- `make doctor`：环境自检，首次推荐执行，之后在怀疑本地环境有问题时再执行
- `make dev-local`：日常开发启动命令，每次本地跑项目时执行

启动后访问：

- 前端：`http://localhost:3000`
- 后端 API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

如果你会用到浏览器采集能力，再额外执行：

```bash
make backend-browser-deps
```

首次启动后端时，系统会自动初始化默认用户，并把 `backend/app/collectors/source_presets.yaml` 中的预置信息源同步到数据库。

## 使用方式

1. 在“模型配置”页面填写 `llm_openai` 或 `llm_codex` 的连接信息。
2. 在“输出配置”页面启用 Notion、Obsidian 或 RSS。
3. 在“信息源”页面检查预置源，或添加你自己的源。
4. 在“任务”页面创建 monitor，选择信息源、报告类型、输出渠道和 AI 路由。
5. 手动运行任务后，在“报告”与“归档”页面查看生成结果。

## 常用命令

```bash
make infra-up        # 启动 postgres + redis
make migrate         # 执行数据库迁移
make backend         # 启动后端开发服务
make frontend        # 启动前端开发服务
make sync-sources    # 同步预置信息源到数据库
make test-all        # 运行后端测试 + 前端 lint/build
make infra-down      # 停止本地基础服务
```
