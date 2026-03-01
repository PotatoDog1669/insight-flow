"""智能打分器"""


class Scorer:
    IMPACT_TERMS = {
        "release",
        "launch",
        "benchmark",
        "reasoning",
        "agent",
        "open source",
        "paper",
        "模型",
        "发布",
        "开源",
        "推理",
        "论文",
    }

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def score_batch(self, articles: list) -> list[float]:
        """批量打分 (0.0~1.0)"""
        return [self._score_one(article) for article in articles]

    def _score_one(self, article) -> float:
        text = f"{getattr(article, 'title', '')} {getattr(article, 'content', '')}".lower()
        score = 0.2
        if any(term in text for term in self.IMPACT_TERMS):
            score += 0.3
        length_score = min(len(text) / 2000.0, 0.35)
        score += length_score
        return round(min(max(score, 0.0), 1.0), 3)
