"""Aggregate source-level events into report-level events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

MODEL_KEY_PATTERN = re.compile(
    r"\b(gpt|gemini|claude|llama|qwen|mistral|deepseek|codex)"
    r"(?:\s+(?:opus|sonnet|haiku|flash|pro|max|mini|nano|ultra|instant|turbo|code|security))?"
    r"(?:[-\s]?\d+(?:\.\d+)*)?\b",
    re.IGNORECASE,
)
TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{1,}", re.IGNORECASE)
PHRASE_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9.+_-]{1,}", re.IGNORECASE)
VERSION_TOKEN_PATTERN = re.compile(r"^\d+(?:\.\d+)*$")
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
    "thinking",
    "system",
    "card",
    "update",
    "blog",
    "post",
    "event",
    "events",
    "summary",
    "source",
    "test",
}
MODEL_FAMILY_TOKENS = {"gpt", "gemini", "claude", "llama", "qwen", "mistral", "deepseek", "codex"}
MODEL_VARIANT_TOKENS = {
    "opus",
    "sonnet",
    "haiku",
    "flash",
    "pro",
    "max",
    "mini",
    "nano",
    "ultra",
    "instant",
    "turbo",
    "code",
}
MERGE_WINDOW = timedelta(hours=36)


def aggregate_events(events: list[dict]) -> list[dict]:
    aggregated: list[dict] = []
    for event in events:
        candidate = _clone_event(event)
        target = _find_merge_target(aggregated, candidate)
        if target is None:
            aggregated.append(candidate)
            continue
        _merge_event(target, candidate)
    return reindex_events(aggregated)


def reindex_events(events: list[dict]) -> list[dict]:
    for index, event in enumerate(events, start=1):
        event["index"] = index
    return events


def _find_merge_target(aggregated: list[dict], candidate: dict) -> dict | None:
    for existing in aggregated:
        if _should_merge(existing, candidate):
            return existing
    return None


def _should_merge(existing: dict, candidate: dict) -> bool:
    if not _within_merge_window(existing, candidate):
        return False

    same_source = _normalized_source_name(existing) == _normalized_source_name(candidate)
    existing_model_keys = _extract_model_keys(existing)
    candidate_model_keys = _extract_model_keys(candidate)
    phrase_overlap = _title_phrase_keys(existing).intersection(_title_phrase_keys(candidate))
    overlap = _event_tokens(existing).intersection(_event_tokens(candidate))
    meaningful_overlap = _merge_overlap_tokens(existing).intersection(_merge_overlap_tokens(candidate))

    if same_source:
        return False

    if phrase_overlap:
        return True

    if existing_model_keys and candidate_model_keys and existing_model_keys.intersection(candidate_model_keys):
        if _is_model_release_pair(existing, candidate) and _has_specific_model_key(
            existing_model_keys.intersection(candidate_model_keys)
        ):
            return True
        return len(meaningful_overlap) >= 1

    if str(existing.get("category") or "") != str(candidate.get("category") or ""):
        return False
    return len(meaningful_overlap) >= 2 or len(overlap) >= 3


def _within_merge_window(existing: dict, candidate: dict) -> bool:
    existing_time = _parse_event_time(existing.get("published_at"))
    candidate_time = _parse_event_time(candidate.get("published_at"))
    if existing_time is None or candidate_time is None:
        return True
    return abs(existing_time - candidate_time) <= MERGE_WINDOW


def _extract_model_keys(event: dict) -> set[str]:
    text = " ".join(
        [
            str(event.get("title") or ""),
            str(event.get("one_line_tldr") or ""),
            " ".join(str(item or "") for item in (event.get("keywords") or [])),
        ]
    )
    keys: set[str] = set()
    for match in MODEL_KEY_PATTERN.finditer(text):
        normalized = re.sub(r"[^a-z0-9.]+", "", match.group(0).lower())
        if normalized:
            keys.add(normalized)
    return keys


def _event_tokens(event: dict) -> set[str]:
    values: list[str] = [
        str(event.get("title") or ""),
        str(event.get("one_line_tldr") or ""),
        *[str(item or "") for item in (event.get("keywords") or [])],
    ]
    tokens: set[str] = set()
    for value in values:
        for match in TOKEN_PATTERN.finditer(value.lower()):
            token = match.group(0)
            if token in GENERIC_TOKENS:
                continue
            tokens.add(token)
    return tokens


def _merge_overlap_tokens(event: dict) -> set[str]:
    return {token for token in _event_tokens(event) if not _is_merge_noise_token(token)}


def _title_phrase_keys(event: dict) -> set[str]:
    values = [
        str(event.get("title") or ""),
        str(event.get("event_title") or ""),
        *[str(item or "") for item in (event.get("keywords") or [])],
    ]
    phrases: set[str] = set()
    for value in values:
        tokens = [
            token
            for token in (match.group(0).lower() for match in PHRASE_TOKEN_PATTERN.finditer(value))
            if token not in GENERIC_TOKENS
        ]
        for start in range(len(tokens) - 1):
            phrase_tokens = tokens[start : start + 2]
            if all(_is_merge_noise_token(token) for token in phrase_tokens):
                continue
            phrases.add(" ".join(phrase_tokens))
    return phrases


def _is_merge_noise_token(token: str) -> bool:
    return token in GENERIC_TOKENS or token in MODEL_FAMILY_TOKENS or token in MODEL_VARIANT_TOKENS or bool(
        VERSION_TOKEN_PATTERN.fullmatch(token)
    )


def _is_model_release_pair(existing: dict, candidate: dict) -> bool:
    return str(existing.get("category") or "") == "模型发布" and str(candidate.get("category") or "") == "模型发布"


def _has_specific_model_key(keys: set[str]) -> bool:
    for key in keys:
        normalized = re.sub(r"[^a-z0-9.]+", "", key.lower())
        if any(ch.isdigit() for ch in normalized):
            return True
        if any(variant in normalized for variant in MODEL_VARIANT_TOKENS):
            return True
    return False


def _normalized_source_name(event: dict) -> str:
    return re.sub(r"\s+", " ", str(event.get("source_name") or "").strip().lower())


def _merge_event(existing: dict, candidate: dict) -> None:
    _merge_unique_list(existing, candidate, "source_links")
    _merge_unique_list(existing, candidate, "keywords")
    _merge_unique_list(existing, candidate, "entities")
    _merge_unique_list(existing, candidate, "metrics")
    _merge_unique_list(existing, candidate, "article_ids")
    existing["source_count"] = len(existing.get("source_links") or [])

    if _priority(candidate) > _priority(existing):
        _replace_primary_fields(existing, candidate)
    else:
        existing["detail"] = _pick_detail(str(existing.get("detail") or ""), str(candidate.get("detail") or ""))
        existing["one_line_tldr"] = _pick_summary(
            str(existing.get("one_line_tldr") or ""),
            str(candidate.get("one_line_tldr") or ""),
        )
        _fill_blank_fields(existing, candidate)
        existing["published_at"] = _pick_latest_time(existing.get("published_at"), candidate.get("published_at"))


def _priority(event: dict) -> tuple[int, int]:
    importance = 1 if str(event.get("importance") or "").strip().lower() == "high" else 0
    detail_len = len(str(event.get("detail") or ""))
    return importance, detail_len


def _replace_primary_fields(existing: dict, candidate: dict) -> None:
    for key in (
        "event_id",
        "title",
        "event_title",
        "one_line_tldr",
        "detail",
        "source_name",
        "published_at",
        "importance",
        "who",
        "what",
        "when",
        "availability",
        "unknowns",
        "evidence",
    ):
        existing[key] = candidate.get(key)


def _fill_blank_fields(existing: dict, candidate: dict) -> None:
    for key in ("who", "what", "when", "availability", "unknowns", "evidence"):
        if str(existing.get(key) or "").strip():
            continue
        value = str(candidate.get(key) or "").strip()
        if value:
            existing[key] = value


def _pick_detail(current: str, candidate: str) -> str:
    if len(candidate) > len(current):
        return candidate
    return current


def _pick_summary(current: str, candidate: str) -> str:
    if len(candidate) > len(current):
        return candidate
    return current


def _merge_unique_list(existing: dict, candidate: dict, key: str) -> None:
    seen: set[str] = set()
    merged: list[str] = []
    for value in [*(existing.get(key) or []), *(candidate.get(key) or [])]:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        merged.append(text)
    existing[key] = merged


def _pick_latest_time(existing: object, candidate: object) -> str | None:
    existing_time = _parse_event_time(existing)
    candidate_time = _parse_event_time(candidate)
    if existing_time is None:
        return str(candidate) if candidate else None
    if candidate_time is None:
        return str(existing) if existing else None
    return existing if existing_time >= candidate_time else candidate


def _parse_event_time(raw: object) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clone_event(event: dict) -> dict:
    cloned = dict(event)
    for key in ("source_links", "keywords", "entities", "metrics", "article_ids"):
        value = cloned.get(key)
        cloned[key] = list(value) if isinstance(value, list) else []
    if not cloned["article_ids"]:
        event_id = str(cloned.get("event_id") or "").strip()
        cloned["article_ids"] = [event_id] if event_id else []
    return cloned
