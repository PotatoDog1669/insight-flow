"""关键词提取器"""

from __future__ import annotations

import re
from collections import Counter


class KeywordExtractor:
    STOPWORDS = {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "into",
        "about",
        "today",
        "发布",
        "一个",
        "我们",
        "以及",
        "通过",
    }

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def extract_batch(self, articles: list) -> list[list[str]]:
        """批量提取关键词"""
        return [self._extract_one(article) for article in articles]

    def _extract_one(self, article) -> list[str]:
        text = f"{getattr(article, 'title', '')} {getattr(article, 'content', '')}"
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9+_.#-]{2,}|[\u4e00-\u9fff]{2,}", text)
        counter: Counter[str] = Counter()
        for token in tokens:
            normalized = token.strip().lower()
            if normalized in self.STOPWORDS:
                continue
            counter[normalized] += 1
        keywords = [word for word, _ in counter.most_common(5)]
        return keywords
