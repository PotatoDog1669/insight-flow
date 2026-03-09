"""Weak candidate clustering for event-centric processing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

from app.collectors.base import RawArticle
from app.processors.event_models import CandidateCluster

MODEL_KEY_PATTERN = re.compile(
    r"\b(gpt|gemini|claude|llama|qwen|mistral|deepseek)(?:[-\s]?\d+(?:\.\d+)*)?\b",
    re.IGNORECASE,
)
TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{1,}", re.IGNORECASE)
GENERIC_TOKENS = {
    "openai",
    "anthropic",
    "google",
    "meta",
    "microsoft",
    "chatgpt",
    "model",
    "models",
    "release",
    "released",
    "launch",
    "update",
    "blog",
    "post",
    "article",
    "source",
    "today",
}
TITLE_GENERIC_TOKENS = GENERIC_TOKENS.union(
    {
        "announcement",
        "announcements",
        "product",
        "products",
        "policy",
        "introducing",
        "introduction",
        "system",
        "card",
        "research",
        "direction",
        "page",
        "official",
        "overview",
        "spotlight",
        "highlights",
        "feb",
        "mar",
        "apr",
        "jan",
        "may",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "nov",
        "dec",
    }
)
MERGE_WINDOW = timedelta(hours=36)
SOURCE_CATEGORY_PRIORITY = {
    "blog": 0,
    "open_source": 1,
    "academic": 2,
    "social": 3,
}


def build_candidate_clusters(articles: list[RawArticle]) -> list[CandidateCluster]:
    clusters: list[CandidateCluster] = []
    for article in articles:
        target = _find_target_cluster(clusters, article)
        if target is None:
            clusters.append(_create_cluster(article=article, index=len(clusters) + 1))
            continue
        _append_article(target, article)
    return clusters


def select_primary_article(cluster: CandidateCluster) -> RawArticle:
    return sorted(cluster.articles, key=_article_priority)[0]


def _find_target_cluster(clusters: list[CandidateCluster], article: RawArticle) -> CandidateCluster | None:
    for cluster in clusters:
        if any(_should_group(existing, article) for existing in cluster.articles):
            return cluster
    return None


def _should_group(existing: RawArticle, candidate: RawArticle) -> bool:
    if _same_url(existing, candidate):
        return True
    if not _within_merge_window(existing.published_at, candidate.published_at):
        return False

    existing_model_keys = _extract_model_keys(existing)
    candidate_model_keys = _extract_model_keys(candidate)
    shared_model_keys = existing_model_keys.intersection(candidate_model_keys)
    if any(any(char.isdigit() for char in key) for key in shared_model_keys):
        return True

    overlap = _title_tokens(existing).intersection(_title_tokens(candidate))
    meaningful_overlap = {token for token in overlap if len(token) >= 4 or any(char.isdigit() for char in token)}
    return len(meaningful_overlap) >= 2


def _same_url(existing: RawArticle, candidate: RawArticle) -> bool:
    left = _normalize_url(existing.url)
    right = _normalize_url(candidate.url)
    return bool(left and right and left == right)


def _normalize_url(raw: str | None) -> str:
    text = str(raw or "").strip().rstrip("/")
    return text.lower()


def _within_merge_window(existing: datetime | None, candidate: datetime | None) -> bool:
    if existing is None or candidate is None:
        return True
    left = existing if existing.tzinfo else existing.replace(tzinfo=timezone.utc)
    right = candidate if candidate.tzinfo else candidate.replace(tzinfo=timezone.utc)
    return abs(left.astimezone(timezone.utc) - right.astimezone(timezone.utc)) <= MERGE_WINDOW


def _extract_model_keys(article: RawArticle) -> set[str]:
    keys: set[str] = set()
    text = _article_title(article)
    for match in MODEL_KEY_PATTERN.finditer(text):
        normalized = re.sub(r"[^a-z0-9.]+", "", match.group(0).lower())
        if normalized:
            keys.add(normalized)
    return keys


def _title_tokens(article: RawArticle) -> set[str]:
    tokens: set[str] = set()
    for match in TOKEN_PATTERN.finditer(_article_title(article)):
        token = match.group(0).lower()
        if token in TITLE_GENERIC_TOKENS:
            continue
        if _is_year_token(token):
            continue
        tokens.add(token)
    return tokens


def _is_year_token(token: str) -> bool:
    return bool(re.fullmatch(r"(19|20)\d{2}", token))


def _article_title(article: RawArticle) -> str:
    return str(article.title or "")


def _article_text(article: RawArticle) -> str:
    content = str(article.content or "")[:600]
    return " ".join([str(article.title or ""), content])


def _create_cluster(*, article: RawArticle, index: int) -> CandidateCluster:
    source_id = str((article.metadata or {}).get("source_id") or "").strip()
    source_name = str((article.metadata or {}).get("source_name") or "").strip()
    return CandidateCluster(
        cluster_id=f"cluster-{index}",
        articles=[article],
        source_ids=[source_id] if source_id else [],
        source_names=[source_name] if source_name else [],
    )


def _append_article(cluster: CandidateCluster, article: RawArticle) -> None:
    cluster.articles.append(article)
    source_id = str((article.metadata or {}).get("source_id") or "").strip()
    source_name = str((article.metadata or {}).get("source_name") or "").strip()
    if source_id and source_id not in cluster.source_ids:
        cluster.source_ids.append(source_id)
    if source_name and source_name not in cluster.source_names:
        cluster.source_names.append(source_name)


def _article_priority(article: RawArticle) -> tuple[int, int, str]:
    metadata = article.metadata or {}
    source_category = str(metadata.get("source_category") or "").strip().lower()
    category_priority = SOURCE_CATEGORY_PRIORITY.get(source_category, 9)
    content_len = len(str(article.content or ""))
    title = str(article.title or "")
    return category_priority, -content_len, title
