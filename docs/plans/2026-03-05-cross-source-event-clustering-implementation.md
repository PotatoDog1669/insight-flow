# Cross-Source Event Clustering in Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在一次 monitor run 内，将跨来源（官网/X/社区）指向同一事件的重复条目在 pipeline 内合并为单事件，减少日报重复，同时保留多来源证据。

**Architecture:** 保持现有采集与时间窗过滤不变，在“主题筛选后、结构化加工前”增加跨来源聚类阶段。聚类采用“两轮法”：先规则聚类（URL/标题高置信匹配），再对剩余候选做一次轻量语义聚类。首版不改数据库主模型，通过 `metadata` 承载聚类溯源字段，确保一次性落地且可回滚。

**Tech Stack:** Python 3.12, asyncio, FastAPI, SQLAlchemy, Pydantic Settings, pytest, 现有 LLM/Codex provider helpers

---

## Implementation Notes

- 执行时强制使用 `@test-driven-development`（先红后绿）。
- 完成前强制使用 `@verification-before-completion`（证据化验收）。
- 本方案首版 **不做 Alembic 迁移**，避免扩大变更面；聚类信息先存 `Article.metadata` 与 `Report.metadata`。

---

### Task 1: Add deterministic cross-source clustering primitives

**Files:**
- Create: `backend/app/processors/event_clustering.py`
- Test: `backend/tests/processors/test_event_clustering.py`

**Step 1: Write failing tests**

```python
from app.collectors.base import RawArticle
from app.processors.event_clustering import (
    ClusterCandidate,
    cluster_by_rules,
    normalize_url,
    select_primary_index,
)


def test_normalize_url_removes_tracking_fragment_and_www() -> None:
    raw = "https://www.openai.com/blog/gpt-5/?utm_source=x#section"
    assert normalize_url(raw) == "https://openai.com/blog/gpt-5"


def test_cluster_by_rules_merges_candidates_with_same_normalized_url() -> None:
    c1 = ClusterCandidate(raw=RawArticle(external_id="b1", title="blog", url="https://openai.com/blog/gpt-5", content="..."), source_id="openai_blog", source_name="OpenAI Blog")
    c2 = ClusterCandidate(raw=RawArticle(external_id="x1", title="tweet", url="https://x.com/openai/status/1", content="see https://openai.com/blog/gpt-5"), source_id="x_openai", source_name="OpenAI X")
    clusters = cluster_by_rules([c1, c2])
    assert clusters == [[0, 1]]


def test_select_primary_index_prefers_official_source_tier_then_content_len() -> None:
    c1 = ClusterCandidate(raw=RawArticle(external_id="x1", title="x", url="https://x.com/openai/status/1", content="short"), source_id="x_openai", source_name="OpenAI X")
    c2 = ClusterCandidate(raw=RawArticle(external_id="b1", title="blog", url="https://openai.com/blog/gpt-5", content="long long long"), source_id="openai_blog", source_name="OpenAI Blog")
    idx = select_primary_index([c1, c2], [0, 1])
    assert idx == 1
```

**Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/python -m pytest tests/processors/test_event_clustering.py -v`
Expected: FAIL with `ModuleNotFoundError: app.processors.event_clustering`

**Step 3: Write minimal implementation**

```python
# backend/app/processors/event_clustering.py
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import re

from app.collectors.base import RawArticle

_TRACKING_KEYS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid"}
_SOURCE_TIER = {
    "openai_blog": 0,
    "anthropic_blog": 0,
    "deepmind_blog": 0,
    "paper": 1,
    "github": 2,
    "news": 3,
    "x": 4,
    "reddit": 4,
}


@dataclass(slots=True)
class ClusterCandidate:
    raw: RawArticle
    source_id: str
    source_name: str


def normalize_url(raw_url: str) -> str:
    parsed = urlparse(str(raw_url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return ""
    host = parsed.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+", "/", parsed.path).rstrip("/") or "/"
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False) if k.lower() not in _TRACKING_KEYS]
    normalized_query = urlencode(query)
    return urlunparse((parsed.scheme.lower(), host, path, "", normalized_query, "")).rstrip("?")


def _candidate_urls(candidate: ClusterCandidate) -> set[str]:
    urls: set[str] = set()
    if candidate.raw.url:
        normalized = normalize_url(candidate.raw.url)
        if normalized:
            urls.add(normalized)
    content = str(candidate.raw.content or "")
    for match in re.findall(r"https?://[^\s)]+", content):
        normalized = normalize_url(match)
        if normalized:
            urls.add(normalized)
    return urls


def cluster_by_rules(candidates: list[ClusterCandidate]) -> list[list[int]]:
    if not candidates:
        return []
    parent = list(range(len(candidates)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        pa, pb = find(a), find(b)
        if pa != pb:
            parent[pb] = pa

    candidate_urls = [_candidate_urls(item) for item in candidates]
    for left in range(len(candidates)):
        for right in range(left + 1, len(candidates)):
            if candidate_urls[left] & candidate_urls[right]:
                union(left, right)

    groups: dict[int, list[int]] = {}
    for index in range(len(candidates)):
        groups.setdefault(find(index), []).append(index)
    return [sorted(items) for items in groups.values()]


def select_primary_index(candidates: list[ClusterCandidate], members: list[int]) -> int:
    scored = []
    for idx in members:
        item = candidates[idx]
        key = item.source_id.lower()
        tier = 9
        for marker, value in _SOURCE_TIER.items():
            if marker in key:
                tier = min(tier, value)
        content_len = len(str(item.raw.content or ""))
        scored.append((tier, -content_len, idx))
    scored.sort()
    return scored[0][2]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/python -m pytest tests/processors/test_event_clustering.py -v`
Expected: PASS (3 passed)

**Step 5: Commit**

```bash
git add backend/app/processors/event_clustering.py backend/tests/processors/test_event_clustering.py
git commit -m "feat: add deterministic cross-source event clustering primitives"
```

---

### Task 2: Add semantic clustering fallback and prompts

**Files:**
- Modify: `backend/app/processors/event_clustering.py`
- Create: `backend/app/prompts/agent/cluster.md`
- Create: `backend/app/prompts/llm/cluster.md`
- Test: `backend/tests/processors/test_event_clustering.py`

**Step 1: Write failing tests**

```python
import pytest

from app.collectors.base import RawArticle
from app.processors.event_clustering import ClusterCandidate, cluster_with_semantic_fallback


@pytest.mark.asyncio
async def test_semantic_cluster_called_for_unresolved_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"count": 0}

    async def _fake_semantic(candidates, provider_name, provider_config):
        called["count"] += 1
        return [[0, 1]]

    monkeypatch.setattr("app.processors.event_clustering.semantic_cluster_candidates", _fake_semantic)

    c1 = ClusterCandidate(raw=RawArticle(external_id="1", title="OpenAI released GPT-5", url="https://a.com/1", content="..."), source_id="news_a", source_name="News A")
    c2 = ClusterCandidate(raw=RawArticle(external_id="2", title="GPT-5 launch by OpenAI", url="https://b.com/2", content="..."), source_id="news_b", source_name="News B")

    clusters = await cluster_with_semantic_fallback([c1, c2], provider_name="llm_openai", provider_config={})
    assert called["count"] == 1
    assert clusters == [[0, 1]]


@pytest.mark.asyncio
async def test_semantic_invalid_output_falls_back_to_singletons(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_semantic(candidates, provider_name, provider_config):
        return [[999]]

    monkeypatch.setattr("app.processors.event_clustering.semantic_cluster_candidates", _fake_semantic)

    c1 = ClusterCandidate(raw=RawArticle(external_id="1", title="A", url="https://a.com", content="..."), source_id="s1", source_name="S1")
    c2 = ClusterCandidate(raw=RawArticle(external_id="2", title="B", url="https://b.com", content="..."), source_id="s2", source_name="S2")

    clusters = await cluster_with_semantic_fallback([c1, c2], provider_name="llm_openai", provider_config={})
    assert sorted(clusters) == [[0], [1]]
```

**Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/python -m pytest tests/processors/test_event_clustering.py -v`
Expected: FAIL with `ImportError`/missing `cluster_with_semantic_fallback`

**Step 3: Write minimal implementation**

```python
# backend/app/processors/event_clustering.py
from app.prompts.registry import render_prompt
from app.providers.codex_agent import run_codex_json
from app.providers.llm_chat import run_llm_json
import json


async def semantic_cluster_candidates(
    candidates: list[ClusterCandidate],
    provider_name: str,
    provider_config: dict,
) -> list[list[int]]:
    rows = []
    for idx, item in enumerate(candidates):
        snippet = str(item.raw.content or "").replace("\n", " ")[:80]
        rows.append({"index": idx, "title": item.raw.title, "snippet": snippet, "source_id": item.source_id})
    prompt = render_prompt(
        scope="llm" if provider_name == "llm_openai" else "agent",
        name="cluster",
        variables={"items_json": json.dumps(rows, ensure_ascii=False)},
    )
    output = await (run_llm_json(prompt=prompt, config=provider_config) if provider_name == "llm_openai" else run_codex_json(prompt=prompt, config=provider_config))
    clusters = output.get("clusters", [])
    if not isinstance(clusters, list):
        return []
    valid: list[list[int]] = []
    for group in clusters:
        if not isinstance(group, list):
            continue
        items = sorted({int(i) for i in group if isinstance(i, int) and 0 <= i < len(candidates)})
        if items:
            valid.append(items)
    return valid


async def cluster_with_semantic_fallback(
    candidates: list[ClusterCandidate],
    provider_name: str,
    provider_config: dict,
) -> list[list[int]]:
    rule_clusters = cluster_by_rules(candidates)
    unresolved = [group for group in rule_clusters if len(group) == 1]
    if len(unresolved) <= 1:
        return rule_clusters

    unresolved_indices = [group[0] for group in unresolved]
    unresolved_candidates = [candidates[idx] for idx in unresolved_indices]
    semantic_groups = await semantic_cluster_candidates(unresolved_candidates, provider_name, provider_config)
    if not semantic_groups:
        return rule_clusters

    merged = [group for group in rule_clusters if len(group) > 1]
    used: set[int] = set()
    for group in semantic_groups:
        mapped = sorted({unresolved_indices[idx] for idx in group if 0 <= idx < len(unresolved_indices)})
        if mapped:
            merged.append(mapped)
            used.update(mapped)

    for idx in unresolved_indices:
        if idx not in used:
            merged.append([idx])

    return sorted([sorted(group) for group in merged], key=lambda g: g[0])
```

Add prompts:

```md
# backend/app/prompts/llm/cluster.md
Cluster same real-world events across different sources.
Return strict JSON only: {"clusters": [[int,...], ...]}.
Rules:
- Merge only when clearly same event.
- Prefer precision over recall.
- Do NOT merge same topic but different event.
Input:
$items_json
```

```md
# backend/app/prompts/agent/cluster.md
你是事件聚类助手。请将同一真实事件的条目聚成一组。
只输出 JSON：{"clusters": [[整数序号], ...]}。
规则：宁可不合并，也不要误合并；同主题不同事件不能合并。
输入：
$items_json
```

**Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/python -m pytest tests/processors/test_event_clustering.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/processors/event_clustering.py backend/app/prompts/llm/cluster.md backend/app/prompts/agent/cluster.md backend/tests/processors/test_event_clustering.py
git commit -m "feat: add semantic fallback clustering with prompts"
```

---

### Task 3: Refactor processing pipeline to support global filter + post-cluster enrichment

**Files:**
- Modify: `backend/app/processors/pipeline.py`
- Modify: `backend/app/prompts/agent/filter.md`
- Modify: `backend/app/prompts/llm/filter.md`
- Test: `backend/tests/processors/test_pipeline.py`

**Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_pipeline_supports_filter_and_enrich_stages_separately(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = ProcessingPipeline(routing_profile="codex_mvp_v1")

    raw_items = [RawArticle(external_id="1", title="OpenAI update", url="https://x.com/1", content="AI update")]
    filtered, filter_trace = await pipeline.filter_articles(raw_items)
    assert len(filtered) == 1
    assert filter_trace["stage"] == "filter"

    processed, keywords_trace = await pipeline.enrich_articles(filtered)
    assert len(processed) == 1
    assert keywords_trace["stage"] == "keywords"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/python -m pytest tests/processors/test_pipeline.py::test_pipeline_supports_filter_and_enrich_stages_separately -v`
Expected: FAIL with `AttributeError: 'ProcessingPipeline' object has no attribute 'filter_articles'`

**Step 3: Write minimal implementation**

```python
# backend/app/processors/pipeline.py
async def filter_articles(self, articles: list[RawArticle]) -> tuple[list[RawArticle], dict]:
    filter_output, filter_provider = await self._run_stage_with_retry(
        stage="filter",
        provider_name=self.routing_profile.stages.filter.primary,
        payload={"articles": articles},
    )
    relevant = filter_output.get("articles", [])
    trace = {
        "stage": "filter",
        "provider": filter_provider,
        "model": self._trace_model(filter_provider),
        "input": len(articles),
        "output": len(relevant),
    }
    self.last_stage_trace["filter"] = {k: v for k, v in trace.items() if k != "stage"}
    return relevant, trace


async def enrich_articles(self, articles: list[RawArticle]) -> tuple[list[ProcessedArticle], dict]:
    (
        keywords_list,
        summaries,
        importances,
        details,
        categories,
        event_titles,
        whos,
        whats,
        whens,
        metrics_list,
        availabilities,
        unknowns_list,
        evidences,
    ) = await self._extract_keywords_and_summaries_with_routing(articles)
    processed: list[ProcessedArticle] = []
    for row in zip(
        articles,
        summaries,
        keywords_list,
        importances,
        details,
        categories,
        event_titles,
        whos,
        whats,
        whens,
        metrics_list,
        availabilities,
        unknowns_list,
        evidences,
    ):
        article, summary, keywords, importance, detail, category, event_title, who, what, when, metrics, availability, unknowns, evidence = row
        processed.append(
            ProcessedArticle(
                raw=article,
                event_title=event_title,
                summary=summary,
                keywords=keywords,
                score=1.0,
                importance=importance,
                detail=detail,
                category=category,
                who=who,
                what=what,
                when=when,
                metrics=metrics,
                availability=availability,
                unknowns=unknowns,
                evidence=evidence,
            )
        )
    trace = {
        "stage": "keywords",
        "provider": self.routing_profile.stages.keywords.primary,
        "model": self._trace_model(self.routing_profile.stages.keywords.primary),
        "input": len(articles),
        "output": len(processed),
    }
    return processed, trace


# process() now calls filter_articles() then enrich_articles()
```

Prompt adjustment (remove dedup responsibility from filter prompt):

```md
# backend/app/prompts/agent/filter.md
任务：从以下 AI 新闻条目中筛选出有价值条目。
# 删除“去重”规则行
```

```md
# backend/app/prompts/llm/filter.md
- Remove only obvious noise/non-AI items.
# 删除 deduplicate 规则段
```

**Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/python -m pytest tests/processors/test_pipeline.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/processors/pipeline.py backend/app/prompts/agent/filter.md backend/app/prompts/llm/filter.md backend/tests/processors/test_pipeline.py
git commit -m "refactor: split pipeline into filter and enrich stages"
```

---

### Task 4: Integrate global cross-source clustering into orchestrator pipeline

**Files:**
- Modify: `backend/app/scheduler/orchestrator.py`
- Test: `backend/tests/scheduler/test_orchestrator_e2e.py`

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_orchestrator_clusters_cross_source_duplicates_before_enrichment(
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: two sources produce same event (blog + x)
    # Expect: processed_articles == 1, cluster stage event exists, report event source_count >= 2
    ...
```

Minimum assertions in this test:

```python
assert result["processed_articles"] == 1
assert any(e["stage"] == "cluster" and e["event_type"] == "cluster_completed" for e in events)
assert len(report.metadata_.get("events", [])) == 1
assert report.metadata_["events"][0]["source_count"] >= 2
```

**Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/python -m pytest tests/scheduler/test_orchestrator_e2e.py::test_orchestrator_clusters_cross_source_duplicates_before_enrichment -v`
Expected: FAIL (`processed_articles` still 2 and no `cluster_completed` event)

**Step 3: Write minimal implementation**

```python
# backend/app/scheduler/orchestrator.py (new flow in _run_daily_pipeline)
# 1) Keep collect + window_filter per source as-is.
# 2) Build global candidate list from all sources after window_filter.

all_candidates: list[ClusterCandidate] = []
for source in subscribed_sources:
    filtered_raw, collect_trace, filter_trace = process_inputs[source.id]
    for raw in filtered_raw:
        raw.metadata.setdefault("source_name", source.name)
        raw.metadata.setdefault("source_id", str(source.id))
        all_candidates.append(ClusterCandidate(raw=raw, source_id=str(source.id), source_name=source.name))

# 3) Global filter once
pipeline = ProcessingPipeline(routing_profile=self.runtime_routing_profile.name)
pipeline.set_routing_profile(self.runtime_routing_profile)
pipeline.set_provider_overrides(self.runtime_provider_overrides)
filtered_global, filter_stage_trace = await pipeline.filter_articles([c.raw for c in all_candidates])

# 4) Cross-source clustering
provider_name = self.runtime_routing_profile.stages.filter.primary
provider_config = self._provider_config(provider_name)
clustered = await build_clustered_articles(
    candidates=[c for c in all_candidates if c.raw in filtered_global],
    provider_name=provider_name,
    provider_config=provider_config,
)

await append_task_event(
    db,
    run_id=pipeline_run_id,
    monitor_id=monitor_id,
    task_id=monitor_task_id,
    source_id=None,
    stage="cluster",
    event_type="cluster_completed",
    message="Cross-source clustering completed",
    payload={
        "window_articles": len(all_candidates),
        "filtered_articles": len(filtered_global),
        "clustered_articles": len(clustered),
    },
)

# 5) Enrich clustered primaries only
processed_articles, keywords_trace = await pipeline.enrich_articles([item.raw for item in clustered])

# 6) Group processed by cluster_primary_source_id and persist back into source tasks.
```

**Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/python -m pytest tests/scheduler/test_orchestrator_e2e.py::test_orchestrator_clusters_cross_source_duplicates_before_enrichment -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/scheduler/orchestrator.py backend/tests/scheduler/test_orchestrator_e2e.py
git commit -m "feat: add global cross-source clustering stage in orchestrator"
```

---

### Task 5: Preserve merged provenance in renderer output

**Files:**
- Modify: `backend/app/renderers/daily.py`
- Test: `backend/tests/renderers/test_daily_renderer.py`

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_daily_renderer_uses_cluster_source_metadata_for_source_labels_and_links() -> None:
    raw = RawArticle(
        external_id="cluster-1",
        title="OpenAI 发布 GPT-5",
        url="https://openai.com/blog/gpt-5",
        content="...",
        metadata={
            "source_name": "OpenAI Blog",
            "cluster_source_names": ["OpenAI Blog", "OpenAI X"],
            "links": ["https://openai.com/blog/gpt-5", "https://x.com/OpenAI/status/123"],
            "cluster_size": 2,
        },
    )
    item = ProcessedArticle(raw=raw, summary="...", keywords=["openai"])
    report = await DailyRenderer().render([item], RenderContext(date="2026-03-05"))
    event = report.metadata["events"][0]
    assert event["source_name"] == "OpenAI Blog、OpenAI X"
    assert event["source_count"] == 2
```

**Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/python -m pytest tests/renderers/test_daily_renderer.py::test_daily_renderer_uses_cluster_source_metadata_for_source_labels_and_links -v`
Expected: FAIL (`source_name` still single source)

**Step 3: Write minimal implementation**

```python
# backend/app/renderers/daily.py (_build_event)
metadata = item.raw.metadata if isinstance(item.raw.metadata, dict) else {}
cluster_source_names = metadata.get("cluster_source_names")
if isinstance(cluster_source_names, list):
    names = [str(v).strip() for v in cluster_source_names if str(v).strip()]
    source_name = "、".join(names) if names else source_name

# keep _extract_links behavior by populating metadata["links"] during clustering
```

**Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/python -m pytest tests/renderers/test_daily_renderer.py::test_daily_renderer_uses_cluster_source_metadata_for_source_labels_and_links -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/renderers/daily.py backend/tests/renderers/test_daily_renderer.py
git commit -m "feat: render merged cluster provenance in daily events"
```

---

### Task 6: Add clustering feature flags and defaults

**Files:**
- Modify: `backend/app/config.py`
- Modify: `config.yaml`
- Test: `backend/tests/test_config_cluster_flags.py`

**Step 1: Write failing test**

```python
from app.config import Settings


def test_cluster_settings_defaults_present() -> None:
    settings = Settings()
    assert isinstance(settings.processor_cross_source_cluster_enabled, bool)
    assert isinstance(settings.processor_semantic_cluster_enabled, bool)
    assert settings.processor_semantic_cluster_max_candidates >= 1
```

**Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_config_cluster_flags.py -v`
Expected: FAIL with missing attributes

**Step 3: Write minimal implementation**

```python
# backend/app/config.py
processor_cross_source_cluster_enabled: bool = Field(default=_yaml.get("processor", {}).get("cross_source_cluster_enabled", True))
processor_semantic_cluster_enabled: bool = Field(default=_yaml.get("processor", {}).get("semantic_cluster_enabled", True))
processor_semantic_cluster_max_candidates: int = Field(default=_yaml.get("processor", {}).get("semantic_cluster_max_candidates", 50))
```

```yaml
# config.yaml
processor:
  score_threshold: 0.4
  dedup_window_hours: 72
  cross_source_cluster_enabled: true
  semantic_cluster_enabled: true
  semantic_cluster_max_candidates: 50
```

Use these flags in orchestrator clustering branch:

```python
if not settings.processor_cross_source_cluster_enabled:
    clustered = [{"raw": raw} for raw in filtered_global]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_config_cluster_flags.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/config.py config.yaml backend/tests/test_config_cluster_flags.py backend/app/scheduler/orchestrator.py
git commit -m "chore: add configurable cluster feature flags"
```

---

### Task 7: End-to-end verification, docs, and final hardening

**Files:**
- Modify: `docs/development/architecture.mdx`
- Modify: `docs/development/collector-plugin.mdx` (add provenance guidance)
- Modify: `backend/tests/scheduler/test_task_events_file_log.py` (cluster stage log assertion)

**Step 1: Write failing regression tests/docs assertions**

```python
@pytest.mark.asyncio
async def test_task_event_log_contains_cluster_stage_payload(...):
    ...
    assert any('stage="cluster"' in line or 'stage=cluster' in line for line in lines)
```

**Step 2: Run targeted tests to verify failure**

Run: `cd backend && ../.venv/bin/python -m pytest tests/scheduler/test_task_events_file_log.py::test_task_event_log_contains_cluster_stage_payload -v`
Expected: FAIL (cluster stage not asserted/absent)

**Step 3: Implement docs + hardening**

Update docs with final pipeline:

```md
1) collect
2) window_filter
3) filter
4) cross_source_cluster
5) keywords_enrichment
6) persist
7) render
8) report_tldr_enhance
9) publish
```

Add hardening checks:

```python
# event_clustering.py
# - reject semantic groups with duplicated members
# - reject groups that include out-of-range indices
# - cap semantic input rows by settings.processor_semantic_cluster_max_candidates
```

**Step 4: Run full verification suite**

Run:

```bash
cd backend && ../.venv/bin/python -m pytest \
  tests/processors/test_event_clustering.py \
  tests/processors/test_pipeline.py \
  tests/scheduler/test_orchestrator_e2e.py \
  tests/renderers/test_daily_renderer.py \
  tests/scheduler/test_task_events_file_log.py \
  tests/test_config_cluster_flags.py -v
```

Expected: PASS all selected tests

Then run broader monitor-related suite:

```bash
cd backend && ../.venv/bin/python -m pytest tests/scheduler -q
```

Expected: PASS (or only known unrelated failures, must be documented)

**Step 5: Commit**

```bash
git add docs/development/architecture.mdx docs/development/collector-plugin.mdx backend/tests/scheduler/test_task_events_file_log.py backend/app/processors/event_clustering.py backend/app/scheduler/orchestrator.py backend/app/processors/pipeline.py backend/app/renderers/daily.py

git commit -m "feat: land cross-source event clustering end-to-end"
```

---

## Rollout Checklist

1. 在 staging 开启 `cross_source_cluster_enabled=true`，观察 3 天。
2. 核对指标：
   - `window_articles`
   - `filtered_articles`
   - `clustered_articles`
   - `cluster_reduction_ratio`
3. 抽样审阅 20 份日报，误合并率目标 < 3%。
4. 如误合并偏高：先关闭 `semantic_cluster_enabled`，保留规则聚类。

## Acceptance Criteria

- 同一事件（官网 + X）在日报中只出现一次，且来源列表包含两者。
- 同主题但不同事件不被错误合并。
- `run events` 中新增 `cluster_completed`，包含聚类前后数量。
- 既有 collect/window/process/report/publish 行为不回归。
