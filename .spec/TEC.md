| **文档版本** | v1.0 |
| --- | --- |
| **产品名称** | LexDeepResearch |
| **负责人** | @黎 耀聪 |
| **创建日期** | 2026年3月1日 |
| **关联文档** | [PRD.md](./PRD.md) |

---

## 1 技术架构总览

### 1.1 架构风格

采用 **单体后端 + 插件式模块** 架构，以 Python 为主语言，适配 MVP 阶段快速迭代需求。

**核心设计原则：采集与用户解耦**——信息源按全局频率统一采集并缓存到共享信息池，多用户订阅同一信息源时直接从缓存分发，个性化筛选/输出/落盘发生在用户层。

架构分为以下六层：

```
┌─────────────────────────────────────────────────────────┐
│                    Web Dashboard (前端)                    │
│              Next.js / React · TailwindCSS                │
├─────────────────────────────────────────────────────────┤
│                   API Gateway (BFF 层)                     │
│                  FastAPI · REST + WebSocket                │
├───────────┬─────────────┬──────────────┬────────────────┤
│ 信息获取层  │  筛选加工层    │   输出层      │  存储/落盘层    │
│ Collector  │  Processor   │  Renderer    │  Sink          │
├───────────┴─────────────┴──────────────┴────────────────┤
│          ⬇️ 共享信息池 (Shared Article Pool)              │
│  全局采集 → 缓存 → 多用户订阅分发（同源不重复采集）       │
├─────────────────────────────────────────────────────────┤
│               调度与编排层 (Scheduler / Orchestrator)        │
│            APScheduler · Celery (可选) · asyncio           │
├─────────────────────────────────────────────────────────┤
│                   数据持久层 (Storage)                      │
│          PostgreSQL · Redis · 本地文件系统                   │
└─────────────────────────────────────────────────────────┘
```

### 1.2 技术栈总览

| **层级** | **技术选型** | **选型理由** |
| --- | --- | --- |
| **语言** | Python 3.12+ | 生态丰富，AI/爬虫类库完善 |
| **后端框架** | FastAPI | 异步原生、自动 OpenAPI 文档、高性能 |
| **前端框架** | Next.js 14 (App Router) + React 18 | SSR/SSG 支持、组件生态丰富 |
| **数据库** | PostgreSQL 16 | 可靠的关系型存储，支持 JSONB 灵活字段 |
| **缓存/队列** | Redis 7 | 任务队列、去重缓存、信息池暂存 |
| **任务调度** | APScheduler / Celery + Redis Broker | 定时触发采集任务、异步任务执行 |
| **浏览器引擎** | deepbrowse (自研) + Browser Provider (本地 Playwright / 云浏览器 CDP) | 动态渲染抓取、登录态管理；支持本地和云端两种浏览器模式 |
| **LLM 调用** | OpenAI API / 兼容接口 (litellm) | 统一多模型调用，灵活切换 |
| **文档站点** | Mintlify | API 文档、用户指南、开发者文档的统一托管 |
| **容器化** | Docker + Docker Compose | 本地开发与部署一致性 |
| **CI/CD** | GitHub Actions | 自动化测试与部署 |

---

## 2 项目目录结构

```
LexDeepResearch/
├── .spec/                          # 产品与技术文档
│   ├── PRD.md
│   └── TEC.md
├── backend/                        # 后端服务（Python）
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── config.py               # 配置管理（环境变量 / YAML）
│   │   ├── models/                 # SQLAlchemy ORM 模型
│   │   │   ├── __init__.py
│   │   │   ├── source.py           # 信息源模型
│   │   │   ├── article.py          # 采集到的文章/信息条目
│   │   │   ├── report.py           # 生成的报告
│   │   │   └── task.py             # 采集任务记录
│   │   ├── schemas/                # Pydantic 请求/响应模型
│   │   │   ├── __init__.py
│   │   │   ├── source.py
│   │   │   ├── article.py
│   │   │   └── report.py
│   │   ├── api/                    # API 路由
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── sources.py      # 信息源 CRUD
│   │   │   │   ├── articles.py     # 文章查询
│   │   │   │   ├── reports.py      # 报告查询
│   │   │   │   └── tasks.py        # 采集任务管理
│   │   │   └── router.py
│   │   ├── collectors/             # 信息获取层 — 各信息源 Collector
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # BaseCollector 抽象基类
│   │   │   ├── github_trending.py  # GitHub Trending
│   │   │   ├── huggingface.py      # Hugging Face
│   │   │   ├── rss.py              # 通用 RSS 采集器
│   │   │   ├── blog_scraper.py     # 自建爬虫脚本（技术博客）
│   │   │   ├── deepbrowse.py       # deepbrowse 兜底采集器
│   │   │   └── registry.py         # Collector 注册表（插件化管理）
│   │   ├── processors/             # 筛选加工层
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py         # 加工流水线编排
│   │   │   ├── filter.py           # AI 初筛
│   │   │   ├── summarizer.py       # 摘要生成
│   │   │   ├── keyword_extractor.py# 关键词提取
│   │   │   ├── dedup.py            # 旧闻排除 / 去重
│   │   │   └── scorer.py           # 智能打分
│   │   ├── renderers/              # 输出层 — 模板渲染
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # BaseRenderer 抽象基类
│   │   │   ├── l1_brief.py         # L1 速览
│   │   │   ├── l2_daily.py         # L2 日报（默认）
│   │   │   ├── l3_weekly.py        # L3 周报
│   │   │   └── l4_deep_report.py   # L4 深度报告
│   │   ├── sinks/                  # 知识存储/落盘层
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # BaseSink 抽象基类
│   │   │   ├── notion.py           # Notion 落盘
│   │   │   ├── obsidian.py         # Obsidian / 本地 Markdown
│   │   │   ├── feishu.py           # 飞书文档
│   │   │   └── database.py         # 数据库结构化存储
│   │   ├── scheduler/              # 调度与编排
│   │   │   ├── __init__.py
│   │   │   ├── scheduler.py        # 定时任务调度器
│   │   │   └── orchestrator.py     # 采集流水线编排
│   │   ├── llm/                    # LLM 调用封装
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # 统一 LLM Client（litellm）
│   │   │   └── prompts.py          # Prompt 模板管理
│   │   └── utils/                  # 通用工具
│   │       ├── __init__.py
│   │       ├── logger.py
│   │       └── retry.py            # 重试与降级
│   ├── alembic/                    # 数据库迁移
│   │   └── versions/
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                       # 前端（Next.js）
│   ├── src/
│   │   ├── app/                    # App Router 页面
│   │   │   ├── page.tsx            # 首页 — 采集结果列表
│   │   │   ├── sources/
│   │   │   │   └── page.tsx        # 信息源状态面板
│   │   │   └── layout.tsx
│   │   ├── components/             # UI 组件
│   │   │   ├── ArticleList.tsx
│   │   │   ├── SourceStatusPanel.tsx
│   │   │   └── TriggerButton.tsx
│   │   └── lib/                    # API 调用封装
│   │       └── api.ts
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── Dockerfile
├── agents/                         # 浏览器 Agent 模块（支持多种 Agent）
│   ├── deepbrowse/                 # 自研 deepbrowse（默认）
│   └── ...                         # browser-use / codex 等（按需添加）
├── docs/                           # Mintlify 文档站点
│   ├── mint.json                   # Mintlify 配置
│   ├── introduction.mdx            # 产品介绍
│   ├── quickstart.mdx              # 快速开始
│   ├── api-reference/              # API 参考文档（自动从 OpenAPI 生成）
│   │   ├── sources.mdx
│   │   ├── articles.mdx
│   │   ├── tasks.mdx
│   │   └── reports.mdx
│   ├── guides/                     # 用户指南
│   │   ├── add-source.mdx          # 如何添加信息源
│   │   ├── configure-sink.mdx      # 如何配置落盘目标
│   │   └── custom-template.mdx     # 如何自定义输出模板
│   └── development/                # 开发者文档
│       ├── architecture.mdx        # 架构说明
│       ├── collector-plugin.mdx    # 如何编写 Collector 插件
│       └── deployment.mdx          # 部署指南
├── docker-compose.yml              # 本地开发编排
├── .env.example                    # 环境变量模板
├── .github/
│   └── workflows/
│       ├── ci.yml                  # CI 流水线
│       └── deploy.yml              # CD 流水线
└── README.md
```

---

## 3 数据库设计

### 3.1 核心表结构

使用 PostgreSQL，以下为 MVP 阶段的核心数据表：

```sql
-- ========================================
-- 信息源表
-- ========================================
CREATE TABLE sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(128) NOT NULL,          -- 信息源名称，如 "OpenAI Blog"
    category        VARCHAR(32)  NOT NULL,           -- 类别: open_source / blog / academic / social
    collect_method  VARCHAR(32)  NOT NULL,           -- 获取方式: api / rss / scraper / deepbrowse
    config          JSONB        NOT NULL DEFAULT '{}', -- 采集配置（URL、API Key、RSS 地址等）
    enabled         BOOLEAN      NOT NULL DEFAULT TRUE,
    last_collected  TIMESTAMPTZ,                     -- 最近一次采集时间
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ========================================
-- 用户表
-- ========================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(256) UNIQUE NOT NULL,
    name            VARCHAR(128),
    settings        JSONB        DEFAULT '{}',       -- 用户偏好设置（输出格式、落盘配置等）
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ========================================
-- 用户订阅关系（用户 ↔ 信息源）
-- ========================================
CREATE TABLE user_subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID         NOT NULL REFERENCES users(id),
    source_id       UUID         NOT NULL REFERENCES sources(id),
    enabled         BOOLEAN      NOT NULL DEFAULT TRUE,
    custom_config   JSONB        DEFAULT '{}',       -- 用户级别的个性化配置（关注关键词、评分阈值等）
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_user_sub_unique ON user_subscriptions(user_id, source_id);
-- 查询某信息源被哪些用户订阅（用于判断是否需要采集）
CREATE INDEX idx_user_sub_source ON user_subscriptions(source_id) WHERE enabled = TRUE;

-- ========================================
-- 采集到的原始文章/信息条目（全局共享，与用户无关）
-- ========================================
CREATE TABLE articles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       UUID         NOT NULL REFERENCES sources(id),
    external_id     VARCHAR(512),                    -- 外部唯一标识（URL / commit hash 等）
    title           VARCHAR(512) NOT NULL,
    url             TEXT,                             -- 原文链接
    raw_content     TEXT,                             -- 原始内容
    summary         VARCHAR(256),                    -- AI 生成摘要（≤50 字目标）
    keywords        JSONB        DEFAULT '[]',       -- 关键词数组
    ai_score        REAL,                            -- AI 打分（0.0~1.0）
    status          VARCHAR(16)  NOT NULL DEFAULT 'raw',
        -- raw: 刚采集 | filtered: 已过滤 | processed: 已加工 | published: 已落盘
    source_type     VARCHAR(16)  DEFAULT 'unknown',  -- P1 预留：primary / secondary / unknown
    metadata        JSONB        DEFAULT '{}',       -- 扩展字段（star 数、作者等）
    published_at    TIMESTAMPTZ,                     -- 原文发布时间
    collected_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 防止重复采集
CREATE UNIQUE INDEX idx_articles_external_id ON articles(source_id, external_id);
-- 加速按时间和状态查询
CREATE INDEX idx_articles_status_time ON articles(status, collected_at DESC);

-- ========================================
-- 生成的报告（用户级别，每个用户有自己的报告）
-- ========================================
CREATE TABLE reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID         REFERENCES users(id), -- 归属用户（NULL 表示系统全局报告）
    time_period     VARCHAR(16)  NOT NULL,           -- daily / weekly / custom
    depth           VARCHAR(16)  NOT NULL,           -- brief / deep
    title           VARCHAR(256) NOT NULL,
    content         TEXT         NOT NULL,            -- 渲染后的 Markdown / HTML
    article_ids     UUID[]       DEFAULT '{}',       -- 关联的文章 ID 列表
    metadata        JSONB        DEFAULT '{}',       -- 扩展字段
    published_to    JSONB        DEFAULT '[]',       -- 已落盘到哪些目标
    report_date     DATE         NOT NULL,            -- 报告日期
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reports_user_date ON reports(user_id, report_date DESC);
CREATE INDEX idx_reports_dimensions ON reports(time_period, depth);

-- ========================================
-- 采集任务记录（全局级别）
-- ========================================
CREATE TABLE collect_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       UUID         REFERENCES sources(id),
    trigger_type    VARCHAR(16)  NOT NULL,           -- scheduled / manual
    status          VARCHAR(16)  NOT NULL DEFAULT 'pending',
        -- pending | running | success | failed
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    articles_count  INTEGER      DEFAULT 0,          -- 本次采集到的条目数
    error_message   TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

### 3.2 Redis 用途

| **用途** | **Key 模式** | **说明** |
| --- | --- | --- |
| **共享采集缓存** | `cache:source:{source_id}:{date}` | 当日采集结果缓存，多用户访问直接命中，24h TTL |
| 去重缓存 | `dedup:{source_id}:{content_hash}` | 72 小时 TTL，Bloom Filter 或 Set |
| 任务队列 | Celery / 自定义 Queue | 异步任务分发 |
| 信息池暂存 | `pool:{date}` | 当日待处理文章的临时缓存 |
| 采集锁 | `lock:collect:{source_id}` | 防止同一信息源并发采集 |
| 订阅计数 | `subscribers:{source_id}` | 订阅某信息源的活跃用户数，用于采集优先级排序 |

---

## 4 核心模块详细设计

### 4.1 信息获取层 (Collectors)

#### 4.1.1 抽象基类

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass
class RawArticle:
    """采集到的原始文章数据结构"""
    external_id: str                # 外部唯一标识
    title: str
    url: str | None = None
    content: str | None = None
    published_at: datetime | None = None
    metadata: dict | None = None    # 扩展字段

class BaseCollector(ABC):
    """信息源采集器抽象基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """采集器名称"""
        ...

    @property
    @abstractmethod
    def category(self) -> str:
        """信息源类别: open_source / blog / academic / social"""
        ...

    @abstractmethod
    async def collect(self, config: dict) -> list[RawArticle]:
        """
        执行一次采集，返回原始文章列表。
        :param config: 信息源配置（来自 sources.config 字段）
        """
        ...

    async def health_check(self) -> bool:
        """健康检查，默认返回 True"""
        return True
```

#### 4.1.2 Collector 注册表（插件化）

```python
# collectors/registry.py
_REGISTRY: dict[str, type[BaseCollector]] = {}

def register(name: str):
    """装饰器：注册 Collector"""
    def wrapper(cls):
        _REGISTRY[name] = cls
        return cls
    return wrapper

def get_collector(name: str) -> BaseCollector:
    return _REGISTRY[name]()

def list_collectors() -> list[str]:
    return list(_REGISTRY.keys())
```

每个 Collector 实现类通过 `@register("github_trending")` 自动注册，实现零配置扩展。

#### 4.1.3 各信息源 Collector 实现

| **Collector** | **获取方式** | **关键依赖** | **优先级** |
| --- | --- | --- | --- |
| `GitHubTrendingCollector` | GitHub API / MCP | `PyGithub` / HTTP | P0 已实现 |
| `HuggingFaceCollector` | `huggingface_hub` API | `huggingface_hub` | P0 |
| `RSSCollector` | 通用 RSS/Atom 解析 | `feedparser` | P0 |
| `BlogScraperCollector` | 定向爬虫脚本 | `httpx` + `selectolax`/`BeautifulSoup` | P0 |
| `DeepBrowseCollector` | deepbrowse 浏览器 Agent | `deepbrowse` (自研) + `playwright` | P0 |
| `ArXivCollector` | arXiv 官方 API | `arxiv` | P1 |
| `RedditCollector` | Reddit API (PRAW) | `praw` | P1 |
| `TwitterCollector` | deepbrowse 抓取 | `deepbrowse` | P1 |

#### 4.1.4 降级策略

信息获取采用 **多级降级**：API → RSS → 爬虫脚本 → deepbrowse。通过 `retry.py` 模块实现：

```python
async def collect_with_fallback(source: Source) -> list[RawArticle]:
    """按优先级尝试多种采集方式"""
    methods = source.config.get("fallback_chain", [source.collect_method])
    for method in methods:
        try:
            collector = get_collector(method)
            return await collector.collect(source.config)
        except CollectError as e:
            logger.warning(f"Collector {method} failed for {source.name}: {e}")
            continue
    raise AllCollectorsFailed(source.name)
```

---

### 4.2 筛选加工层 (Processors)

#### 4.2.1 加工流水线

```python
# processors/pipeline.py
class ProcessingPipeline:
    """信息加工流水线：初筛 → 并行加工 → 输出到信息池"""

    def __init__(self, llm_client: LLMClient, dedup_store: DedupStore):
        self.filter = AIFilter(llm_client)
        self.summarizer = Summarizer(llm_client)
        self.keyword_extractor = KeywordExtractor(llm_client)
        self.dedup = DedupChecker(dedup_store)
        self.scorer = Scorer(llm_client)

    async def process(self, articles: list[RawArticle]) -> list[ProcessedArticle]:
        # Step 1: AI 初筛（剔除无关内容）
        relevant = await self.filter.filter_batch(articles)

        # Step 2: 并行加工（4 项任务同时执行）
        results = await asyncio.gather(
            self.summarizer.summarize_batch(relevant),
            self.keyword_extractor.extract_batch(relevant),
            self.dedup.check_batch(relevant),
            self.scorer.score_batch(relevant),
        )
        summaries, keywords, dedup_flags, scores = results

        # Step 3: 合并结果，排除重复和低分项
        processed = []
        for i, article in enumerate(relevant):
            if dedup_flags[i]:      # 是旧闻，跳过
                continue
            if scores[i] < SCORE_THRESHOLD:
                continue
            processed.append(ProcessedArticle(
                raw=article,
                summary=summaries[i],
                keywords=keywords[i],
                score=scores[i],
            ))
        return processed
```

#### 4.2.2 各处理器说明

| **处理器** | **输入** | **输出** | **实现要点** |
| --- | --- | --- | --- |
| `AIFilter` | 原始文章列表 | 过滤后文章列表 | 批量 LLM 判定，Prompt 含「与 AI 相关」「有报道价值」规则 |
| `Summarizer` | 文章全文 | ≤50 字摘要 | LLM 生成，带长度约束的 Prompt |
| `KeywordExtractor` | 文章全文 + 已有关键词库 | 关键词列表 | LLM 提取，已有关键词作上下文参考 |
| `DedupChecker` | 文章 + 72h 历史 | 是否重复 (bool) | 内容 hash 对比 (Redis Bloom Filter) + 语义相似度兜底 |
| `Scorer` | 文章全文 | 0.0~1.0 分值 | LLM 打分，综合新颖度、影响力、技术深度 |

#### 4.2.3 LLM 调用策略

- **统一封装**：通过 `litellm` 适配多种 LLM（OpenAI / Claude / 国产模型）
- **批量调用**：同类任务合并为 batch prompt，减少 API 调用次数
- **成本控制**：初筛和打分优先使用低成本模型（如 GPT-4o-mini），深度报告使用高质量模型
- **错误处理**：Rate Limit 自动退避重试、模型降级（主→备）

```python
# llm/client.py
class LLMClient:
    def __init__(self, config: LLMConfig):
        self.primary_model = config.primary_model     # e.g. "gpt-4o-mini"
        self.fallback_model = config.fallback_model   # e.g. "deepseek-chat"
    
    async def complete(self, prompt: str, **kwargs) -> str:
        try:
            return await litellm.acompletion(
                model=self.primary_model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs,
            )
        except RateLimitError:
            return await litellm.acompletion(
                model=self.fallback_model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs,
            )
```

---

### 4.3 输出层 (Renderers)

#### 4.3.1 模板渲染体系

```python
class BaseRenderer(ABC):
    """报告渲染器抽象基类"""
    
    @property
    @abstractmethod
    def depth(self) -> str:
        """深度: brief / deep"""
        ...

    @abstractmethod
    async def render(self, articles: list[ProcessedArticle], context: RenderContext) -> Report:
        """渲染生成对应深度的分析内容"""
        ...
```

#### 4.3.2 深度渲染逻辑

| **维度** | **触发方式与逻辑** |
| --- | --- |
| **简报 (Brief)** | 对文章内容进行总结归纳，提取关键亮点（TL;DR），适合日报/周报的高效速读场景。 |
| **深研 (Deep Dive)** | 深入全文细节与上下文，对 Github 分析代码目录与 README / 架构；对论文分析方法与对比实验；对博客长文深挖作者思路与技术启示。 |

#### 4.3.3 输出 Markdown 模板结构（L2 日报示例）

```markdown
# 🤖 AI Daily Report — {{ date }}

## TL;DR
{% for item in top_items %}
- {{ item.summary }} [→ 原文]({{ item.url }})
{% endfor %}

---

## 🐙 开源社区
{% for item in opensource_items %}
### {{ item.title }}
> {{ item.summary }}
> 
> ⭐ AI 评分: {{ item.score }} · 📡 来源: {{ item.source_name }} · [原文链接]({{ item.url }})
{% endfor %}

## 📝 技术博客
{% for item in blog_items %}
...
{% endfor %}

---

## 🏷️ 今日关键词
{{ keyword_tags }}
```

---

### 4.4 知识存储/落盘层 (Sinks)

依据外部落盘目标的开放能力不同，此层设计抽象基类与多个原生实现，并重点规范了主流工作流工具（Notion, Obsidian）的落盘最佳实践。

#### 4.4.1 抽象基类

```python
class BaseSink(ABC):
    """落盘目标抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def publish(self, report: Report, config: dict) -> PublishResult:
        """将报告发布到目标位置"""
        ...

    async def health_check(self) -> bool:
        return True
```

#### 4.4.2 各落盘实现与核心架构设计

| **Sink** | **接入方式** | **关键依赖** | **MVP** |
| --- | --- | --- | --- |
| `NotionSink` | Notion API API | `notion-client` | ✅ P0 |
| `ObsidianSink` | HTTP PUT (WebDAV) | `httpx` | ✅ P0 |
| `RssSink` | 生成标准 XML File |内置 `xml` 库 | ✅ P0 |
| `FeishuSink` | 飞书开放平台 API | `httpx` | P1 预留 |
| `DatabaseSink` | 写入 PostgreSQL | `sqlalchemy` | ✅ P0 |

#### 4.4.3 具体写入逻辑规范 (关键技术选型)

**一、 Rss 落盘方案 (被动订阅池)**
作为补充性终点，系统为最终产出的报告生成全局的标准 `RSS 2.0` 源文件。
当系统激活了 `RSS Feed` Destination 时，每当 Monitor Task 生成了一篇新 Report，系统除了将其抛给 Notion 等主动 Sink 外，也会调用 `RssSink.publish()`。
- **机制:** 该 Sink 会读取最新的 N 篇 Report，利用 Python 原生 XML 库或专门的生成器写入 `/static/feed.xml` 或直接开放 GET API `/api/v1/feed` 返回动态组装的 XML。
- **配置:** `frontend` 展示的固定 URL `http://<domain>/api/v1/feed.xml` 直接暴露给用户的第三方阅读器订阅。

**二、 Notion 落盘方案 (基于官方 API 能力)**
Notion 存在针对 Block 的严格数量截断要求，LexDeepResearch 针对不同长短的报告采取两步动态降级策略：

1. **短报告 (如日报 L2) —— 一步直写方案**
   - **端点**: `POST /v1/pages`
   - **逻辑**: 通过设置 `parent` 为目标 `database_id`，并使用 `markdown` 字段直接灌入报告正文。无需复杂的 Block 结构解析，简单快速。
   - **适用条件**: 报告块数量预估在 100 Blocks 左右及以内。

2. **长篇深度报告 (如深研 L4) —— 两步分块追加方案**
   - **端点**: 先调用 `POST /v1/pages` 创建属性元数据(不带内容)；接着通过循环调用 `PATCH /v1/blocks/{block_id}/children`。
   - **分块逻辑 (Chunking)**: 每次 `PATCH` 追加最大 **100个 Block**。<br>
   *(参考 n8n 写入机制：长篇内容必须先分块（chunk），再循环追加)*
   - **约束注意**: 每个 `rich_text` 对象最多 2000 个字符，嵌套最多 2 层。须引入重试及速率限制控制（约 `3req/s`）。

**三、 Obsidian 落盘方案 (基于 WebDAV + Remotely Save 插件)**
考虑到 LexDeepResearch 的数据收集工作流运行在云端 Linux 服务器，而用户的 Obsidian Vault 位于本地 Mac，直接使用文件系统写入或依赖 Local REST API 会面临复杂的 P2P 网络打通（如 Tailscale）与设备同时在线的要求。
因此，我们采用了 **中转解耦** 的同步架构：

- **依赖前置**：
  1. 服务端：在服务器部署一个极其轻量的 **WebDAV Server** 容器（存放 Markdown 文件）。
  2. 客户端：用户在其 Obsidian 中安装官方推荐的第三方同步插件 **Remotely Save**。
- **写入方式**：`ObsidianSink` 使用 HTTP 协议发送 PUT 请求：`PUT /{{文件夹名}}/{{报告文件名}}.md`，将内容写入服务器本地的 WebDAV 目录中。
- **拉取方式**：当用户的 Obsidian 客户端打开时，Remotely Save 插件按设定时间（或手动触发）连接 WebDAV 服务器拉取最新的 Markdown 文件。由于是纯文本 Markdown，Obsidian 会立即自动完成索引与双链解析。

**【关于自建存储选型的对比：为什么是 WebDAV 而非 MinIO/S3？】**
虽然 Remotely Save 插件也支持 S3/MinIO 作为同步中转，但在本产品 MVP 阶段的选型结论是 WebDAV，原因如下：
1. **轻量级**：我们的场景仅仅是"传输几十 KB 的 Markdown 文件"，不需要 S3 复杂的对象版本控制、分片上传和 IAM 权限管理。WebDAV 容器镜像仅 10MB、内存占用 5MB，比 MinIO (`~100MB`) 轻量极多。
2. **部署简单**：WebDAV 协议本质就是 HTTP 加上文件写入扩展（`PUT/MKCOL`），只需配置两个环境变量（用户名/密码）即可启动，不需要像 MinIO 那样配置 Bucket、Access Key 和 Region 等概念。
3. **代码侵入性低**：对 `ObsidianSink` 来说，向 WebDAV 写入只是发一个自带 Basic Auth 的 `httpx.put` HTTP 请求，复用了项目现有的 `httpx` 客户端，不需要引入重量级的 `boto3`（AWS S3 SDK）依赖。

#### 4.4.4 落盘增量更新机制

- 周报/深度报告支持追加更新模式。对于已经绑定了源 Page ID 的任务（依靠本地 DatabaseSink 暂存状态映射），可通过对应的 PATCH / Append 接口在已有文档末尾追加新采集的长内容。
- Notion 落盘支持基于预设的 Database Template 创建新 Page，保持版式输出标准统一。

---

### 4.5 调度与编排层

#### 4.5.1 定时任务调度

```python
# scheduler/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# 每日采集任务：默认 06:30 开始
scheduler.add_job(
    daily_collect_and_report,
    trigger="cron",
    hour=6, minute=30,
    id="daily_collect",
)

# 每周周报生成：周日 20:00
scheduler.add_job(
    weekly_report,
    trigger="cron",
    day_of_week="sun",
    hour=20,
    id="weekly_report",
)
```

#### 4.5.2 采集编排流程（含共享缓存）

```mermaid
flowchart TD
    START["⏰ 定时触发 / 手动触发"] --> LOAD["加载有用户订阅的信息源列表"]
    LOAD --> CACHE{"Redis 共享缓存\n是否命中？"}
    
    CACHE -->|"命中（当日已采集）"| POOL["直接使用缓存数据"]
    CACHE -->|"未命中"| PAR["并行采集（控制并发数）"]
    
    PAR --> RAW["原始文章存入 DB (status=raw)"]
    RAW --> WRITE_CACHE["写入 Redis 共享缓存\n(24h TTL)"]
    WRITE_CACHE --> PIPELINE["加工流水线处理"]
    
    PAR -->|"采集失败"| FALLBACK["降级策略"]
    FALLBACK --> PAR
    
    POOL --> PIPELINE
    PIPELINE --> PROCESSED["处理后文章存入信息池 (status=processed)"]
    PROCESSED --> DISPATCH["按用户订阅分发"]
    DISPATCH --> RENDER["为每个用户渲染个性化报告"]
    RENDER --> SINK["落盘到用户配置的目标"]
    SINK --> DONE["✅ 完成，记录任务日志"]
```

#### 4.5.3 并发控制

- 采集阶段并发数限制：默认 **5 个信息源并行**，deepbrowse 类型限制为 **2 并发**（CDP 连接资源限制）
- 使用 `asyncio.Semaphore` 实现并发控制
- Redis 分布式锁防止同一信息源重复采集

#### 4.5.4 多用户共享采集与分发机制

核心思路：**采集是全局的，分发是个性化的**。

```
信息源 A ─── 全局采集（每日 1 次）──→ 共享缓存 ──┬──→ 用户 1（关注 AI + NLP）   → 个性化筛选 → L2 日报 → Notion
                                               ├──→ 用户 2（关注 AI + CV）    → 个性化筛选 → L1 速览 → Obsidian
                                               └──→ 用户 3（关注全部）        → 个性化筛选 → L2 日报 → 飞书
```

**工作流程：**

1. **全局采集阶段**：系统按信息源维度统一调度采集，不区分用户。同一信息源在同一采集周期内只采集一次
2. **缓存写入**：采集结果写入 Redis 共享缓存（`cache:source:{source_id}:{date}`），24h TTL
3. **订阅分发**：查询 `user_subscriptions` 表，将共享信息池中的文章按用户订阅关系分发
4. **个性化处理**：每个用户可配置独立的关注关键词（`custom_config`）、评分阈值、输出格式（L1~L4）、落盘目标
5. **缓存命中**：后续用户请求或补充触发时，优先从缓存读取，避免重复采集

**采集优先级排序**：订阅用户数多的信息源优先采集（基于 Redis `subscribers:{source_id}` 计数），确保高热度信息源最先完成

---

## 5 API 接口设计

### 5.1 RESTful API

基于 FastAPI，版本前缀：`/api/v1`

#### 全局常量与枚举

| **分类值 (category)** | **时间跨度 (time_period)** | **深度 (depth)** |
| --- | --- | --- |
| `open_source`, `blog`, `academic`, `social` | `daily`, `weekly`, `custom` | `brief`, `deep` |

#### 1. Sources (信息源大厅)

为 `src/app/sources/page.tsx` 提供支持。

| **方法** | **路径** | **描述** | **优先级** |
| --- | --- | --- | --- |
| `GET` | `/api/v1/sources` | 获取全部全局信息源列表，支持 `?category=blog` 筛选。**DTO 需包含动态 `status` (healthy/error/running) 及 `last_run` 字段。** | P0 |
| `GET` | `/api/v1/sources/categories` | 获取源的大盘统计数据 (每种 category 包含的数量) | P0 |
| `POST` | `/api/v1/sources` | 新增一个自定义全局信息源。**Payload 需包含 `category`, `name`, `url` 字段，后端据此自动解析决定 `collect_method` 获取方式。** | P0 |
| `PATCH` | `/api/v1/sources/{id}` | 更新或停用该信息源 | P1 |
| `DELETE`| `/api/v1/sources/{id}` | 彻底删除（仅限无人订阅时） | P1 |

#### 2. Monitors (监控任务)

为 `src/app/monitors/page.tsx` 提供支持。

| **方法** | **路径** | **描述** | **优先级** |
| --- | --- | --- | --- |
| `GET` | `/api/v1/monitors` | 获取当前用户设定的全部监控任务规则列表 | P0 |
| `POST` | `/api/v1/monitors` | 创建新的监控任务（需传入 `time_period`, `depth`, 订阅的 `source_ids` 列表等） | P0 |
| `POST` | `/api/v1/monitors/{id}/run` | 用户手动立刻触发某一个监控规则执行一次全量采集和生成 | P0 |
| `PATCH` | `/api/v1/monitors/{id}` | 启停或修改监控规则 (如更改为每周) | P1 |
| `DELETE`| `/api/v1/monitors/{id}` | 取消关联并彻底删除该任务 | P1 |

#### 3. Reports (报告展示: Discover & Library)

为 `src/app/page.tsx` (Discover - Top 10) 和 `src/app/library/page.tsx` (全量检索) 提供支持。

| **方法** | **路径** | **描述** | **优先级** |
| --- | --- | --- | --- |
| `GET` | `/api/v1/reports` | 获取报告列表。<br>参数支持：`?time_period=xxx&depth=xxx&limit=10&page=1` | P0 |
| `GET` | `/api/v1/reports/{id}` | 查看单份报告详情上下文 | P0 |
| `GET` | `/api/v1/reports/filters` | 请求当前知识库真实可用的标签、年月分类、报告大类集合，用于点亮前端下拉框 | P0 |
| `POST` | `/api/v1/reports/custom` | 提交自定义临时报告请求（生成后不入库或作为 custom 类型入库） | P2 |

#### 4. Users / Auth (用户体系)

支撑前端左下角的个人档案面板及全局设定交互。

| **方法** | **路径** | **描述** | **优先级** |
| --- | --- | --- | --- |
| `GET` | `/api/v1/users/me` | 获取当前登录用户的基本信息（昵称，邮箱，订阅计划如 Free Plan 等） | P0 |
| `PATCH` | `/api/v1/users/me/settings` | 修改用户的全局配置选项或偏好设置 | P0 |

#### 4. Articles (文章与底层数据)

为生成报告提供底层支撑及后续的图谱联调支持。

| **方法** | **路径** | **描述** | **优先级** |
| --- | --- | --- | --- |
| `GET` | `/api/v1/articles` | 查询原始文章，支持按源、分类、日期、评分阈值过滤 | P0 |
| `GET` | `/api/v1/articles/{id}` | 查看单篇文章详情以及其关联的 reports 引用 | P0 |

### 5.2 WebSocket (P1)

用于实时推送采集进度和任务状态：

```
WS /api/v1/ws/tasks/{task_id}   # 订阅某采集任务的实时进度
```

---

## 6 浏览器引擎与 deepbrowse 集成方案

### 6.1 整体定位

deepbrowse 是 LexDeepResearch 的 **核心差异化能力**，作为信息获取的兜底方案和高级能力层。

浏览器引擎采用 **Browser Provider 抽象层** 设计，deepbrowse Agent 不关心底层浏览器来源，只通过统一接口操作。Playwright 的定位是 **本地模式下的浏览器驱动库**，而非系统的核心依赖。

### 6.2 Browser Provider 架构

```mermaid
flowchart TB
    DB["deepbrowse Agent"] --> BP["BrowserProvider 抽象层"]
    
    BP --> LOCAL["LocalBrowserProvider\n本地浏览器模式"]
    BP --> CLOUD["CloudBrowserProvider\n云浏览器模式"]
    
    LOCAL --> PW["Playwright 驱动"]
    PW --> LC["本地 Chromium 实例"]
    
    CLOUD --> CDP["CDP 直连"]
    CDP --> RC["远程浏览器实例\n(Browserless / 自建集群 / lexmount)"]
    
    DB --> LM["lexmount 凭证管理\nCookie / Token 注入"]
```

#### 6.2.1 Provider 抽象接口

```python
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager

class BrowserProvider(ABC):
    """浏览器实例提供者抽象基类"""

    @abstractmethod
    @asynccontextmanager
    async def get_browser_context(self, **kwargs):
        """获取一个可用的浏览器上下文（Page 级别）"""
        yield

    @abstractmethod
    async def health_check(self) -> bool:
        ...


class LocalBrowserProvider(BrowserProvider):
    """
    本地浏览器模式：通过 Playwright 启动和管理本地 Chromium 实例。
    适用场景：开发环境、低成本部署、无需远程浏览器服务。
    """
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser = None

    @asynccontextmanager
    async def get_browser_context(self, **kwargs):
        if not self._browser:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
        context = await self._browser.new_context(**kwargs)
        try:
            yield context
        finally:
            await context.close()


class CloudBrowserProvider(BrowserProvider):
    """
    云浏览器模式：通过 CDP (Chrome DevTools Protocol) 连接远程浏览器实例。
    适用场景：生产环境、高并发、需要稳定的浏览器集群。
    支持：Browserless、自建 Chrome 集群、lexmount 托管浏览器。
    """
    def __init__(self, cdp_endpoint: str):
        self.cdp_endpoint = cdp_endpoint  # e.g. "ws://cloud-browser:3000"

    @asynccontextmanager
    async def get_browser_context(self, **kwargs):
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        browser = await pw.chromium.connect_over_cdp(self.cdp_endpoint)
        context = await browser.new_context(**kwargs)
        try:
            yield context
        finally:
            await context.close()
            await browser.close()
            await pw.stop()
```

#### 6.2.2 两种模式对比

| **维度** | **本地模式 (LocalBrowserProvider)** | **云模式 (CloudBrowserProvider)** |
| --- | --- | --- |
| **底层驱动** | Playwright 管理的本地 Chromium | CDP 直连远程浏览器实例 |
| **适用环境** | 开发 / 测试 / 轻量级部署 | 生产环境 / 高并发场景 |
| **启动成本** | 需要本地安装 Chromium | 无需本地浏览器，连接现有集群 |
| **并发能力** | 受本地资源限制（CPU/内存） | 横向扩展，依赖云端集群规模 |
| **稳定性** | 受本地环境影响 | 云端统一管理，更稳定 |
| **典型服务** | 直接启动 | Browserless / Steel / 自建集群 |

### 6.3 使用场景

| **场景** | **说明** |
| --- | --- |
| 无 API/RSS 技术博客 | 约 20 家无 RSS 的技术博客，deepbrowse 作为爬虫脚本失败时的兜底 |
| 动态渲染页面 | SPA 类技术博客需要 JS 渲染才能获取内容 |
| X (Twitter) 抓取 | 官方 API 已无免费方案，通过 deepbrowse + 登录态抓取 |
| API 挖掘 | 通过浏览器 DevTools 分析隐藏 API 接口 |

### 6.4 资源管理

- **浏览器实例池**：
  - 本地模式：预启动 1~2 个 Chromium 实例，通过 Playwright 管理生命周期
  - 云模式：连接远程浏览器池，通过 CDP endpoint 复用连接
- **并发限制**：默认 2 并发（可在配置中调整），本地模式受限于本地资源，云模式可依据集群规模放大
- **超时控制**：单次 deepbrowse 采集任务超时 60 秒
- **登录态管理**：通过 lexmount 管理的 Cookie/Token 注入浏览器上下文
- **自动降级**：云浏览器连接失败时，可自动降级到本地模式

---

## 7 配置管理

### 7.1 配置层级

```
环境变量 (.env)  →  覆盖  →  YAML 配置文件  →  覆盖  →  代码默认值
```

### 7.2 核心配置项

```yaml
# config.yaml

app:
  name: LexDeepResearch
  debug: false
  log_level: INFO

database:
  url: postgresql+asyncpg://user:pass@localhost:5432/lexdeepresearch
  pool_size: 10

redis:
  url: redis://localhost:6379/0

llm:
  primary_model: gpt-4o-mini
  fallback_model: deepseek-chat
  api_key: ${OPENAI_API_KEY}
  max_tokens: 2048
  temperature: 0.3

scheduler:
  daily_collect_time: "06:30"
  weekly_report_day: "sunday"
  weekly_report_time: "20:00"

collector:
  max_concurrency: 5
  deepbrowse_concurrency: 2
  timeout_seconds: 60
  retry_max_attempts: 3

browser:
  provider: local                    # local | cloud
  local:
    headless: true
  cloud:
    cdp_endpoint: ws://cloud-browser:3000
    # 支持 Browserless / Steel / 自建集群

processor:
  score_threshold: 0.4
  dedup_window_hours: 72

sink:
  default: notion
  notion:
    api_key: ${NOTION_API_KEY}
    database_id: ${NOTION_DATABASE_ID}
  obsidian:
    vault_path: /path/to/obsidian/vault
```

---

## 8 部署方案

### 8.1 本地开发

```yaml
# docker-compose.yml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: .env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on:
      - backend

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: lexdeepresearch
      POSTGRES_USER: lex
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

volumes:
  pgdata:
```

### 8.2 生产部署 (P1)

- **云服务**：推荐 Railway / Fly.io / AWS ECS（容器化部署）
- **数据库**：Supabase / Neon (托管 PostgreSQL) 或自管理
- **域名 + HTTPS**：Cloudflare / Nginx Reverse Proxy
- **监控**：Sentry (错误追踪) + Prometheus + Grafana (P2)

---

## 9 文档层 — Mintlify

### 9.1 定位与价值

使用 [Mintlify](https://mintlify.com) 构建项目文档站点，统一承载 API 参考文档、用户指南和开发者文档。

| **文档类型** | **目标读者** | **内容** |
| --- | --- | --- |
| **API 参考** | 前端开发 / 集成方** | 自动从 FastAPI OpenAPI Schema 生成，保持与代码同步 |
| **用户指南** | 产品使用者 | 快速开始、信息源配置、落盘目标设置、自定义模板 |
| **开发者文档** | 贡献者 / 内部团队 | 架构说明、如何编写 Collector 插件、部署指南 |

### 9.2 核心配置

```json
// docs/mint.json
{
  "name": "LexDeepResearch",
  "logo": { "dark": "/logo/dark.svg", "light": "/logo/light.svg" },
  "favicon": "/favicon.svg",
  "colors": { "primary": "#6366F1", "light": "#818CF8", "dark": "#4F46E5" },
  "navigation": [
    { "group": "开始", "pages": ["introduction", "quickstart"] },
    {
      "group": "API 参考",
      "pages": [
        "api-reference/sources",
        "api-reference/articles",
        "api-reference/tasks",
        "api-reference/reports"
      ]
    },
    {
      "group": "用户指南",
      "pages": [
        "guides/add-source",
        "guides/configure-sink",
        "guides/custom-template"
      ]
    },
    {
      "group": "开发者",
      "pages": [
        "development/architecture",
        "development/collector-plugin",
        "development/deployment"
      ]
    }
  ],
  "openapi": "https://api.lexdeepresearch.com/openapi.json"
}
```

### 9.3 OpenAPI 自动集成

FastAPI 天然生成 OpenAPI 3.0 Schema，Mintlify 通过 `openapi` 字段自动拉取并渲染为交互式 API 文档。开发阶段可直接指向本地 `http://localhost:8000/openapi.json`。

### 9.4 文档部署

- **本地预览**：`npx mintlify dev` 在 `docs/` 目录下启动
- **生产部署**：连接 GitHub 仓库后，Mintlify 自动 CI/CD，每次 `docs/` 目录变更自动重新部署
- **自定义域名**：配置 CNAME 指向 `docs.lexdeepresearch.com`

---

## 10 MVP 交付范围与里程碑

### 10.1 MVP 交付清单

| **模块** | **MVP 范围** | **P1+ 预留** |
| --- | --- | --- |
| **信息获取** | GitHub Trending + HuggingFace + RSS (7家) + 爬虫脚本 (20+家) + deepbrowse 兜底 | arXiv / Reddit / X |
| **筛选加工** | AI 初筛 + 摘要 + 关键词 + 去重 + 打分 | 信息溯源标注 |
| **输出** | L2 日报（默认） + L1 速览（自动精简） | L3 周报 / L4 深度报告 |
| **落盘** | Notion + Obsidian/本地 Markdown | 飞书 / 数据库查询 |
| **Web 平台** | 采集结果列表 + 信息源状态面板 + 手动触发 | 完整 Dashboard |
| **调度** | 每日定时采集 + 手动触发 | 用户自定义频率 |

### 10.2 里程碑规划

```mermaid
gantt
    title LexDeepResearch MVP 里程碑
    dateFormat YYYY-MM-DD
    
    section 基础搭建
    项目脚手架 + DB 设计          :m1, 2026-03-01, 3d
    配置管理 + LLM Client        :m2, after m1, 2d
    
    section 信息获取层
    Collector 基类 + Registry     :m3, after m2, 2d
    GitHub Trending Collector     :m4, after m3, 1d
    HuggingFace Collector         :m5, after m3, 2d
    RSS Collector                 :m6, after m3, 2d
    Blog Scraper Collector        :m7, after m6, 3d
    deepbrowse Collector          :m8, after m7, 3d
    
    section 筛选加工层
    Processing Pipeline           :m9, after m8, 4d
    
    section 输出层
    L2 日报 Renderer              :m10, after m9, 2d
    L1 速览 Renderer              :m11, after m10, 1d
    
    section 落盘层
    Notion Sink                   :m12, after m10, 2d
    Obsidian Sink                 :m13, after m10, 1d
    
    section 调度与编排
    Scheduler + Orchestrator      :m14, after m12, 2d
    
    section Web 平台 (MVP)
    API 接口开发                   :m15, after m14, 3d
    前端页面开发                   :m16, after m15, 3d
    
    section 集成测试
    端到端测试与修复              :m17, after m16, 3d
```

---

## 11 扩展性预留

### 11.1 P1 多代理 Agent 集群

当前 MVP 采用单一 Orchestrator 顺序编排。P1 阶段将引入多代理架构：

- `Planner Agent`：接收配置 → 拆解为子任务
- `Router Agent`：按信息源类型分发给对应子 Agent
- `Critic Agent`：交叉验证与事实核查
- `Synthesis Agent`：汇总生成最终报告

**预留点**：Orchestrator 内部留有 `strategy` 接口，可替换为 Agent 集群调度策略。

### 11.2 P2 知识图谱

- 数据库预留 `metadata` JSONB 字段存储实体和关系
- 文章表预留 `keywords` 字段用于实体提取
- 后续可引入 Neo4j 或 PostgreSQL 的图扩展（Apache AGE）

### 11.3 P3 Human-in-the-Loop

- 文章表 `status` 字段支持 `pending_review` 状态
- API 预留 `PATCH /api/v1/articles/{id}/review` 端点

---

## 12 安全与合规

| **方面** | **措施** |
| --- | --- |
| **API Key 管理** | 环境变量 + Secret Manager，不入库不入代码 |
| **爬虫合规** | 遵守 `robots.txt`；设置合理请求间隔（≥2s）；标识自定义 User-Agent |
| **数据隐私** | 不抓取用户隐私数据；社交媒体仅抓取公开信息 |
| **LLM 数据安全** | 敏感信息不传入 LLM；使用企业级 API 通道 |
| **访问控制 (P1)** | JWT 认证 + RBAC 权限模型 |

---

## 13 测试策略

| **层级** | **覆盖范围** | **工具** |
| --- | --- | --- |
| **单元测试** | Collector / Processor / Renderer / Sink 各模块 | `pytest` + `pytest-asyncio` |
| **集成测试** | 采集 → 加工 → 渲染 → 落盘全流程 | `pytest` + `testcontainers` (PG/Redis) |
| **E2E 测试** | API 接口 + 前端页面 | `httpx` (API) + `Playwright` (前端) |
| **Mock 策略** | 外部 API / LLM 调用全部 Mock | `respx` + `unittest.mock` |

---

## 14 监控与可观测性

### MVP 阶段

- **结构化日志**：`structlog` / `loguru`，JSON 格式输出
- **采集任务追踪**：`collect_tasks` 表记录每次任务的状态、耗时、采集条数、错误信息

### P1+ 扩展

- **APM**：Sentry Performance 追踪关键流程耗时
- **Metrics**：Prometheus + Grafana 监控采集成功率、LLM 调用量、API 响应时间
- **告警**：采集失败率 > 20% / LLM 成本超预算时通知
