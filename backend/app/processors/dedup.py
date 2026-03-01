"""旧闻排除 / 去重"""

from __future__ import annotations

import hashlib


class DedupChecker:
    def __init__(self, dedup_store=None):
        self.dedup_store = dedup_store if dedup_store is not None else set()

    async def check_batch(self, articles: list) -> list[bool]:
        """批量检查是否为旧闻，返回 True 表示是旧闻"""
        seen_in_batch: set[str] = set()
        is_old_list: list[bool] = []

        for article in articles:
            key = self._dedup_key(article)
            already_seen = key in seen_in_batch or self._store_contains(key)
            is_old_list.append(already_seen)
            seen_in_batch.add(key)
            self._store_add(key)
        return is_old_list

    def _dedup_key(self, article) -> str:
        title = str(getattr(article, "title", "") or "").strip().lower()
        url = str(getattr(article, "url", "") or "").strip().lower()
        external_id = str(getattr(article, "external_id", "") or "").strip().lower()
        if title:
            seed = f"title:{title}"
        elif url:
            seed = f"url:{url}"
        else:
            seed = f"external:{external_id}"
        return hashlib.sha256(str(seed).strip().lower().encode("utf-8")).hexdigest()

    def _store_contains(self, key: str) -> bool:
        if hasattr(self.dedup_store, "__contains__"):
            return key in self.dedup_store
        if hasattr(self.dedup_store, "exists"):
            return bool(self.dedup_store.exists(key))
        return False

    def _store_add(self, key: str) -> None:
        if hasattr(self.dedup_store, "add"):
            self.dedup_store.add(key)
