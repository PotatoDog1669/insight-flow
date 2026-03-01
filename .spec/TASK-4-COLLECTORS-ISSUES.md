# Task 4 Issue Breakdown: Collectors（4.1 ~ 4.5）

> 关联主任务：`/.spec/TASK-P0-MVP-E2E.md` 的「子任务 4」
>  
> 使用方式：每个小节可直接作为一个 GitHub Issue 模板使用。

---

## 公共约定（适用于 4.1~4.5）

### A. 输出对象统一 Schema（`RawArticle`）

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class RawArticle:
    external_id: str              # 源内稳定唯一键
    title: str
    url: str | None = None
    content: str | None = None    # 正文全文/README
    published_at: datetime | None = None
    metadata: dict = field(default_factory=dict)
```

### B. 入库映射约定（Collector -> `articles`）

- `external_id` -> `articles.external_id`
- `title` -> `articles.title`
- `url` -> `articles.url`
- `content` -> `articles.raw_content`
- `published_at` -> `articles.published_at`
- `metadata` -> `articles.metadata`
- `status` 初始值：`raw`

### C. 非功能要求（统一）

- 每次采集必须包含超时、重试、错误日志。
- 采集失败不能导致整批中断，需记录失败项并继续。
- 网络请求默认 `User-Agent` 与 `timeout` 可配置。

### D. 预制来源基线

- 所有 4.x issue 的来源基线使用：`backend/app/collectors/source_presets.yaml`
- 清单说明见：`.spec/BLOG-SOURCE-PRESET-CATALOG.md`
- Task 4 验收时至少覆盖：`priority=p0 && enabled=true` 的全部来源

---

## 4.1 Issue: RSS 两段式采集（Feed 元数据 + 详情页全文）

### 目标

实现 RSS/Atom 的两段式抓取，确保输出不是 feed 摘要，而是详情页正文全文。

### 范围

- 修改 `backend/app/collectors/rss.py`
- 新增正文抽取模块（建议）：`backend/app/collectors/fulltext.py`
- 新增测试：`backend/tests/collectors/test_rss_collector.py`

### 输入（Config Schema）

```json
{
  "feed_url": "https://openai.com/blog/rss.xml",
  "source_id": "11111111-1111-1111-1111-111111111111",
  "max_items": 30,
  "timeout_seconds": 20,
  "retry_max_attempts": 3,
  "user_agent": "LexDeepResearchBot/0.1",
  "extractor_chain": ["trafilatura", "readability", "selectolax", "bs4"]
}
```

### 输出（Metadata Schema）

```json
{
  "collector": "rss",
  "feed_url": "https://openai.com/blog/rss.xml",
  "extractor": "trafilatura",
  "content_length": 12345,
  "fetched_at": "2026-03-01T04:00:00Z",
  "tags": ["openai", "blog"]
}
```

### 验收命令

```bash
cd backend
pytest tests/collectors/test_rss_collector.py -q
pytest tests/collectors/test_rss_collector.py::test_rss_fetches_full_article_content_not_feed_summary -q
pytest tests/collectors/test_rss_collector.py::test_rss_extractor_fallback_chain -q
```

### 完成定义（DoD）

- `RawArticle.content` 为详情页正文（长度阈值可配置，例如 `>= 500` 字符）。
- 当首选抽取器失败时，能自动回退到下一个抽取器。
- 单条失败不影响整批输出。

---

## 4.2 Issue: GitHub Trending Daily Top10 + Repo 增强采集

### 目标

抓取当日 GitHub Trending Top10，并补齐 repo、README、代码结构索引，为 Brief/Deep 输入打底。

### 范围

- 修改 `backend/app/collectors/github_trending.py`
- 可选新增 GitHub API client：`backend/app/collectors/github_client.py`
- 新增测试：`backend/tests/collectors/test_github_trending_collector.py`

### 输入（Config Schema）

```json
{
  "since": "daily",
  "limit": 10,
  "language": null,
  "include_readme": true,
  "include_repo_tree": true,
  "repo_tree_depth": 2,
  "github_token": "",
  "timeout_seconds": 20,
  "retry_max_attempts": 3
}
```

### 输出（Metadata Schema）

```json
{
  "collector": "github_trending",
  "repo_full_name": "owner/repo",
  "stars_today": 1024,
  "stars_total": 12345,
  "language": "Python",
  "description": "repo description",
  "readme_source": "github_api",
  "readme_chars": 8000,
  "repo_tree": ["src/", "README.md", "docs/"],
  "fetched_at": "2026-03-01T04:00:00Z"
}
```

### 验收命令

```bash
cd backend
pytest tests/collectors/test_github_trending_collector.py -q
pytest tests/collectors/test_github_trending_collector.py::test_extracts_daily_top10 -q
pytest tests/collectors/test_github_trending_collector.py::test_fetches_repo_readme_and_tree_index -q
```

### 完成定义（DoD）

- 返回固定 Top10（去除 sponsor/噪音链接）。
- 每个 repo 都有 `README`（Brief 输入）和 `repo_tree`（Deep 输入）。
- GitHub API 受限时有降级策略（例如只保留 Trending 页面解析结果）。

---

## 4.3 Issue: Hugging Face Daily Papers 采集器

### 目标

以 Daily Papers 为主入口，建立稳定的论文发现流，并补充 paper 详情与 arXiv 相关仓库关联。

### 范围

- 修改 `backend/app/collectors/huggingface.py`
- 新增测试：`backend/tests/collectors/test_huggingface_collector.py`

### 输入（Config Schema）

```json
{
  "limit": 30,
  "p": 0,
  "date": null,
  "week": null,
  "month": null,
  "submitter": null,
  "sort": "trending",
  "include_paper_detail": true,
  "include_arxiv_repos": true,
  "timeout_seconds": 20,
  "retry_max_attempts": 3
}
```

### 输出（Metadata Schema）

```json
{
  "collector": "huggingface_daily_papers",
  "paper_id": "2509.02523",
  "source_endpoint": "/api/daily_papers",
  "authors": ["A", "B"],
  "summary_source": "hf_paper_detail",
  "arxiv_repos": {
    "models": [],
    "datasets": [],
    "spaces": []
  },
  "fetched_at": "2026-03-01T04:00:00Z"
}
```

### 验收命令

```bash
cd backend
pytest tests/collectors/test_huggingface_collector.py -q
pytest tests/collectors/test_huggingface_collector.py::test_collects_daily_papers_with_filters -q
pytest tests/collectors/test_huggingface_collector.py::test_enriches_with_paper_detail_or_arxiv_repos -q
```

### 完成定义（DoD）

- 能从 Daily Papers 成功拉取并转成 `RawArticle`。
- 至少打通 1 条增强链路（paper detail 或 arxiv repos）。
- 详情接口失败时可回退，不阻断主流程。

### 接口参考

- `GET https://huggingface.co/api/daily_papers`
- `GET https://huggingface.co/api/papers/{paperId}`（实测可用）
- `GET https://huggingface.co/api/arxiv/{paperId}/repos`（实测可用）
- `GET https://huggingface.co/api/papers/search`

---

## 4.4 Issue: 无 RSS Blog 抓取与 `site_profile` 体系

### 目标

针对无 RSS 的 blog 建立可维护的站点模式配置体系，支持列表页发现 + 详情页全文抓取。

### 范围

- 修改 `backend/app/collectors/blog_scraper.py`
- 新增 profile 目录：`backend/app/collectors/site_profiles/`
- 新增 profile 读取/校验模块（建议）：`backend/app/collectors/site_profile_loader.py`
- 新增测试：`backend/tests/collectors/test_blog_scraper_profiles.py`

### 输入（Site Profile Schema）

```yaml
site_key: openai_blog
start_urls:
  - https://openai.com/news/
list_page:
  item_selector: "article a[href]"
  title_selector: "h2"
  url_attr: "href"
  published_selector: "time"
  published_attr: "datetime"
detail_page:
  content_selector: "article"
  remove_selectors:
    - "script"
    - "style"
    - "nav"
  published_selector: "time"
  published_attr: "datetime"
normalization:
  url_prefix: "https://openai.com"
  min_content_chars: 500
```

### 输出（Metadata Schema）

```json
{
  "collector": "blog_scraper",
  "site_key": "openai_blog",
  "profile_version": "v1",
  "content_selector": "article",
  "cleaning_applied": ["script", "style", "nav"],
  "content_length": 9800,
  "fetched_at": "2026-03-01T04:00:00Z"
}
```

### 验收命令

```bash
cd backend
pytest tests/collectors/test_blog_scraper_profiles.py -q
pytest tests/collectors/test_blog_scraper_profiles.py::test_profile_driven_list_and_detail_extraction -q
pytest tests/collectors/test_blog_scraper_profiles.py::test_two_sites_with_different_profiles -q
```

### 完成定义（DoD）

- 至少 2 个无 RSS 站点可稳定抓到全文。
- 每个站点差异通过 `site_profile` 管理，不写死在 collector 逻辑中。
- profile 变更不需要改核心采集代码。

---

## 4.5 Issue: 站点模式挖掘 Skill 化（可复用接入流程）

### 目标

把“无 RSS 站点模式挖掘”固化为 skill，降低新增站点接入成本。

### 范围

- 新增 skill 目录（建议）：
  - `.agents/skills/blog-pattern-mining/SKILL.md`
  - `.agents/skills/blog-pattern-mining/templates/site_profile.template.yaml`
  - `.agents/skills/blog-pattern-mining/checklists/validation.md`
- 新增 profile 校验脚本（建议）：
  - `backend/scripts/validate_site_profile.py`
- 新增文档：
  - `docs/development/collector-plugin.mdx`（新增 section）

### 输入（Skill 执行输入）

```yaml
target_site: https://example.com/blog
list_page_urls:
  - https://example.com/blog
sample_article_urls:
  - https://example.com/blog/post-1
  - https://example.com/blog/post-2
acceptance_threshold:
  min_content_chars: 500
  success_ratio: 0.8
```

### 输出（Skill 产物）

```yaml
site_profile: backend/app/collectors/site_profiles/example_blog.yaml
validation_report:
  sampled_articles: 5
  success_count: 4
  success_ratio: 0.8
  failed_cases:
    - url: "https://example.com/blog/post-x"
      reason: "content selector empty"
```

### 验收命令

```bash
cd backend
python scripts/validate_site_profile.py --profile app/collectors/site_profiles/example_blog.yaml
pytest tests/collectors/test_blog_scraper_profiles.py::test_profile_contract_validation -q
```

### 完成定义（DoD）

- 新站点接入可按 skill 流程执行并产出标准 profile。
- 校验报告可复现，失败原因可定位。
- 团队成员可在不改 collector 代码的情况下新增站点。

---

## 建议分配顺序

1. `4.1 RSS`  
2. `4.2 GitHub Trending`  
3. `4.3 HuggingFace Daily Papers`  
4. `4.4 Blog + site_profile`  
5. `4.5 Skill 化`  
