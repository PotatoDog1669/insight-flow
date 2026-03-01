"""信息加工流水线编排"""

import asyncio
from dataclasses import dataclass, field

from app.collectors.base import RawArticle
from app.config import settings
from app.processors.dedup import DedupChecker
from app.processors.filter import AIFilter
from app.processors.keyword_extractor import KeywordExtractor
from app.processors.scorer import Scorer
from app.processors.summarizer import Summarizer


@dataclass
class ProcessedArticle:
    """加工后的文章"""

    raw: RawArticle
    summary: str = ""
    keywords: list[str] = field(default_factory=list)
    score: float = 0.0


class ProcessingPipeline:
    """信息加工流水线：初筛 → 并行加工 → 输出到信息池"""

    def __init__(self, llm_client=None, dedup_store=None, score_threshold: float | None = None):
        self.llm_client = llm_client
        self.dedup_store = dedup_store
        self.score_threshold = score_threshold if score_threshold is not None else settings.processor_score_threshold
        self.filter = AIFilter(llm_client)
        self.summarizer = Summarizer(llm_client)
        self.keyword_extractor = KeywordExtractor(llm_client)
        self.dedup = DedupChecker(dedup_store)
        self.scorer = Scorer(llm_client)

    async def process(self, articles: list[RawArticle]) -> list[ProcessedArticle]:
        """执行完整加工流水线"""
        if not articles:
            return []

        # Step 1: AI 初筛
        relevant = await self.filter.filter_batch(articles)
        if not relevant:
            return []

        # Step 2: 去重（含历史去重）
        dedup_flags = await self.dedup.check_batch(relevant)
        fresh_articles = [article for article, is_old in zip(relevant, dedup_flags) if not is_old]
        if not fresh_articles:
            return []

        # Step 3: 并行加工（摘要/关键词/评分）
        summaries, keywords_list, scores = await asyncio.gather(
            self.summarizer.summarize_batch(fresh_articles),
            self.keyword_extractor.extract_batch(fresh_articles),
            self.scorer.score_batch(fresh_articles),
        )

        processed: list[ProcessedArticle] = []
        for article, summary, keywords, score in zip(fresh_articles, summaries, keywords_list, scores):
            if score < self.score_threshold:
                continue
            processed.append(
                ProcessedArticle(
                    raw=article,
                    summary=summary,
                    keywords=keywords,
                    score=score,
                )
            )

        processed.sort(key=lambda item: item.score, reverse=True)
        return processed
