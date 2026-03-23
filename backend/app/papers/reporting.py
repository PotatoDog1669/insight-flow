"""Paper report assembly helpers."""

from __future__ import annotations

import ast
import re
from collections import Counter
from typing import Any

from app.processors.pipeline import ProcessedArticle
from app.renderers.base import RenderContext, Report
from app.template_engine.renderer import render_report_template

_TITLE_SLUG_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")
_IMPORTANCE_WEIGHT = {"high": 3, "normal": 2, "low": 1}
_KEYWORD_STOPWORDS = {
    "academic",
    "agent",
    "agents",
    "ai",
    "arxiv",
    "llm",
    "paper",
    "papers",
    "preprint",
    "research",
}


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
        links = _paper_links(article)
        entry = {
            "title": _paper_title(article),
            "authors": _authors_text(article),
            "affiliations": _affiliations_text(article),
            "links": _link_items(links),
            "figure": _figure_url(article),
            "one_line_judgment": _one_line_summary(article),
            "core_problem": _problem_text(article),
            "core_method": _method_text(article),
            "key_result": _result_text(article),
            "why_it_matters": _importance_text(article),
            "recommendation": _reading_level(article, selected=selected),
            "detail_link": detail_link,
            "source_label": _paper_source_label(links),
            "topic_label": _infer_paper_topic(
                title=_paper_title(article),
                text_parts=[
                    _one_line_summary(article),
                    _problem_text(article),
                    _method_text(article),
                    _result_text(article),
                    " ".join(str(item) for item in (article.keywords or [])),
                ],
            ),
            "paper_identity": identity,
            "paper_slug": slug,
            "selected": selected,
            # Backward-compatible aliases for metadata readers and helper tests.
            "one_line": _one_line_summary(article),
            "problem": _problem_text(article),
            "method": _method_text(article),
            "result": _result_text(article),
            "importance": _importance_text(article),
            "reading_level": _reading_level(article, selected=selected),
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
    review_payload: dict[str, Any] | None = None,
) -> Report:
    resolved_review_payload = review_payload or _paper_review_payload(context)
    if resolved_review_payload:
        return _build_paper_digest_report_from_review_payload(
            articles=articles,
            context=context,
            review_payload=resolved_review_payload,
            detail_links_by_identity=detail_links_by_identity,
        )

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
    properties = _build_digest_properties(articles=articles, papers=papers, context=context)
    frontmatter = _build_digest_frontmatter(properties)
    theme_groups = _build_theme_groups(papers)
    rendered = render_report_template(
        report_type="paper",
        version="v1",
        context={
            **_paper_mode_context("digest"),
            "title": digest_title,
            "date": context.date,
            "summary": digest_summary,
            "frontmatter": frontmatter,
            "properties": properties,
            "theme_groups": theme_groups,
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
            properties=properties,
            frontmatter=frontmatter,
            theme_groups=theme_groups,
            selected_paper_identities=sorted(selected_identities),
        ),
    )


def build_paper_note_report(
    article: ProcessedArticle,
    *,
    context: RenderContext,
    parent_report_id: str | None = None,
    digest_title: str | None = None,
    note_payload: dict[str, Any] | None = None,
) -> Report:
    resolved_note_payload = note_payload or _paper_note_payload(context)
    if resolved_note_payload:
        return _build_paper_note_report_from_payload(
            article,
            context=context,
            parent_report_id=parent_report_id,
            digest_title=digest_title,
            note_payload=resolved_note_payload,
        )

    identity = build_paper_identity(article)
    slug = build_paper_slug(article)
    title = _paper_title(article)
    digest_title = digest_title or _digest_title(context)
    parent_link = build_paper_parent_link(parent_report_id=parent_report_id, digest_title=digest_title)
    summary = _note_summary(article)
    contributions = _contributions(article, summary=summary)
    method_details = _method_details(article, summary=summary, contributions=contributions)
    experiments = _experiments(
        article,
        summary=summary,
        contributions=contributions,
        method_details=method_details,
    )
    strengths = _strengths(
        article,
        summary=summary,
        contributions=contributions,
        method_details=method_details,
        experiments=experiments,
    )
    related_reading = _related_reading(article)
    back_link = _note_back_link(parent_link)
    rendered = render_report_template(
        report_type="paper",
        version="v1",
        context={
            **_paper_mode_context("note"),
            "title": title,
            "authors": _authors_text(article),
            "affiliations": _affiliations_text(article),
            "links": _paper_links(article),
            "summary": summary,
            "contributions": contributions,
            "problem_statement": _problem_statement(article, summary=summary),
            "prior_limitations": _prior_limitations(article),
            "motivation": _motivation(article, summary=summary),
            "method_details": method_details,
            "figure_notes": _figure_notes(article),
            "experiments": experiments,
            "strengths": strengths,
            "limitations": _limitations(article),
            "next_steps": _next_steps(article),
            "related_reading": related_reading,
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


def _paper_review_payload(context: RenderContext | None) -> dict[str, Any] | None:
    extra = (context.extra or {}) if context is not None else {}
    payload = extra.get("paper_review_payload")
    return payload if isinstance(payload, dict) else None


def _paper_note_payload(context: RenderContext | None) -> dict[str, Any] | None:
    extra = (context.extra or {}) if context is not None else {}
    payload = extra.get("paper_note_payload")
    return payload if isinstance(payload, dict) else None


def _build_paper_digest_report_from_review_payload(
    *,
    articles: list[ProcessedArticle],
    context: RenderContext,
    review_payload: dict[str, Any],
    detail_links_by_identity: dict[str, str] | None = None,
) -> Report:
    digest_title = _digest_title(context)
    digest_summary = str(review_payload.get("digest_summary") or "").strip() or _digest_summary(
        articles,
        context=context,
    )
    raw_papers = review_payload.get("papers")
    papers = _paper_digest_entries_from_review_payload(
        raw_papers if isinstance(raw_papers, list) else [],
        detail_links_by_identity=detail_links_by_identity,
    )
    selected_identities = sorted(
        {
            str(item.get("paper_identity") or "").strip()
            for item in papers
            if item.get("note_candidate") and str(item.get("paper_identity") or "").strip()
        }
    )
    note_links = [
        {
            "paper_identity": str(item.get("paper_identity") or "").strip(),
            "paper_slug": str(item.get("paper_slug") or "").strip(),
            "title": str(item.get("title") or "").strip(),
            "selected": True,
        }
        for item in papers
        if item.get("note_candidate") and str(item.get("paper_identity") or "").strip()
    ]
    triage_groups = _build_triage_groups(papers)
    properties = _build_digest_properties(articles=articles, papers=papers, context=context)
    frontmatter = _build_digest_frontmatter(properties)
    theme_groups = _build_theme_groups(papers)
    rendered = render_report_template(
        report_type="paper",
        version="v1",
        context={
            **_paper_mode_context("digest"),
            "title": digest_title,
            "date": context.date,
            "summary": digest_summary,
            "frontmatter": frontmatter,
            "properties": properties,
            "theme_groups": theme_groups,
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
            properties=properties,
            frontmatter=frontmatter,
            theme_groups=theme_groups,
            triage_groups=triage_groups,
            selected_paper_identities=selected_identities,
            paper_recommendations=[
                {
                    "paper_identity": str(item.get("paper_identity") or "").strip(),
                    "recommendation": str(item.get("recommendation") or "").strip(),
                }
                for item in papers
                if str(item.get("paper_identity") or "").strip()
            ],
        ),
    )


def _paper_digest_entries_from_review_payload(
    papers: list[dict[str, Any]],
    *,
    detail_links_by_identity: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for raw in papers:
        if not isinstance(raw, dict):
            continue
        identity = str(raw.get("paper_identity") or "").strip()
        title = str(raw.get("title") or "未命名论文").strip() or "未命名论文"
        slug = str(raw.get("paper_slug") or "").strip() or _slugify(title)
        detail_report_id = (detail_links_by_identity or {}).get(identity)
        detail_link = (
            f"[查看详细笔记](/reports/{detail_report_id})"
            if detail_report_id
            else str(raw.get("detail_link") or "").strip()
        )
        one_line = str(raw.get("one_line_judgment") or raw.get("one_line") or "").strip()
        problem = str(raw.get("core_problem") or raw.get("problem") or "").strip()
        method = str(raw.get("core_method") or raw.get("method") or "").strip()
        result = str(raw.get("key_result") or raw.get("result") or "").strip()
        why = str(raw.get("why_it_matters") or raw.get("importance") or "").strip()
        recommendation = str(raw.get("recommendation") or "").strip()
        reading_advice = str(raw.get("reading_advice") or raw.get("reading_level") or "").strip()
        raw_links = raw.get("links")
        link_items = _link_items(raw_links)
        entry = {
            "paper_identity": identity,
            "paper_slug": slug,
            "title": title,
            "topic_label": str(raw.get("topic_label") or "").strip(),
            "authors": _display_list(raw.get("authors")),
            "affiliations": _display_list(raw.get("affiliations")),
            "links": link_items,
            "figure": str(raw.get("figure") or "").strip(),
            "recommendation": recommendation,
            "one_line_judgment": one_line,
            "core_problem": problem,
            "core_method": method,
            "key_result": result,
            "why_it_matters": why,
            "reading_advice": reading_advice,
            "note_candidate": bool(raw.get("note_candidate")),
            "detail_link": detail_link,
            "source_label": _paper_source_label(_link_urls(link_items)),
            # Backward-compatible aliases for fallback templates and metadata readers.
            "one_line": one_line,
            "problem": problem,
            "method": method,
            "result": result,
            "importance": why,
            "reading_level": reading_advice or recommendation,
        }
        entries.append(entry)
    return entries


def _build_triage_groups(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = ("必读", "值得看", "可略读")
    groups: list[dict[str, Any]] = []
    for label in order:
        items = []
        for paper in papers:
            if str(paper.get("recommendation") or "").strip() != label:
                continue
            title = str(paper.get("title") or "").strip()
            reason = str(paper.get("one_line_judgment") or "").strip()
            if not title:
                continue
            items.append({"title": title, "reason": reason})
        if items:
            groups.append({"label": label, "items": items})
    return groups


def _build_theme_groups(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for paper in papers:
        title = str(paper.get("title") or "").strip()
        theme = str(paper.get("topic_label") or "").strip() or _infer_paper_topic(
            title=title,
            text_parts=[
                str(paper.get("one_line_judgment") or paper.get("one_line") or "").strip(),
                str(paper.get("core_problem") or paper.get("problem") or "").strip(),
                str(paper.get("core_method") or paper.get("method") or "").strip(),
                str(paper.get("key_result") or paper.get("result") or "").strip(),
            ],
        )
        paper["topic_label"] = theme
        groups.setdefault(theme, []).append(paper)
    return [{"title": title, "papers": items} for title, items in groups.items() if items]


def _build_digest_properties(
    *,
    articles: list[ProcessedArticle],
    papers: list[dict[str, Any]],
    context: RenderContext,
) -> list[dict[str, str]]:
    keywords = _digest_keywords(articles=articles, papers=papers)
    tags = ["daily-papers", "paper-digest", "auto-generated"]
    theme_tags = [
        _slugify(str(item.get("title") or "").strip())
        for item in _build_theme_groups([dict(paper) for paper in papers])
    ]
    for tag in theme_tags[:2]:
        if tag and tag not in tags:
            tags.append(tag)
    properties: list[dict[str, str]] = []
    if context.date:
        properties.append({"label": "date", "value": context.date})
    if keywords:
        properties.append({"label": "keywords", "value": ", ".join(keywords)})
    properties.append({"label": "tags", "value": ", ".join(tags)})
    return properties


def _build_digest_frontmatter(properties: list[dict[str, str]]) -> dict[str, Any]:
    frontmatter: dict[str, Any] = {}
    for item in properties:
        label = str(item.get("label") or "").strip()
        value = str(item.get("value") or "").strip()
        if not label or not value:
            continue
        if label in {"keywords", "tags"}:
            frontmatter[label] = [part.strip() for part in value.split(",") if part.strip()]
        else:
            frontmatter[label] = value
    return frontmatter


def _digest_keywords(*, articles: list[ProcessedArticle], papers: list[dict[str, Any]]) -> list[str]:
    counter: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    ordinal = 0

    for article in articles:
        for raw_keyword in article.keywords or []:
            keyword = str(raw_keyword or "").strip().lower()
            if not keyword or keyword in _KEYWORD_STOPWORDS:
                continue
            if keyword not in first_seen:
                first_seen[keyword] = ordinal
                ordinal += 1
            counter[keyword] += 1

    for paper in papers:
        theme = str(paper.get("topic_label") or "").strip().lower()
        if not theme:
            continue
        if theme not in first_seen:
            first_seen[theme] = ordinal
            ordinal += 1
        counter[theme] += 1

    ranked = sorted(counter.items(), key=lambda item: (-item[1], first_seen[item[0]]))
    return [keyword for keyword, _ in ranked[:8]]


def _build_paper_note_report_from_payload(
    article: ProcessedArticle,
    *,
    context: RenderContext,
    parent_report_id: str | None = None,
    digest_title: str | None = None,
    note_payload: dict[str, Any],
) -> Report:
    identity = (
        str(note_payload.get("paper_identity") or build_paper_identity(article)).strip()
        or build_paper_identity(article)
    )
    slug = str(note_payload.get("paper_slug") or build_paper_slug(article)).strip() or build_paper_slug(article)
    title = str(note_payload.get("title") or _paper_title(article)).strip() or _paper_title(article)
    digest_title = digest_title or _digest_title(context)
    parent_link = build_paper_parent_link(parent_report_id=parent_report_id, digest_title=digest_title)
    summary = str(note_payload.get("summary") or "").strip() or _note_summary(article)
    contributions = _string_list(note_payload.get("core_contributions")) or _contributions(
        article,
        summary=summary,
    )
    problem_background = _string_list(note_payload.get("problem_background"))
    method_breakdown = _string_list(note_payload.get("method_breakdown")) or _method_details(
        article,
        summary=summary,
        contributions=contributions,
    )
    figure_notes = _string_list(note_payload.get("figure_notes"), max_items=8) or _figure_notes(article)
    experiments = _string_list(note_payload.get("experiments")) or _experiments(
        article,
        summary=summary,
        contributions=contributions,
        method_details=method_breakdown,
    )
    strengths = _string_list(note_payload.get("strengths")) or _strengths(
        article,
        summary=summary,
        contributions=contributions,
        method_details=method_breakdown,
        experiments=experiments,
    )
    limitations = _string_list(note_payload.get("limitations")) or _limitations(article)
    related_reading = _string_list(
        note_payload.get("related_reading"),
        max_items=8,
        max_len=160,
    ) or _related_reading(article)
    next_steps = _string_list(note_payload.get("next_steps"), max_items=6, max_len=180) or _next_steps(article)
    back_link = _note_back_link(parent_link)
    rendered = render_report_template(
        report_type="paper",
        version="v1",
        context={
            **_paper_mode_context("note"),
            "title": title,
            "authors": _display_list(note_payload.get("authors")) or _authors_text(article),
            "affiliations": _display_list(note_payload.get("affiliations")) or _affiliations_text(article),
            "links": _string_list(note_payload.get("links"), max_items=6, max_len=400) or _paper_links(article),
            "summary": summary,
            "core_contributions": contributions,
            "contributions": contributions,
            "problem_background": problem_background,
            "problem_statement": (
                problem_background[0] if problem_background else _problem_statement(article, summary=summary)
            ),
            "prior_limitations": (
                problem_background[1] if len(problem_background) > 1 else _prior_limitations(article)
            ),
            "motivation": (
                problem_background[2] if len(problem_background) > 2 else _motivation(article, summary=summary)
            ),
            "method_breakdown": method_breakdown,
            "method_details": method_breakdown,
            "figure_notes": figure_notes,
            "experiments": experiments,
            "strengths": strengths,
            "limitations": limitations,
            "next_steps": next_steps,
            "related_reading": related_reading,
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


def _string_list(raw: Any, *, max_items: int = 8, max_len: int = 200) -> list[str]:
    values = raw if isinstance(raw, list) else [raw]
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        text = text[:max_len]
        if text in output:
            continue
        output.append(text)
        if len(output) >= max_items:
            break
    return output


def _display_list(raw: Any) -> str:
    values = _string_list(raw, max_items=8, max_len=120)
    return "，".join(values)


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
    for key in ("figure_url", "figure", "image", "cover", "project_teaser_url"):
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
    return _digest_field_text([article.what, article.summary, article.detail])


def _method_text(article: ProcessedArticle) -> str:
    return _digest_field_text([article.detail, article.evidence, article.summary])


def _result_text(article: ProcessedArticle) -> str:
    return _digest_field_text([article.metrics, article.evidence, article.detail, article.summary])


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


def _link_items(raw_links: Any) -> list[dict[str, str]]:
    if isinstance(raw_links, list):
        values = raw_links
    else:
        values = [raw_links]
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_link in values:
        if isinstance(raw_link, dict):
            url = str(raw_link.get("url") or "").strip()
            label = str(raw_link.get("label") or "").strip() or _link_label(url)
        else:
            url = str(raw_link or "").strip()
            label = _link_label(url)
        if not url or url in seen:
            continue
        seen.add(url)
        items.append({"label": label, "url": url})
    return items


def _link_urls(items: list[dict[str, str]]) -> list[str]:
    return [str(item.get("url") or "").strip() for item in items if str(item.get("url") or "").strip()]


def _link_label(url: str) -> str:
    text = url.lower()
    if "arxiv.org/abs/" in text:
        return "Abs"
    if "arxiv.org/html/" in text:
        return "HTML"
    if "arxiv.org/pdf/" in text or text.endswith(".pdf"):
        return "PDF"
    if "github.com" in text:
        return "Code"
    if "project" in text or "demo" in text:
        return "Project"
    return "Link"


def _paper_source_label(links: list[str]) -> str:
    text = " ".join(str(link).lower() for link in links)
    if "arxiv.org" in text:
        return "arXiv"
    if "huggingface.co" in text:
        return "Hugging Face"
    if "openreview.net" in text:
        return "OpenReview"
    return "Paper"


def _infer_paper_topic(*, title: str, text_parts: list[str]) -> str:
    text = " ".join([title, *text_parts]).lower()
    if any(
        token in text
        for token in ("world model", "diffusion", "sim2real", "manipulation", "robot world")
    ):
        return "World Model"
    if any(
        token in text
        for token in (
            "prompt injection",
            "privacy",
            "pii",
            "security",
            "red-team",
            "red team",
            "deputy",
            "mitm",
            "vulnerable",
        )
    ):
        return "Safety"
    if any(token in text for token in ("benchmark", "evaluation", "eval", "critic", "reward", "planning")):
        return "Training & Evaluation"
    if any(
        token in text
        for token in ("gui", "computer-use", "computer using", "android", "mobile", "grounding", "screen")
    ):
        return "GUI Agent"
    return "Paper Picks"


def _digest_field_text(values: list[Any]) -> str:
    for value in values:
        fragments = _note_fragments(value)
        if not fragments:
            continue
        candidate = fragments[0].strip()
        if candidate:
            return candidate
    return ""


def _note_summary(article: ProcessedArticle) -> str:
    return _first_note_text([article.summary, article.what, article.detail])


def _contributions(article: ProcessedArticle, *, summary: str) -> list[str]:
    return _collect_note_points([article.what, article.evidence, article.summary], exclude=[summary], limit=3)


def _problem_statement(article: ProcessedArticle, *, summary: str) -> str:
    return _first_note_text([article.what, summary])


def _prior_limitations(article: ProcessedArticle) -> str:
    return _first_note_text([article.unknowns])


def _motivation(article: ProcessedArticle, *, summary: str) -> str:
    return _first_note_text([summary, article.detail], exclude=[_problem_statement(article, summary=summary)])


def _method_details(article: ProcessedArticle, *, summary: str, contributions: list[str]) -> list[str]:
    metadata = _article_metadata(article)
    return _collect_note_points(
        [metadata.get("method_summary"), article.detail],
        exclude=[summary, *contributions],
        limit=4,
    )


def _figure_notes(article: ProcessedArticle) -> list[str]:
    metadata = _article_metadata(article)
    notes: list[str] = []

    figure = _figure_url(article)
    figure_caption = _first_text(metadata.get("figure_caption")) or "Figure 1"
    if figure:
        notes.append(_render_figure_block(title=figure_caption, image_url=figure, source_label="arXiv HTML"))

    project_teaser = _first_text(metadata.get("project_teaser_url"))
    if project_teaser and project_teaser != figure:
        notes.append(
            _render_figure_block(
                title="Project Teaser",
                image_url=project_teaser,
                source_label="项目页 teaser",
            )
        )

    return notes


def _experiments(
    article: ProcessedArticle,
    *,
    summary: str,
    contributions: list[str],
    method_details: list[str],
) -> list[str]:
    return _collect_note_points(
        [article.metrics, article.evidence],
        exclude=[summary, *contributions, *method_details],
        limit=4,
    )


def _strengths(
    article: ProcessedArticle,
    *,
    summary: str,
    contributions: list[str],
    method_details: list[str],
    experiments: list[str],
) -> list[str]:
    return _collect_note_points(
        [article.summary, article.metrics],
        exclude=[summary, *contributions, *method_details, *experiments],
        limit=3,
    )


def _limitations(article: ProcessedArticle) -> list[str]:
    return _collect_note_points([article.unknowns], limit=3)


def _next_steps(article: ProcessedArticle) -> list[str]:
    metadata = _article_metadata(article)
    steps: list[str] = []
    if not _first_text(metadata.get("code_url")):
        steps.append("补查代码仓库、复现配置与许可证信息。")
    if not article.metrics:
        steps.append("补看正文中的主结果表与消融实验。")
    if not _figure_url(article) and not _first_text(metadata.get("project_teaser_url")):
        steps.append("补抓论文图示与项目页 teaser。")
    return _collect_note_points([steps], limit=3)


def _related_reading(article: ProcessedArticle) -> list[str]:
    return _collect_note_points([article.keywords], limit=6)


def _note_back_link(parent_link: dict[str, Any] | None) -> str:
    if not parent_link:
        return ""
    report_id = str(parent_link.get("report_id") or "").strip()
    title = str(parent_link.get("title") or "").strip()
    if report_id and title:
        return f"[{title}](/reports/{report_id})"
    return title


def _render_figure_block(*, title: str, image_url: str, source_label: str) -> str:
    return "\n\n".join(
        [
            f"### {title}",
            f"![{title}]({image_url})",
            f"图示来源：{source_label}",
        ]
    )


def _first_note_text(values: list[Any], *, exclude: list[str] | None = None) -> str:
    items = _collect_note_points(values, exclude=exclude, limit=1)
    return items[0] if items else ""


def _collect_note_points(values: list[Any], *, exclude: list[str] | None = None, limit: int | None = None) -> list[str]:
    points: list[str] = []
    seen = {_note_dedupe_key(item) for item in (exclude or []) if str(item).strip()}
    for value in values:
        for item in _note_fragments(value):
            key = _note_dedupe_key(item)
            if not key or key in seen:
                continue
            seen.add(key)
            points.append(item)
            if limit is not None and len(points) >= limit:
                return points
    return points


def _note_fragments(value: Any) -> list[str]:
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_note_fragments(item))
        return items
    if not isinstance(value, str):
        text = str(value or "").strip()
        return [text] if text else []

    text = value.strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, list):
            return _note_fragments(parsed)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) <= 1:
        cleaned = _strip_markdown_prefixes(text)
        return [cleaned] if cleaned else []

    fragments: list[str] = []
    for line in lines:
        cleaned = _strip_markdown_prefixes(line)
        if cleaned:
            fragments.append(cleaned)
    return fragments or [text]


def _note_dedupe_key(text: str) -> str:
    normalized = re.sub(r"[*`_#>\-]+", " ", str(text or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def _strip_markdown_prefixes(text: str) -> str:
    cleaned = re.sub(r"^[-*]\s+", "", str(text or "").strip())
    cleaned = re.sub(r"^>\s*", "", cleaned).strip()
    return cleaned


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

    for prefix in (
        "https://arxiv.org/abs/",
        "https://arxiv.org/pdf/",
        "http://arxiv.org/abs/",
        "http://arxiv.org/pdf/",
        "arxiv:",
    ):
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
