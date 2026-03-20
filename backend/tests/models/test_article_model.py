from __future__ import annotations

from app.models.article import Article


def test_article_model_exposes_paper_link_and_content_type_defaults() -> None:
    table = Article.__table__

    assert "paper_id" in table.c
    assert "content_type" in table.c
    assert table.c.paper_id.nullable is True
    assert table.c.content_type.nullable is False
    assert table.c.content_type.default is not None
    assert table.c.content_type.default.arg == "metadata"
