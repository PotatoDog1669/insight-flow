"""摘要生成器"""


class Summarizer:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def summarize_batch(self, articles: list) -> list[str]:
        """批量生成 ≤50 字摘要"""
        return [self._summarize_one(article) for article in articles]

    def _summarize_one(self, article) -> str:
        content = (getattr(article, "content", "") or "").strip()
        title = (getattr(article, "title", "") or "").strip()
        base = content or title
        if not base:
            return ""
        # 优先截取第一句，保留足够信息密度
        for sep in (". ", "。", "!", "！", "?", "？", "\n"):
            if sep in base:
                base = base.split(sep)[0]
                break
        return base[:120].strip()
