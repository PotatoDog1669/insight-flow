"""site_profile 加载与校验。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROFILE_DIR = Path(__file__).resolve().parent / "site_profiles"


def load_site_profile(site_key: str) -> dict[str, Any]:
    path = PROFILE_DIR / f"{site_key}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"site_profile not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        profile = yaml.safe_load(fh) or {}
    validate_site_profile(profile)
    return profile


def validate_site_profile(profile: dict[str, Any]) -> None:
    if not isinstance(profile, dict):
        raise ValueError("site_profile must be a dict")
    if not profile.get("site_key"):
        raise ValueError("site_profile.site_key is required")
    start_urls = profile.get("start_urls")
    if not isinstance(start_urls, list) or not start_urls:
        raise ValueError("site_profile.start_urls must be a non-empty list")
    list_page = profile.get("list_page")
    if not isinstance(list_page, dict) or not list_page.get("item_selector"):
        raise ValueError("site_profile.list_page.item_selector is required")
    detail_page = profile.get("detail_page")
    if not isinstance(detail_page, dict) or not detail_page.get("content_selector"):
        raise ValueError("site_profile.detail_page.content_selector is required")
