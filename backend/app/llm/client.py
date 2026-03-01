"""统一 LLM Client — 基于 litellm 适配多模型"""

import structlog

from app.config import settings

logger = structlog.get_logger()


class LLMClient:
    """统一 LLM 调用封装"""

    def __init__(
        self,
        primary_model: str | None = None,
        fallback_model: str | None = None,
    ):
        self.primary_model = primary_model or settings.llm_primary_model
        self.fallback_model = fallback_model or settings.llm_fallback_model

    async def complete(self, prompt: str, **kwargs) -> str:
        """调用 LLM 完成一次生成，失败时自动降级"""
        import litellm

        try:
            response = await litellm.acompletion(
                model=self.primary_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get("max_tokens", settings.llm_max_tokens),
                temperature=kwargs.get("temperature", settings.llm_temperature),
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.warning("llm_primary_failed", model=self.primary_model, error=str(e))
            response = await litellm.acompletion(
                model=self.fallback_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get("max_tokens", settings.llm_max_tokens),
                temperature=kwargs.get("temperature", settings.llm_temperature),
            )
            return response.choices[0].message.content or ""

    async def complete_batch(self, prompts: list[str], **kwargs) -> list[str]:
        """批量调用 LLM"""
        import asyncio

        tasks = [self.complete(p, **kwargs) for p in prompts]
        return await asyncio.gather(*tasks)
