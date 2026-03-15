"""
配置管理 — 支持 环境变量 > YAML 配置文件 > 代码默认值 三层覆盖
"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_yaml_config() -> dict:
    """加载 config.yaml"""
    config_path = PROJECT_ROOT / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


_yaml = _load_yaml_config()


class Settings(BaseSettings):
    """应用配置 — 环境变量自动覆盖同名字段"""

    # App
    app_name: str = Field(default=_yaml.get("app", {}).get("name", "LexDeepResearch"))
    app_debug: bool = Field(default=_yaml.get("app", {}).get("debug", False))
    app_log_level: str = Field(default=_yaml.get("app", {}).get("log_level", "INFO"))

    # Database
    database_url: str = Field(
        default=_yaml.get("database", {}).get("url", "postgresql+asyncpg://lex:password@localhost:5432/lexdeepresearch")
    )
    database_pool_size: int = Field(default=_yaml.get("database", {}).get("pool_size", 10))

    # Redis
    redis_url: str = Field(default=_yaml.get("redis", {}).get("url", "redis://localhost:6379/0"))

    # LLM
    openai_api_key: str = Field(default="")
    llm_primary_model: str = Field(default=_yaml.get("llm", {}).get("primary_model", "gpt-4o-mini"))
    llm_fallback_model: str = Field(default=_yaml.get("llm", {}).get("fallback_model", "deepseek-chat"))
    llm_max_tokens: int = Field(default=_yaml.get("llm", {}).get("max_tokens", 2048))
    llm_temperature: float = Field(default=_yaml.get("llm", {}).get("temperature", 0.3))
    codex_api_key: str = Field(default="")
    codex_base_url: str = Field(default="https://api.openai.com/v1")
    codex_model: str = Field(default="gpt-5-codex")
    codex_timeout_sec: int = Field(default=120)

    # Scheduler
    daily_collect_time: str = Field(default=_yaml.get("scheduler", {}).get("daily_collect_time", "06:30"))
    weekly_report_day: str = Field(default=_yaml.get("scheduler", {}).get("weekly_report_day", "sunday"))
    weekly_report_time: str = Field(default=_yaml.get("scheduler", {}).get("weekly_report_time", "20:00"))

    # Collector
    collector_max_concurrency: int = Field(default=_yaml.get("collector", {}).get("max_concurrency", 5))
    collector_deepbrowse_concurrency: int = Field(default=_yaml.get("collector", {}).get("deepbrowse_concurrency", 2))
    collector_timeout_seconds: int = Field(default=_yaml.get("collector", {}).get("timeout_seconds", 60))
    collector_retry_max_attempts: int = Field(default=_yaml.get("collector", {}).get("retry_max_attempts", 3))

    # Browser
    browser_provider: str = Field(default=_yaml.get("browser", {}).get("provider", "local"))
    browser_headless: bool = Field(default=_yaml.get("browser", {}).get("local", {}).get("headless", True))
    cloud_cdp_endpoint: str = Field(
        default=_yaml.get("browser", {}).get("cloud", {}).get("cdp_endpoint", "ws://cloud-browser:3000")
    )

    # Processor
    processor_score_threshold: float = Field(default=_yaml.get("processor", {}).get("score_threshold", 0.4))
    processor_dedup_window_hours: int = Field(default=_yaml.get("processor", {}).get("dedup_window_hours", 72))

    # Notion
    notion_api_key: str = Field(default="")
    notion_database_id: str = Field(default=_yaml.get("sink", {}).get("notion", {}).get("database_id", ""))
    notion_parent_page_id: str = Field(default=_yaml.get("sink", {}).get("notion", {}).get("parent_page_id", ""))

    # Obsidian
    obsidian_vault_path: str = Field(default=_yaml.get("sink", {}).get("obsidian", {}).get("vault_path", ""))

    # Routing
    routing_default_profile: str = Field(default=_yaml.get("routing", {}).get("default_profile", "stable_v1"))

    # Research agents
    research_default_agent: str = Field(default=_yaml.get("research", {}).get("default_agent", "deerflow_embedded"))
    research_agents: dict = Field(default=_yaml.get("research", {}).get("agents", {}))

    model_config = {"env_file": str(PROJECT_ROOT / ".env"), "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
