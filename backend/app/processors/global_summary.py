"""Global summary stage helpers."""

from __future__ import annotations

from collections import Counter
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from app.providers.registry import get_provider
from app.routing.schema import StageRoute
from app.providers.errors import ProviderUnavailableError

from app.processors.event_models import GlobalSummary

SummaryRunner = Callable[[dict], Awaitable[tuple[dict, str]]]

if TYPE_CHECKING:
    from app.providers.base import BaseStageProvider

_LEAD_MAP = {
    "模型发布": "今日 AI 主线是模型能力与交付效率同步升级。",
    "产品应用": "今日 AI 主线是产品化落地继续提速。",
    "技术与洞察": "今日 AI 主线是评测与方法论并行演进。",
    "开发生态": "今日 AI 主线是开发工具链进一步完善。",
    "前瞻与传闻": "今日 AI 主线是前瞻信号增多但仍需证据验证。",
    "要闻": "今日 AI 主线是头部事件密集释放。",
    "行业动态": "今日 AI 主线是平台与生态位变化持续放大。",
}
_COMMENT_MAP = {
    "模型发布": "后续更值得关注真实采用速度与单位成本改善。",
    "产品应用": "后续更值得关注流程深度整合与持续留存。",
    "技术与洞察": "后续更值得关注结论在生产环境的可复现性。",
    "前瞻与传闻": "后续更值得关注可验证的官方与代码证据。",
    "开发生态": "后续更值得关注生态兼容性与团队协作效率。",
    "要闻": "后续更值得关注企业侧落地节奏与反馈质量。",
    "行业动态": "后续更值得关注平台策略变化带来的二阶影响。",
}


def build_global_summary_payload(events: list[dict]) -> dict:
    compact: list[dict[str, object]] = []
    for index, item in enumerate(events[:20], start=1):
        compact.append(
            {
                "index": int(item.get("index") or index),
                "category": str(item.get("category") or ""),
                "title": str(item.get("title") or "").strip(),
                "summary": str(item.get("one_line_tldr") or item.get("summary") or "").strip(),
                "detail": str(item.get("detail") or "").strip()[:400],
                "source_name": str(item.get("source_name") or "").strip(),
                "source_count": int(item.get("source_count") or 0),
                "who": str(item.get("who") or "").strip(),
                "what": str(item.get("what") or "").strip(),
                "when": str(item.get("when") or "").strip(),
            }
        )
    return {"events": compact}


def build_global_summary_fallback(events: list[dict]) -> str:
    if not events:
        return ""

    category_counts = Counter(str(item.get("category") or "行业动态") for item in events)
    dominant = category_counts.most_common(1)[0][0]
    lead = _LEAD_MAP.get(dominant, _LEAD_MAP["行业动态"])
    titles = [str(item.get("title") or "").strip() for item in events if str(item.get("title") or "").strip()]
    compact_titles = [_compact_title(title) for title in titles[:2] if _compact_title(title)]
    trend_line = f"代表性动态包括{'、'.join(compact_titles)}。" if compact_titles else "重点仍是验证技术能否稳定落地到真实业务。"
    comment = _COMMENT_MAP.get(dominant, _COMMENT_MAP["行业动态"])
    return f"{lead}{trend_line}{comment}"


async def run_global_summary_stage(
    *,
    events: list[dict],
    runner: SummaryRunner | None = None,
) -> GlobalSummary:
    payload = build_global_summary_payload(events)
    fallback = build_global_summary_fallback(payload["events"])
    metrics = _prompt_metrics(payload, fallback)
    if not payload["events"]:
        return GlobalSummary(global_tldr="", provider="fallback", fallback_used=True, prompt_metrics=metrics)
    if runner is None:
        return GlobalSummary(global_tldr=fallback, provider="fallback", fallback_used=True, prompt_metrics=metrics)

    try:
        output, provider = await runner(payload)
    except ProviderUnavailableError:
        raise
    except Exception:
        return GlobalSummary(global_tldr=fallback, provider="fallback", fallback_used=True, prompt_metrics=metrics)

    generated = str(output.get("global_tldr") or "").strip()
    if not generated:
        return GlobalSummary(global_tldr=fallback, provider="fallback", fallback_used=True, prompt_metrics=metrics)

    provider_metrics = output.get("summary_metrics")
    merged_metrics = {**metrics, "output_chars": len(generated)}
    if isinstance(provider_metrics, dict):
        merged_metrics.update({str(key): value for key, value in provider_metrics.items()})

    return GlobalSummary(
        global_tldr=generated,
        provider=provider,
        fallback_used=False,
        prompt_metrics=merged_metrics,
    )


def _compact_title(title: str) -> str:
    cleaned = str(title or "").strip().rstrip("。！？!?")
    if len(cleaned) <= 18:
        return cleaned
    return cleaned[:18].rstrip() + "…"


def _prompt_metrics(payload: dict, text: str) -> dict[str, int | bool]:
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    input_chars = sum(
        len(str(item.get("title") or "")) + len(str(item.get("summary") or "")) + len(str(item.get("detail") or ""))
        for item in events
        if isinstance(item, dict)
    )
    return {
        "input_event_count": len(events),
        "input_chars": input_chars,
        "output_chars": len(text),
    }


def _merge_provider_config(
    *,
    provider_name: str,
    profile_config: dict,
    provider_overrides: dict[str, dict],
) -> dict:
    merged = dict(profile_config) if isinstance(profile_config, dict) else {}
    override = provider_overrides.get(provider_name)
    if isinstance(override, dict):
        merged.update(override)
    return merged


def _max_retry(config: dict) -> int:
    raw = config.get("max_retry", 0) if isinstance(config, dict) else 0
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return 0


async def run_global_summary_with_retry(
    *,
    route: StageRoute,
    providers: dict[str, dict],
    provider_overrides: dict[str, dict],
    payload: dict,
    provider_getter: Callable[..., BaseStageProvider] = get_provider,
) -> tuple[dict, str]:
    provider_chain = [name for name in [route.primary, *(route.fallback or [])] if str(name or "").strip()]
    last_exc: Exception | None = None
    for provider_name in provider_chain:
        config = _merge_provider_config(
            provider_name=provider_name,
            profile_config=providers.get(provider_name, {}),
            provider_overrides=provider_overrides,
        )
        provider = provider_getter(stage="global_summary", name=provider_name)
        for _ in range(_max_retry(config) + 1):
            try:
                result = await provider.run(payload=payload, config=config)
                return result, provider_name
            except ProviderUnavailableError as exc:
                if provider_name == "llm_openai" and not exc.stage:
                    exc.stage = "global_summary"
                if provider_name == "llm_openai" or exc.provider == "llm_openai":
                    raise
                last_exc = exc
                break
            except Exception as exc:
                last_exc = exc
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("global_summary stage has no available provider")
