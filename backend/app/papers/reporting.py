"""Paper report assembly helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.collectors.base import RawArticle
from app.processors.event_models import ProcessedEvent
from app.processors.pipeline import ProcessedArticle
from app.renderers.base import RenderContext, Report
from app.template_engine.renderer import render_report_template

_TITLE_SLUG_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")
_IMPORTANCE_WEIGHT = {"high": 3, "normal": 2, "low": 1}


@dataclass(slots=True)
class PaperIdentity:
    paper_identity: str
    paper_slug: str


def build_paper_identity(article: ProcessedArticle) -> str:
    metadata = dict(article.raw.metadata or {})
    for key in ("paper_id", "doi", "arxiv_id", "pmid", "pmcid"):
        value = metadata.get(key)
        if value:
            return _normalize_identity(value)
    return build_paper_slug(article)


def build_paper_slug(article: ProcessedArticle) -> str:
    title = _paper_title(article)
    return _slugify(title)


def select_paper_note_candidates(articles: list[ProcessedArticle], *, limit: int = 2) -> list[ProcessedArticle]:
    ranked = sorted(articles, key=_paper_rank_key, reverse=True)
    return ranked[:limit]


def build_paper_digest_entries(
    articles: list[ProcessedArticle],
    *,
    selected_identities: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entries: list[dict[str, Any]] = []
    note_links: list[dict[str, Any]] = []
    for article in articles:
        identity = build_paper_identity(article)
        slug = build_paper_slug(article)
        selected = identity in selected_identities
        detail_link = f"[阅读笔记](#{slug})" if selected else ""
        entry = {
            "title": _paper_title(article),
            "authors": _authors_text(article),
            "affiliations": _affiliations_text(article),
            "figure": _figure_url(article),
            "one_line": _one_line_summary(article),
            "problem": _problem_text(article),
            "method": _method_text(article),
            "result": _result_text(article),
            "importance": _importance_text(article),
            "reading_level": _reading_level(article, selected=selected),
            "detail_link": detail_link,
            "paper_identity": identity,
            "paper_slug": slug,
            "selected": selected,
        }
        entries.append(entry)
        if selected:
            note_links.append(
                {
                    "paper_identity": identity,
                    "paper_slug": slug,
                    "title": entry["title"],
                    "selected": True,
                    "detail_link": detail_link,
                }
            )
    return entries, note_links


def build_paper_digest_report(*, articles: list[ProcessedArticle], context: RenderContext) -> Report:
    selected = select_paper_note_candidates(articles)
    selected_identities = {build_paper_identity(article) for article in selected}
    digest_title = _digest_title(context)
    papers, _ = build_paper_digest_entries(articles, selected_identities=selected_identities)
    note_links = build_paper_note_links(
        articles,
        selected_identities=selected_identities,
        digest_identity=_digest_identity(context),
        digest_title=digest_title,
    )
    rendered = render_report_template(
        report_type="paper",
        version="v1",
        context={
            **_paper_mode_context("digest"),
            "title": digest_title,
            "date": context.date,
            "summary": _digest_summary(articles),
            "papers": papers,
        },
    )
    return Report(
        level="L3",
        title=digest_title,
        content=rendered,
        article_ids=[article.raw.external_id for article in articles],
        metadata=_paper_metadata(
            paper_mode="digest",
            paper_identity=_digest_identity(context),
            paper_slug=_slugify(digest_title),
            paper_note_links=note_links,
            papers=papers,
            selected_paper_identities=sorted(selected_identities),
        ),
    )


def build_paper_note_report(
    article: ProcessedArticle,
    *,
    context: RenderContext,
    parent_report_id: str | None = None,
    digest_title: str | None = None,
) -> Report:
    identity = build_paper_identity(article)
    slug = build_paper_slug(article)
    title = _paper_title(article)
    digest_title = digest_title or _digest_title(context)
    parent_link = build_paper_parent_link(parent_report_id=parent_report_id, digest_title=digest_title)
    back_link = parent_link["detail_link"] if parent_link else ""
    rendered = render_report_template(
        report_type="paper",
        version="v1",
        context={
            **_paper_mode_context("note"),
            "title": title,
            "authors": _authors_text(article),
            "affiliations": _affiliations_text(article),
            "links": _paper_links(article),
            "summary": _note_summary(article),
            "contributions": _contributions(article),
            "method_details": _method_details(article),
            "figure_notes": _figure_notes(article),
            "experiments": _experiments(article),
            "interpretation": _interpretation(article),
            "limitations": _limitations(article),
            "use_cases": _use_cases(article),
            "related_reading": _related_reading(article),
            "back_link": back_link,
        },
    )
    return Report(
        level="L4",
        title=title,
        content=rendered,
        article_ids=[article.raw.external_id],
        metadata=_paper_metadata(
            paper_mode="note",
            parent_report_id=parent_report_id,
            paper_identity=identity,
            paper_slug=slug,
            paper_note_links=[],
            paper_parent_link=parent_link,
        ),
    )


def _digest_summary(articles: list[ProcessedArticle]) -> str:
    if not articles:
        return ""
    selected = select_paper_note_candidates(articles, limit=min(3, len(articles)))
    titles = [_paper_title(article) for article in selected if _paper_title(article)]
    if not titles:
        return ""
    if len(titles) == 1:
        return f"本期聚焦 {titles[0]}。"
    if len(titles) == 2:
        return f"本期聚焦 {titles[0]} 和 {titles[1]}。"
    return f"本期聚焦 {titles[0]}、{titles[1]} 等 {len(articles)} 篇论文。"


def build_paper_note_links(
    articles: list[ProcessedArticle],
    *,
    selected_identities: set[str],
    digest_identity: str,
    digest_title: str,
) -> list[dict[str, Any]]:
    _, note_links = build_paper_digest_entries(articles, selected_identities=selected_identities)
    if note_links:
        return note_links
    return [
        {
            "paper_identity": digest_identity,
            "paper_slug": _slugify(digest_title),
            "title": digest_title,
            "selected": False,
            "detail_link": "",
        }
    ]


def build_paper_parent_link(*, parent_report_id: str | None, digest_title: str) -> dict[str, Any] | None:
    if not parent_report_id:
        return None
    return {
        "report_id": parent_report_id,
        "title": digest_title,
        "detail_link": f"[返回 {digest_title}](#{parent_report_id})",
    }


def _paper_rank_key(article: ProcessedArticle) -> tuple[int, float, str]:
    importance = _IMPORTANCE_WEIGHT.get(str(article.importance or "").strip().lower(), 0)
    return importance, float(article.score or 0.0), _paper_title(article).lower()


def _digest_title(context: RenderContext) -> str:
    extra = context.extra or {}
    candidate = str(extra.get("title") or "").strip()
    if candidate:
        return candidate
    if context.date:
        return f"{context.date} 论文推荐"
    return "论文推荐"


def _digest_identity(context: RenderContext) -> str:
    return _slugify(_digest_title(context))


def _paper_mode_context(paper_mode: str) -> dict[str, str]:
    return {"paper_mode": paper_mode}


def _paper_metadata(
    *,
    paper_mode: str,
    paper_identity: str,
    paper_slug: str,
    paper_note_links: list[dict[str, Any]],
    **extra: Any,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    metadata.update(_paper_mode_metadata(paper_mode))
    metadata.update(_paper_identity_metadata(paper_identity))
    metadata.update(_paper_slug_metadata(paper_slug))
    metadata.update(_paper_note_links_metadata(paper_note_links))
    metadata.update(_parent_report_id_metadata(extra.get("parent_report_id")))
    metadata.update(_paper_parent_link_metadata(extra.get("paper_parent_link")))
    for key, value in extra.items():
        if key in {"parent_report_id", "paper_parent_link"}:
            continue
        metadata[key] = value
    return metadata


def _paper_mode_metadata(paper_mode: str) -> dict[str, str]:
    return {"paper_mode": paper_mode}


def _parent_report_id_metadata(parent_report_id: str | None) -> dict[str, str]:
    if not parent_report_id:
        return {}
    return {"parent_report_id": parent_report_id}


def _paper_identity_metadata(paper_identity: str) -> dict[str, str]:
    return {"paper_identity": paper_identity}


def _paper_slug_metadata(paper_slug: str) -> dict[str, str]:
    return {"paper_slug": paper_slug}


def _paper_note_links_metadata(paper_note_links: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {"paper_note_links": paper_note_links}


def _paper_parent_link_metadata(paper_parent_link: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if paper_parent_link is None:
        return {}
    return {"paper_parent_link": paper_parent_link}


def _paper_title(article: ProcessedArticle) -> str:
    raw_title = str(article.raw.title or "").strip()
    return raw_title or "未命名论文"


def _authors_text(article: ProcessedArticle) -> str:
    authors = article.raw.metadata.get("authors") if isinstance(article.raw.metadata, dict) else None
    if isinstance(authors, list):
        items = [str(item).strip() for item in authors if str(item).strip()]
        if items:
            return "，".join(items)
    if isinstance(authors, str) and authors.strip():
        return authors.strip()
    return "N/A"


def _affiliations_text(article: ProcessedArticle) -> str:
    metadata = article.raw.metadata if isinstance(article.raw.metadata, dict) else {}
    affiliations = metadata.get("affiliations")
    if isinstance(affiliations, list):
        items = [str(item).strip() for item in affiliations if str(item).strip()]
        if items:
            return "，".join(items)
    if isinstance(affiliations, str) and affiliations.strip():
        return affiliations.strip()
    return "N/A"


def _figure_url(article: ProcessedArticle) -> str:
    metadata = article.raw.metadata if isinstance(article.raw.metadata, dict) else {}
    for key in ("figure_url", "figure", "image", "cover"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _one_line_summary(article: ProcessedArticle) -> str:
    return str(article.summary or article.raw.title or "").strip()


def _problem_text(article: ProcessedArticle) -> str:
    return str(article.what or article.summary or article.detail or "").strip()


def _method_text(article: ProcessedArticle) -> str:
    return str(article.detail or article.evidence or article.summary or "").strip()


def _result_text(article: ProcessedArticle) -> str:
    metrics = ", ".join(str(item).strip() for item in article.metrics if str(item).strip())
    if metrics:
        return metrics
    return str(article.evidence or article.detail or article.summary or "").strip()


def _importance_text(article: ProcessedArticle) -> str:
    importance = str(article.importance or "").strip()
    return {
        "high": "值得重点关注",
        "normal": "有阅读价值",
        "low": "可按需查看",
    }.get(importance, importance or "有阅读价值")


def _reading_level(article: ProcessedArticle, *, selected: bool) -> str:
    if selected and str(article.importance or "").strip().lower() == "high":
        return "必读"
    if selected:
        return "值得看"
    return "可略读"


def _paper_links(article: ProcessedArticle) -> list[str]:
    metadata = article.raw.metadata if isinstance(article.raw.metadata, dict) else {}
    links: list[str] = []
    for key in ("paper_url", "arxiv_url", "pdf_url", "project_url", "code_url"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            links.append(value.strip())
    if article.raw.url and article.raw.url not in links:
        links.append(article.raw.url)
    return links


def _note_summary(article: ProcessedArticle) -> str:
    pieces = [str(article.summary or "").strip(), str(article.detail or "").strip()]
    return next((piece for piece in pieces if piece), "")


def _contributions(article: ProcessedArticle) -> list[str]:
    return _nonempty_items(
        [
            article.summary,
            article.evidence,
            article.detail,
        ]
    )


def _method_details(article: ProcessedArticle) -> list[str]:
    return _nonempty_items([article.detail, article.what, article.evidence])


def _figure_notes(article: ProcessedArticle) -> list[str]:
    figure = _figure_url(article)
    return [f"核心图：{figure}"] if figure else []


def _experiments(article: ProcessedArticle) -> list[str]:
    return _nonempty_items([article.metrics, article.evidence])


def _interpretation(article: ProcessedArticle) -> list[str]:
    return _nonempty_items([article.detail, article.summary])


def _limitations(article: ProcessedArticle) -> list[str]:
    values = _nonempty_items([article.unknowns])
    return values or ["暂无明确局限信息"]


def _use_cases(article: ProcessedArticle) -> list[str]:
    return _nonempty_items([article.category, article.raw.metadata.get("source_name") if isinstance(article.raw.metadata, dict) else None])


def _related_reading(article: ProcessedArticle) -> list[str]:
    return _nonempty_items([article.keywords])


def _nonempty_items(values: list[Any]) -> list[str]:
    items: list[str] = []
    for value in values:
        if isinstance(value, list):
            nested = [str(item).strip() for item in value if str(item).strip()]
            items.extend(nested)
            continue
        if isinstance(value, str) and value.strip():
            items.append(value.strip())
    return items


def _normalize_identity(value: Any) -> str:
    candidate = str(value).strip()
    return candidate or "unknown-paper"


def _slugify(value: str) -> str:
    candidate = str(value or "").strip().lower()
    candidate = candidate.replace("&", " and ")
    candidate = _TITLE_SLUG_RE.sub("-", candidate)
    candidate = re.sub(r"-+", "-", candidate)
    return candidate.strip("-") or "paper"
