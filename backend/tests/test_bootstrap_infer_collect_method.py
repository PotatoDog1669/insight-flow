from __future__ import annotations

from app.bootstrap import _infer_collect_method


def test_infer_collect_method_maps_twitter_snaplytics_strategy() -> None:
    method, config = _infer_collect_method(
        {
            "key": "openai_x",
            "strategy": "twitter_snaplytics_profile",
            "urls": ["https://x.com/OpenAI"],
            "collect_config": {"max_items": 40, "include_retweets": False},
        }
    )

    assert method == "twitter_snaplytics"
    assert config.get("username") == "OpenAI"
    assert config.get("max_items") == 40
    assert config.get("include_retweets") is False


def test_infer_collect_method_keeps_explicit_username_for_twitter_snaplytics() -> None:
    method, config = _infer_collect_method(
        {
            "key": "xai_x",
            "strategy": "twitter_snaplytics",
            "urls": ["https://x.com/xai"],
            "collect_config": {"username": "xai", "max_items": 20},
        }
    )

    assert method == "twitter_snaplytics"
    assert config.get("username") == "xai"
    assert config.get("max_items") == 20


def test_infer_collect_method_keeps_usernames_list_for_twitter_snaplytics() -> None:
    method, config = _infer_collect_method(
        {
            "key": "x_social",
            "strategy": "twitter_snaplytics",
            "urls": ["https://x.com"],
            "collect_config": {"usernames": ["OpenAI", "AnthropicAI"], "max_items": 50},
        }
    )

    assert method == "twitter_snaplytics"
    assert config.get("usernames") == ["OpenAI", "AnthropicAI"]
    assert config.get("max_items") == 50


def test_infer_collect_method_uses_blog_scraper_for_site_profile_strategy() -> None:
    method, config = _infer_collect_method(
        {
            "key": "cursor",
            "strategy": "site_profile_scraper",
            "urls": ["https://cursor.com/blog"],
        }
    )

    assert method == "blog_scraper"
    assert config.get("site_key") == "cursor"
    assert config.get("max_items") == 20
    assert config.get("fallback_chain") == ["blog_scraper", "deepbrowse"]
