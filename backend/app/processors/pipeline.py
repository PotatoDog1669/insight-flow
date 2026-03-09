"""信息加工流水线编排"""
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeVar

from app.collectors.base import RawArticle
from app.config import settings
from app.processors.candidate_cluster import build_candidate_clusters
from app.processors.content_quality_gate import apply_content_quality_gate
from app.processors.event_extract import build_event_extraction_inputs, build_processed_event
from app.processors.event_models import CandidateCluster, EventExtractionInput, ProcessedEvent
from app.providers.registry import get_provider
from app.routing.loader import load_routing_profile
from app.routing.schema import RoutingProfile

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


@dataclass
class ProcessedArticle:
    """加工后的文章"""

    raw: RawArticle
    event_title: str = ""
    summary: str = ""
    keywords: list[str] = field(default_factory=list)
    score: float = 1.0
    importance: str = "normal"
    detail: str = ""
    category: str | None = None
    who: str = ""
    what: str = ""
    when: str = ""
    metrics: list[str] = field(default_factory=list)
    availability: str = ""
    unknowns: str = ""
    evidence: str = ""
    detail_mode: str = "full"


class ProcessingPipeline:
    """信息加工流水线：初筛 → 并行加工 → 输出到信息池"""

    def __init__(
        self,
        llm_client=None,
        dedup_store=None,
        score_threshold: float | None = None,
        routing_profile: str | None = None,
        provider_overrides: dict[str, dict] | None = None,
    ):
        self.llm_client = llm_client
        self.dedup_store = dedup_store
        # Kept for backward compatibility, but score-based filtering is disabled.
        self.score_threshold = score_threshold if score_threshold is not None else settings.processor_score_threshold
        self.routing_profile_name = routing_profile or settings.routing_default_profile
        self.routing_profile = load_routing_profile(self.routing_profile_name)
        self.provider_overrides = provider_overrides or {}
        self.stage_concurrency = 1
        self.last_stage_trace: dict[str, dict] = {}

    async def process(self, articles: list[RawArticle]) -> list[ProcessedArticle]:
        """执行完整加工流水线"""
        # Reset per-run trace to avoid leaking stage metrics from previous source.
        self.last_stage_trace = {}
        if not articles:
            return []

        relevant, _ = await self.run_filter_stage(articles)
        if not relevant:
            return []

        await self.run_candidate_cluster_stage(relevant)
        processed, _ = await self.run_keywords_stage(relevant)
        return processed

    async def run_candidate_cluster_stage(self, articles: list[RawArticle]) -> tuple[list, dict]:
        """运行候选事件聚类，并记录弱规则召回 trace。"""
        clusters = build_candidate_clusters(articles)
        trace = {
            "provider": "candidate_rule",
            "input": len(articles),
            "output": len(clusters),
            "largest_cluster": max((len(cluster.articles) for cluster in clusters), default=0),
        }
        self.last_stage_trace["candidate_cluster"] = trace
        return clusters, trace

    async def run_event_extract_stage(self, clusters: list[CandidateCluster]) -> tuple[list[ProcessedEvent], dict]:
        """运行事件级提炼，基于 cluster 输入复用现有 keywords routing。"""
        route = self.routing_profile.stages.keywords
        event_inputs = build_event_extraction_inputs(clusters)

        async def _extract_event(event_input: EventExtractionInput) -> ProcessedEvent:
            output, _ = await self._run_stage_with_retry(
                stage="keywords",
                provider_name=route.primary,
                payload={"event_input": event_input},
            )

            return build_processed_event(event_input, output)

        events = await self._run_with_stage_concurrency(event_inputs, _extract_event)

        trace = {
            "provider": route.primary,
            "model": self._trace_model(route.primary),
            "input": len(clusters),
            "output": len(events),
            "clustered_articles": sum(len(cluster.articles) for cluster in clusters),
            "stage_concurrency": self.stage_concurrency,
        }
        self.last_stage_trace["event_extract"] = trace
        return events, trace

    async def run_filter_stage(self, articles: list[RawArticle]) -> tuple[list[RawArticle], dict]:
        """运行 filter stage 并返回保留文章。"""
        filter_output, filter_provider = await self._run_stage_with_retry(
            stage="filter",
            provider_name=self.routing_profile.stages.filter.primary,
            payload={"articles": articles},
        )
        relevant = filter_output.get("articles", [])
        trace = {
            "provider": filter_provider,
            "model": self._trace_model(filter_provider),
            "input": len(articles),
            "output": len(relevant),
        }
        self.last_stage_trace["filter"] = trace
        return relevant, trace

    async def run_keywords_stage(self, articles: list[RawArticle]) -> tuple[list[ProcessedArticle], dict]:
        """运行 keywords stage 并返回加工结果。"""
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
        for (
            article,
            summary,
            keywords,
            importance,
            detail,
            category,
            event_title,
            who,
            what,
            when,
            metrics,
            availability,
            unknowns,
            evidence,
        ) in zip(
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
            processed.append(
                apply_content_quality_gate(
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
            )

        trace = {
            "provider": self.routing_profile.stages.keywords.primary,
            "model": self._trace_model(self.routing_profile.stages.keywords.primary),
            "input": len(articles),
            "output": len(summaries),
            "compact_output": len([item for item in processed if item.detail_mode == "compact"]),
            "stage_concurrency": self.stage_concurrency,
        }
        self.last_stage_trace["summarizer"] = trace
        return processed, trace

    async def _extract_keywords_and_summaries_with_routing(
        self, articles: list[RawArticle]
    ) -> tuple[
        list[list[str]],
        list[str],
        list[str],
        list[str],
        list[str | None],
        list[str],
        list[str],
        list[str],
        list[str],
        list[list[str]],
        list[str],
        list[str],
        list[str],
    ]:
        route = self.routing_profile.stages.keywords
        all_keywords: list[list[str]] = []
        all_summaries: list[str] = []
        all_importances: list[str] = []
        all_details: list[str] = []
        all_categories: list[str | None] = []
        all_event_titles: list[str] = []
        all_whos: list[str] = []
        all_whats: list[str] = []
        all_whens: list[str] = []
        all_metrics: list[list[str]] = []
        all_availabilities: list[str] = []
        all_unknowns: list[str] = []
        all_evidences: list[str] = []

        async def _extract_article(article: RawArticle) -> tuple[
            list[str],
            str,
            str,
            str,
            str | None,
            str,
            str,
            str,
            str,
            list[str],
            str,
            str,
            str,
        ]:
            output, _ = await self._run_stage_with_retry(
                stage="keywords",
                provider_name=route.primary,
                payload={"article": article},
            )

            keywords = output.get("keywords", [])
            summary = str(output.get("summary") or "").strip()
            if not summary:
                raise ValueError("Missing summary from keywords stage output")
            importance = str(output.get("importance") or "normal").strip().lower()
            detail = str(output.get("detail") or "").strip()
            category = output.get("category")
            normalized_category = str(category).strip() if category else None
            event_title = str(output.get("event_title") or "").strip()
            who = str(output.get("who") or "").strip()
            what = str(output.get("what") or "").strip()
            when = str(output.get("when") or "").strip()

            raw_metrics = output.get("metrics")
            metrics: list[str] = []
            if isinstance(raw_metrics, list):
                for item in raw_metrics:
                    metric = str(item or "").strip()
                    if not metric:
                        continue
                    if metric in metrics:
                        continue
                    metrics.append(metric)
                    if len(metrics) >= 12:
                        break
            return (
                keywords,
                summary,
                importance,
                detail,
                normalized_category,
                event_title,
                who,
                what,
                when,
                metrics,
                str(output.get("availability") or "").strip(),
                str(output.get("unknowns") or "").strip(),
                str(output.get("evidence") or "").strip(),
            )

        results = await self._run_with_stage_concurrency(articles, _extract_article)
        for (
            keywords,
            summary,
            importance,
            detail,
            category,
            event_title,
            who,
            what,
            when,
            metrics,
            availability,
            unknowns,
            evidence,
        ) in results:
            all_keywords.append(keywords)
            all_summaries.append(summary)
            all_importances.append(importance)
            all_details.append(detail)
            all_categories.append(category)
            all_event_titles.append(event_title)
            all_whos.append(who)
            all_whats.append(what)
            all_whens.append(when)
            all_metrics.append(metrics)
            all_availabilities.append(availability)
            all_unknowns.append(unknowns)
            all_evidences.append(evidence)

        self.last_stage_trace["keywords"] = {
            "provider": route.primary,
            "model": self._trace_model(route.primary),
            "providers": [route.primary],
            "input": len(articles),
            "output": len(all_keywords),
            "stage_concurrency": self.stage_concurrency,
        }
        return (
            all_keywords,
            all_summaries,
            all_importances,
            all_details,
            all_categories,
            all_event_titles,
            all_whos,
            all_whats,
            all_whens,
            all_metrics,
            all_availabilities,
            all_unknowns,
            all_evidences,
        )

    async def _run_stage_with_retry(self, stage: str, provider_name: str, payload: dict) -> tuple[dict, str]:
        if not provider_name:
            raise RuntimeError(f"Missing provider for stage={stage}")

        provider = get_provider(stage=stage, name=provider_name)
        provider_config = self._provider_config(provider_name)
        max_retry = self._max_retry(provider_config)
        last_exc: Exception | None = None

        for _ in range(max_retry + 1):
            try:
                result = await provider.run(payload=payload, config=provider_config)
                return result, provider_name
            except Exception as exc:  # pragma: no cover - retry guard
                last_exc = exc
                continue

        if last_exc:
            raise last_exc
        raise RuntimeError(f"Provider execution failed for stage={stage}, provider={provider_name}")

    def _provider_config(self, provider_name: str) -> dict:
        raw_config = self.routing_profile.providers.get(provider_name, {})
        merged: dict = dict(raw_config) if isinstance(raw_config, dict) else {}
        override_config = self.provider_overrides.get(provider_name, {})
        if isinstance(override_config, dict):
            merged.update(override_config)
        return merged

    def set_provider_overrides(self, provider_overrides: dict[str, dict]) -> None:
        self.provider_overrides = provider_overrides if isinstance(provider_overrides, dict) else {}

    def set_stage_concurrency(self, stage_concurrency: int) -> None:
        self.stage_concurrency = max(1, int(stage_concurrency))

    def set_routing_profile(self, routing_profile: RoutingProfile | str) -> None:
        if isinstance(routing_profile, str):
            self.routing_profile_name = routing_profile
            self.routing_profile = load_routing_profile(routing_profile)
            return
        self.routing_profile_name = routing_profile.name
        self.routing_profile = routing_profile

    def _trace_model(self, provider_name: str) -> str | None:
        provider_config = self._provider_config(provider_name)
        model = str(provider_config.get("model") or "").strip() if isinstance(provider_config, dict) else ""
        return model or None

    async def _run_with_stage_concurrency(
        self,
        items: list[InputT],
        worker: Callable[[InputT], Awaitable[OutputT]],
    ) -> list[OutputT]:
        if self.stage_concurrency <= 1 or len(items) <= 1:
            return [await worker(item) for item in items]

        semaphore = asyncio.Semaphore(self.stage_concurrency)

        async def _run(item: InputT) -> OutputT:
            async with semaphore:
                return await worker(item)

        return await asyncio.gather(*(_run(item) for item in items))

    @staticmethod
    def _max_retry(provider_config: dict) -> int:
        raw = provider_config.get("max_retry", 0) if isinstance(provider_config, dict) else 0
        try:
            value = int(raw)
        except Exception:
            value = 0
        return max(value, 0)
