# RSS Verification Report（2026-03-01）

## 背景

针对 `source_presets.yaml` 中原 `rss_status=claimed_yes_url_tbd` 的 7 个来源进行实测验证并回填。

验证时间：**2026-03-01**  
验证方式：`curl -L --max-time 20` + 响应体是否为 RSS/XML（`<rss>/<feed>`）

---

## 结果总览

| Source Key | URL / Candidate | HTTP | Feed 判定 | 结论 |
| --- | --- | ---: | --- | --- |
| `microsoft_research` | `https://www.microsoft.com/en-us/research/blog/feed/` | 200 | feed | 可用，回填 `provided` |
| `nvidia` | `https://blogs.nvidia.com/blog/category/enterprise/deep-learning/feed/` | 200 | feed | 可用，回填 `provided` |
| `meituan_longcat` | `https://tech.meituan.com/feed/` | 200 | feed | 可用，回填 `provided` |
| `huggingface_blog` | `https://huggingface.co/blog/feed.xml` | 200 | feed | 可用，回填 `provided` |
| `meta_ai` | `https://ai.meta.com/blog/rss.xml` | 404 | non-feed | 未发现可用 RSS，回填 `none` |
| `amazon_science` | `https://www.amazon.science/blog/rss.xml` | 404 | non-feed | 未发现可用 RSS，回填 `none` |
| `minimax` | `https://minimax.io/news/rss.xml` | 404 | non-feed | 未发现可用 RSS，回填 `none` |

---

## 备注

- Microsoft Research feed 对不同 UA 行为不一致：
  - `python-httpx/0.28.1` 返回 200 + RSS；
  - 部分浏览器 UA 可能返回 403。
- NVIDIA 页面可解析出 `rel=alternate` feed 链接并已验证成功。
- Meta/Amazon/MiniMax 在常见 feed 路径（`/rss.xml`、`/feed.xml`、`/rss`、`/feed`）下未发现可用 RSS。

---

## 已落盘修改

- 机器可读清单更新：`backend/app/collectors/source_presets.yaml`
- 汇总目录更新：`.spec/BLOG-SOURCE-PRESET-CATALOG.md`

