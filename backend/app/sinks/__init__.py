"""知识存储/落盘层"""

from app.sinks.base import BaseSink, PublishResult
from app.sinks.registry import get_sink, normalize_sink_name

__all__ = ["BaseSink", "PublishResult", "get_sink", "normalize_sink_name"]
