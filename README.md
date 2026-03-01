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

> 首次启动后端时，系统会自动执行最小种子初始化：创建默认用户、P0 预置信息源（含 GitHub Trending / Hugging Face Daily Papers）以及默认订阅关系。

## 📁 项目结构

```
LexDeepResearch/
├── .spec/              # 产品与技术文档 (PRD.md / TEC.md)
├── backend/            # 后端服务 (Python/FastAPI)
├── frontend/           # 前端 (Next.js)
├── deepbrowse/         # 自研浏览器 Agent (独立模块)
├── docs/               # Mintlify 文档站点
├── docker-compose.yml  # 本地开发编排
└── .github/workflows/  # CI/CD
```

## 📖 文档

详细技术文档请参阅 [`.spec/TEC.md`](./.spec/TEC.md)，产品需求请参阅 [`.spec/PRD.md`](./.spec/PRD.md)。

## 📄 License

Private — All rights reserved.
