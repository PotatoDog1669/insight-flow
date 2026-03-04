"""信息加工流水线编排"""
from dataclasses import dataclass, field

from app.collectors.base import RawArticle
from app.config import settings
from app.providers.registry import get_provider
from app.routing.loader import load_routing_profile


@dataclass
class ProcessedArticle:
    """加工后的文章"""

    raw: RawArticle
    summary: str = ""
    keywords: list[str] = field(default_factory=list)
    score: float = 1.0
    importance: str = "normal"
    detail: str = ""


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
        self.last_stage_trace: dict[str, dict] = {}

    async def process(self, articles: list[RawArticle]) -> list[ProcessedArticle]:
        """执行完整加工流水线"""
        # Reset per-run trace to avoid leaking stage metrics from previous source.
        self.last_stage_trace = {}
        if not articles:
            return []

        # Step 1: 初筛（静态路由）
        filter_output, filter_provider = await self._run_stage_with_retry(
            stage="filter",
            provider_name=self.routing_profile.stages.filter.primary,
            payload={"articles": articles},
        )
        relevant = filter_output.get("articles", [])
        self.last_stage_trace["filter"] = {"provider": filter_provider, "input": len(articles), "output": len(relevant)}
        if not relevant:
            return []

        # Step 2: 加工（单次会话提取关键词+摘要+重要性+详情）
        # 去重由 filter 阶段的 AI 统一处理。
        keywords_list, summaries, importances, details = await self._extract_keywords_and_summaries_with_routing(relevant)
        self.last_stage_trace["summarizer"] = {
            "provider": self.routing_profile.stages.keywords.primary,
            "input": len(relevant),
            "output": len(summaries),
        }

        processed: list[ProcessedArticle] = []
        for article, summary, keywords, importance, detail in zip(relevant, summaries, keywords_list, importances, details):
            processed.append(
                ProcessedArticle(
                    raw=article,
                    summary=summary,
                    keywords=keywords,
                    score=1.0,
                    importance=importance,
                    detail=detail,
                )
            )

        return processed

    async def _extract_keywords_and_summaries_with_routing(self, articles: list[RawArticle]) -> tuple[list[list[str]], list[str], list[str], list[str]]:
        route = self.routing_profile.stages.keywords
        all_keywords: list[list[str]] = []
        all_summaries: list[str] = []
        all_importances: list[str] = []
        all_details: list[str] = []
        for article in articles:
            output, _ = await self._run_stage_with_retry(
                stage="keywords",
                provider_name=route.primary,
                payload={"article": article},
            )
            all_keywords.append(output.get("keywords", []))
            summary = str(output.get("summary") or "").strip()
            if not summary:
                raise ValueError("Missing summary from keywords stage output")
            all_summaries.append(summary)
            all_importances.append(str(output.get("importance") or "normal").strip().lower())
            all_details.append(str(output.get("detail") or "").strip())
        self.last_stage_trace["keywords"] = {
            "provider": route.primary,
            "providers": [route.primary],
            "input": len(articles),
            "output": len(all_keywords),
        }
        return all_keywords, all_summaries, all_importances, all_details

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

    @staticmethod
    def _max_retry(provider_config: dict) -> int:
        raw = provider_config.get("max_retry", 0) if isinstance(provider_config, dict) else 0
        try:
            value = int(raw)
        except Exception:
            value = 0
        return max(value, 0)
