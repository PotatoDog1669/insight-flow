"""Collector 注册表（插件化管理）"""

from app.collectors.base import BaseCollector

_REGISTRY: dict[str, type[BaseCollector]] = {}


def register(name: str):
    """装饰器：注册 Collector"""

    def wrapper(cls: type[BaseCollector]):
        _REGISTRY[name] = cls
        return cls

    return wrapper


def get_collector(name: str) -> BaseCollector:
    """获取已注册的 Collector 实例"""
    if name not in _REGISTRY:
        raise KeyError(f"Collector '{name}' not found. Available: {list(_REGISTRY.keys())}")
    return _REGISTRY[name]()


def list_collectors() -> list[str]:
    """列出所有已注册的 Collector 名称"""
    return list(_REGISTRY.keys())
