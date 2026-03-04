"""Generate default site profiles from source_presets.yaml."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
PRESETS_PATH = ROOT / "app" / "collectors" / "source_presets.yaml"
PROFILE_DIR = ROOT / "app" / "collectors" / "site_profiles"


def origin_of(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""


def build_profile(key: str, urls: list[str]) -> dict:
    primary = urls[0] if urls else ""
    origin = origin_of(primary)
    return {
        "site_key": key,
        "profile_version": "v1",
        "start_urls": [primary] if primary else [],
        "list_page": {
            "item_selector": "a[href*='/blog/'], a[href*='/news/'], a[href*='/research/'], a[href*='/posts/'], a[href*='/article/'], a[href]",
            "url_selector": "",
            "url_attr": "href",
            "title_selector": "",
            "published_selector": "time",
            "published_attr": "datetime",
        },
        "detail_page": {
            "content_selector": "article, main, [role='main'], .post-content, .article-content, .content",
            "remove_selectors": ["script", "style", "nav", "footer", "header", ".share", ".social"],
            "published_selector": "time",
            "published_attr": "datetime",
        },
        "normalization": {
            "url_prefix": origin,
            "min_content_chars": 300,
        },
    }


def main() -> int:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    data = yaml.safe_load(PRESETS_PATH.read_text(encoding="utf-8")) or {}
    sources = data.get("sources", []) if isinstance(data, dict) else []

    written = 0
    skipped = 0
    for source in sources:
        if not isinstance(source, dict):
            continue
        if source.get("priority") != "p0" or not source.get("enabled"):
            continue

        key = str(source.get("key") or "").strip()
        if not key:
            continue

        rss_url = source.get("rss_url")
        strategy = str(source.get("strategy") or "")

        # RSS-only sources skip profile generation.
        if rss_url and strategy == "rss_then_article_fulltext":
            skipped += 1
            continue

        urls = [u for u in (source.get("urls") or []) if isinstance(u, str) and u.strip()]
        if not urls:
            skipped += 1
            continue

        profile_path = PROFILE_DIR / f"{key}.yaml"
        if profile_path.exists():
            skipped += 1
            continue

        profile = build_profile(key, urls)
        profile_path.write_text(yaml.safe_dump(profile, sort_keys=False, allow_unicode=True), encoding="utf-8")
        written += 1

    print(f"generated={written} skipped={skipped} dir={PROFILE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
