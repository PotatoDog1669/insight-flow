"""Routing profile loader."""

from __future__ import annotations

from app.config import _yaml
from app.routing.schema import PublishRoute, RoutingProfile, RoutingStages, StageRoute


def _stage(config: dict, default_primary: str, default_fallback: list[str] | None = None) -> StageRoute:
    data = config or {}
    fallback = data.get("fallback", default_fallback or [])
    if not isinstance(fallback, list):
        fallback = [str(fallback)]
    return StageRoute(primary=str(data.get("primary", default_primary)), fallback=[str(item) for item in fallback])


def _publish(config: dict) -> PublishRoute:
    data = config or {}
    targets = data.get("targets", ["database"])
    if not isinstance(targets, list):
        targets = [str(targets)]
    on_failure = data.get("on_failure", {})
    if not isinstance(on_failure, dict):
        on_failure = {}
    return PublishRoute(targets=[str(item) for item in targets], on_failure={str(k): str(v) for k, v in on_failure.items()})


def load_routing_profile(name: str = "stable_v1") -> RoutingProfile:
    routing = _yaml.get("routing", {})
    profiles = routing.get("profiles", {})
    profile_data = profiles.get(name, {})
    stages = profile_data.get("stages", {})
    providers = profile_data.get("providers", {})

    parsed_stages = RoutingStages(
        collect=_stage(stages.get("collect", {}), "rss", ["blog_scraper", "deepbrowse"]),
        filter=_stage(stages.get("filter", {}), "rule", ["llm_openai"]),
        keywords=_stage(stages.get("keywords", {}), "llm_openai", ["rule"]),
        report=_stage(stages.get("report", {}), "llm_openai", []),
        publish=_publish(stages.get("publish", {})),
        global_summary=_stage(stages.get("global_summary", stages.get("report", {})), "llm_openai", []),
    )
    return RoutingProfile(name=name, stages=parsed_stages, providers=providers if isinstance(providers, dict) else {})
