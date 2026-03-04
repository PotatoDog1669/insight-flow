"""Sink registry with routing aliases."""

from __future__ import annotations

from app.sinks.base import BaseSink
from app.sinks.database import DatabaseSink
from app.sinks.feishu import FeishuSink
from app.sinks.notion import NotionSink
from app.sinks.obsidian import ObsidianSink
from app.sinks.rss import RssSink

_ALIASES = {
    "database": "database",
    "notion": "notion",
    "notion_api": "notion",
    "notion_mcp": "notion",
    "obsidian": "obsidian",
    "obsidian_rest": "obsidian",
    "obsidian_file": "obsidian",
    "rss": "rss",
    "rss_feed": "rss",
    "feishu": "feishu",
}

_FACTORIES = {
    "database": DatabaseSink,
    "notion": NotionSink,
    "obsidian": ObsidianSink,
    "rss": RssSink,
    "feishu": FeishuSink,
}


def normalize_sink_name(name: str) -> str:
    return _ALIASES.get(name, name)


def get_sink(name: str) -> BaseSink:
    normalized = normalize_sink_name(name)
    try:
        return _FACTORIES[normalized]()
    except KeyError as exc:
        available = sorted(_FACTORIES.keys())
        raise KeyError(f"Unknown sink: {name} (normalized={normalized}, available={available})") from exc
