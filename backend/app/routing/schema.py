"""Routing profile schema for static provider matrix."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class StageRoute:
    primary: str
    fallback: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PublishRoute:
    targets: list[str] = field(default_factory=list)
    on_failure: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class RoutingStages:
    collect: StageRoute
    filter: StageRoute
    keywords: StageRoute
    report: StageRoute
    publish: PublishRoute
    global_summary: StageRoute | None = None


@dataclass(slots=True)
class RoutingProfile:
    name: str
    stages: RoutingStages
    providers: dict[str, dict] = field(default_factory=dict)
