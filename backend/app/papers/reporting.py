"""Paper report assembly helpers."""

from __future__ import annotations

import re
from typing import Any

from app.collectors.base import RawArticle
from app.processors.pipeline import ProcessedArticle
from app.renderers.base import RenderContext, Report
from app.template_engine.renderer import render_report_template

_TITLE_SLUG_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")
_IMPORTANCE_WEIGHT = {"high": 3, "normal": 2, "low": 1}


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
    ranked = sorted(_representative_articles_by_identity(articles), key=_paper_rank_key, reverse=True)
    return ranked[:limit]


def build_paper_digest_entries(
    articles: list[ProcessedArticle],
    *,
    selected_identities: set[str],
    detail_links_by_identity: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entries: list[dict[str, Any]] = []
    note_links: list[dict[str, Any]] = []
    for article in _representative_articles_by_identity(articles):
        identity = build_paper_identity(article)
        slug = build_paper_slug(article)
        selected = identity in selected_identities
        detail_report_id = (detail_links_by_identity or {}).get(identity)
        detail_link = f"[查看详细笔记](/reports/{detail_report_id})" if detail_report_id else ""
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
                }
            )
    return entries, note_links


def build_paper_digest_report(
    *,
    articles: list[ProcessedArticle],
    context: RenderContext,
    detail_links_by_identity: dict[str, str] | None = None,
) -> Report:
    selected = select_paper_note_candidates(articles)
    selected_identities = {build_paper_identity(article) for article in selected}
    digest_title = _digest_title(context)
    digest_summary = _digest_summary(articles, context=context)
    papers, _ = build_paper_digest_entries(
        articles,
        selected_identities=selected_identities,
        detail_links_by_identity=detail_links_by_identity,
    )
    note_links = build_paper_note_links(
        articles,
        selected_identities=selected_identities,
    )
    rendered = render_report_template(
        report_type="paper",
        version="v1",
        context={
            **_paper_mode_context("digest"),
            "title": digest_title,
            "date": context.date,
            "summary": digest_summary,
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
            global_tldr=digest_summary,
            tldr=[digest_summary] if digest_summary else [],
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
    back_link = digest_title if parent_link else ""
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


def _digest_summary(articles: list[ProcessedArticle], *, context: RenderContext | None = None) -> str:
    extra = (context.extra or {}) if context is not None and context.extra else {}
    explicit = str(extra.get("digest_summary") or extra.get("global_tldr") or "").strip()
    if explicit:
        return explicit
    if not articles:
        return ""
    selected = select_paper_note_candidates(articles, limit=min(2, len(articles)))
    summaries: list[str] = []
    for article in selected:
        sentence = _clean_digest_sentence(_one_line_summary(article))
        if sentence and sentence not in summaries:
            summaries.append(sentence)
    if len(summaries) >= 2:
        return (
            f"{summaries[0]}同时，{summaries[1]}"
            "整体上，本期更值得关注这些工作是否正在从单点结果走向可复用框架与系统能力。"
        )
    if len(summaries) == 1:
        return f"{summaries[0]}整体上，本期更值得关注这项方向能否进一步沉淀为可复用的方法框架。"
    titles = [_paper_title(article) for article in selected if _paper_title(article)]
    if not titles:
        return ""
    return f"本期收录 {len(articles)} 篇论文，重点围绕 {titles[0]} 等方向展开，后续更值得关注其工程落地与可复用性。"


def build_paper_note_links(
    articles: list[ProcessedArticle],
    *,
    selected_identities: set[str],
) -> list[dict[str, Any]]:
    _, note_links = build_paper_digest_entries(
        articles,
        selected_identities=selected_identities,
    )
    return note_links


def build_paper_parent_link(*, parent_report_id: str | None, digest_title: str) -> dict[str, Any] | None:
    if not parent_report_id:
        return None
    return {
        "report_id": parent_report_id,
        "title": digest_title,
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
    authors = _paper_authors(article)
    if isinstance(authors, list):
        items = [_author_name(item) for item in authors]
        items = [item for item in items if item]
        if items:
            return "，".join(items)
    if isinstance(authors, str) and authors.strip():
        return authors.strip()
    return "N/A"


def _affiliations_text(article: ProcessedArticle) -> str:
    metadata = _article_metadata(article)
    authors = _paper_authors(article)
    if isinstance(authors, list) and authors:
        first_author_affiliation = _author_affiliation(authors[0])
        if first_author_affiliation:
            return first_author_affiliation
    for key in ("first_author_affiliation", "first_author_institution", "affiliations", "institution", "institutions"):
        value = _first_text(metadata.get(key))
        if value:
            return value
    organization = _organization_name(metadata.get("organization"))
    if organization:
        return organization
    return "N/A"


def _article_metadata(article: ProcessedArticle) -> dict[str, Any]:
    return article.raw.metadata if isinstance(article.raw.metadata, dict) else {}


def _paper_authors(article: ProcessedArticle) -> Any:
    metadata = _article_metadata(article)
    authors = metadata.get("authors")
    if authors:
        return authors
    nested_paper = metadata.get("paper")
    if isinstance(nested_paper, dict):
        nested_authors = nested_paper.get("authors")
        if nested_authors:
            return nested_authors
    return None


def _author_name(author: Any) -> str:
    if isinstance(author, str):
        return author.strip()
    if isinstance(author, dict):
        for key in ("name", "fullname", "full_name", "display_name"):
            value = author.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        user = author.get("user")
        if isinstance(user, dict):
            for key in ("fullname", "name", "user"):
                value = user.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return ""


def _author_affiliation(author: Any) -> str:
    if not isinstance(author, dict):
        return ""
    for key in ("affiliations", "affiliation", "institution", "institutions", "organization", "org"):
        value = _first_text(author.get(key))
        if value:
            return value
    return ""


def _first_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        for item in value:
            text = _display_text(item)
            if text:
                return text
        return ""
    if isinstance(value, dict):
        return _display_text(value)
    return ""


def _display_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("fullname", "name", "title", "label", "institution", "affiliation"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return ""


def _organization_name(value: Any) -> str:
    return _display_text(value)


def _figure_url(article: ProcessedArticle) -> str:
    metadata = _article_metadata(article)
    for key in ("figure_url", "figure", "image", "cover"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _one_line_summary(article: ProcessedArticle) -> str:
    return str(article.summary or article.raw.title or "").strip()


def _clean_digest_sentence(text: str) -> str:
    sentence = str(text or "").strip()
    if not sentence:
        return ""
    sentence = re.sub(r"\s+", " ", sentence)
    sentence = sentence.rstrip("。！？!?；;，, ")
    return f"{sentence}。"


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
    metadata = _article_metadata(article)
    notes: list[str] = []

    figure = _figure_url(article)
    figure_caption = _first_text(metadata.get("figure_caption")) or "Figure 1"
    if figure:
        notes.append(_render_figure_block(title=figure_caption, image_url=figure, source_label="arXiv HTML"))

    project_teaser = _first_text(metadata.get("project_teaser_url"))
    if project_teaser and project_teaser != figure:
        notes.append(_render_figure_block(title="Project Teaser", image_url=project_teaser, source_label="项目页 teaser"))

    return notes


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


def _render_figure_block(*, title: str, image_url: str, source_label: str) -> str:
    return "\n\n".join(
        [
            f"### {title}",
            f"![{title}]({image_url})",
            f"图示来源：{source_label}",
        ]
    )


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
    if not candidate:
        return "unknown-paper"

    compact = re.sub(r"\s+", "", candidate)
    lowered = compact.lower()

    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "doi:"):
        if lowered.startswith(prefix):
            suffix = compact[len(prefix) :]
            return suffix.lower() or "unknown-paper"

    for prefix in ("https://arxiv.org/abs/", "https://arxiv.org/pdf/", "http://arxiv.org/abs/", "http://arxiv.org/pdf/", "arxiv:"):
        if lowered.startswith(prefix):
            suffix = compact[len(prefix) :]
            suffix = re.sub(r"\.pdf$", "", suffix, flags=re.IGNORECASE)
            return suffix.lower() or "unknown-paper"

    return compact.lower()


def _representative_articles_by_identity(articles: list[ProcessedArticle]) -> list[ProcessedArticle]:
    identity_order: list[str] = []
    best_by_identity: dict[str, ProcessedArticle] = {}
    for article in articles:
        identity = build_paper_identity(article)
        if identity not in best_by_identity:
            identity_order.append(identity)
        current = best_by_identity.get(identity)
        if current is None or _paper_rank_key(article) > _paper_rank_key(current):
            best_by_identity[identity] = article
    return [best_by_identity[identity] for identity in identity_order]


def _slugify(value: str) -> str:
    candidate = str(value or "").strip().lower()
    candidate = candidate.replace("&", " and ")
    candidate = _TITLE_SLUG_RE.sub("-", candidate)
    candidate = re.sub(r"-+", "-", candidate)
    return candidate.strip("-") or "paper"
