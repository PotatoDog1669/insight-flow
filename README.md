<div align="center">
  <img src="docs/banner.svg" alt="Insight Flow banner" />
</div>

---

<div align="center">
  <p>
    <a href="https://insight-flow.potatodog.cc/zh/introduction">
      <img src="https://img.shields.io/badge/docs-home-0EA5E9?style=flat-square" alt="Documentation">
    </a>
    <a href="backend/">
      <img src="https://img.shields.io/badge/backend-FastAPI-009688?style=flat-square" alt="Backend: FastAPI">
    </a>
    <a href="frontend/">
      <img src="https://img.shields.io/badge/frontend-Next.js-111111?style=flat-square" alt="Frontend: Next.js">
    </a>
    <a href="https://insight-flow.potatodog.cc/zh/quickstart">
      <img src="https://img.shields.io/badge/python-3.12%2B-3776AB?style=flat-square" alt="Python 3.12+">
    </a>
    <a href="https://insight-flow.potatodog.cc/zh/introduction">
      <img src="https://img.shields.io/badge/status-active-65A30D?style=flat-square" alt="Status: active">
    </a>
  </p>
  <p>
    <a href="https://insight-flow.potatodog.cc/en/introduction">English</a>
    |
    <a href="https://insight-flow.potatodog.cc/zh/introduction">简体中文</a>
  </p>
</div>

Insight Flow 是一个面向研究监控、持续情报收集和内容沉淀的工作台。

Insight Flow 支持两种使用方式：你可以手动配置 monitor，也可以先告诉 Agent 想关注什么主题、对象或方向，由它帮你生成可编辑的 monitor 草案；随后系统会基于你配置的信息源、模型和输出目标，持续完成采集、筛选、总结、报告生成与同步发布。

当前项目已经覆盖一条完整链路：信息源侧支持 RSS、网站抓取、GitHub Trending、Hugging Face，以及面向学术和社区场景的 OpenAlex、PubMed、Europe PMC、Reddit、X 等来源；任务侧支持按计划运行 monitor，生成日报、周报、调研报告 和 论文推荐 等报告类型；模型侧可以配置 openai 接口的 LLM，也可以使用 codex，并为不同处理阶段设置 AI routing；输出侧可以将结果同步到 Notion、Obsidian 或 RSS，同时保留运行记录、报告归档和手动补发布能力。

## 演示

演示视频建议展示以下流程：

1. 使用 Agent 生成 monitor 草案，或手动创建一个 monitor。
2. 配置信息源、模型连接和 destination。
3. 手动运行任务，查看运行记录、报告详情与归档。
4. 将生成结果同步到 Notion、Obsidian 或 RSS。

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

- `make bootstrap`：首次执行，或依赖、虚拟环境损坏时再执行
- `make doctor`：环境自检，首次推荐执行，之后在怀疑本地环境有问题时再执行
- `make dev-local`：日常开发启动命令，每次本地跑项目时执行

启动后访问：

- 前端：`http://localhost:3018`
- 后端 API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

如果你会用到浏览器采集能力，再额外执行：

```bash
make backend-browser-deps
```

首次启动后端时，系统会自动初始化默认用户，并把 `backend/app/collectors/source_presets.yaml` 中的预置信息源同步到数据库。

## 本地文档预览

仓库内的 Mint 配置文件位于 `docs/docs.json`。

```bash
cd docs
npx mint dev
```

如果你需要查看完整的后端 OpenAPI 文档，请单独启动后端服务后访问 `http://localhost:8000/docs`。
