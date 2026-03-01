"""AI 初筛 — 剔除与 AI 无关或无报道价值的内容"""


class AIFilter:
    AI_TERMS = {
        "ai",
        "llm",
        "agent",
        "model",
        "transformer",
        "machine learning",
        "deep learning",
        "openai",
        "anthropic",
        "huggingface",
        "inference",
        "reasoning",
        "智能",
        "模型",
        "大模型",
        "推理",
        "机器学习",
        "深度学习",
    }

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def filter_batch(self, articles: list) -> list:
        """批量过滤，返回有价值的文章"""
        kept = []
        for article in articles:
            content = f"{getattr(article, 'title', '')}\n{getattr(article, 'content', '')}".lower()
            if any(term in content for term in self.AI_TERMS):
                kept.append(article)
        return kept
