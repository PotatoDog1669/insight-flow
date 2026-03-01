# Blog Source Preset Catalog（预制清单）

## 目的

将当前确认的厂商来源落盘为可执行预制清单，作为后续 `sources` 种子数据与采集器配置输入。

对应机器可读文件：  
[`source_presets.yaml`](/Users/leo/workspace/Lexmount/LexDeepResearch/backend/app/collectors/source_presets.yaml)

---

## 当前规模（2026-03-01）

- 总来源数：`40`
- `rss_status=provided`：`6`
- `rss_status=claimed_yes_url_tbd`：`0`
- `rss_status=none`：`25`
- `rss_status=n_a`：`8`
- `rss_status=invalid_proxy`：`1`

---

## 特别说明

- Anthropic 代理 RSS 地址 `http://43.160.197.144:1200/anthropic/news` 已由用户确认无效，已标记为 `invalid_proxy`，策略改为 `site_profile_scraper`。

---

## 已完成的 RSS 回填（2026-03-01）

- 回填为 `provided`：
  - Microsoft Research: `https://www.microsoft.com/en-us/research/blog/feed/`
  - NVIDIA: `https://blogs.nvidia.com/blog/category/enterprise/deep-learning/feed/`
  - 美团: `https://tech.meituan.com/feed/`
  - Hugging Face Blog: `https://huggingface.co/blog/feed.xml`
- 回填为 `none`（未发现可用 RSS）：
  - Meta AI
  - Amazon Science
  - MiniMax

---

## 执行约定

- `strategy=rss_then_article_fulltext`：先 RSS，再逐条进详情页抓全文。
- `strategy=rss_if_found_else_site_profile_scraper`：先做 RSS 发现；未命中则走站点 profile 抓取。
- `strategy=site_profile_scraper`：直接走站点模式抓取。
- `strategy=github_only/github_plus_docs/github_paper_only/manual_research`：非标准 blog 流量，默认不纳入 P0 自动日报主链路。

---

## 与 Task 4 的关系

- Task 4.1~4.5 的验收覆盖对象应以该清单为准。
- P0 最低要求：
  - 所有 `priority=p0 && enabled=true` 的来源必须有可运行采集路径。
  - `rss_status=provided` 来源必须走两段式全文抓取，不得仅存 feed 摘要。
