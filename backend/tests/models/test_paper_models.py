from __future__ import annotations

from app.models.paper import Paper, PaperAsset, PaperContent, PaperIdentifier


def test_paper_model_has_expected_columns_and_defaults() -> None:
    table = Paper.__table__

    for column_name in (
        "normalized_title",
        "best_landing_url",
        "best_pdf_url",
        "fulltext_status",
        "best_content_id",
        "metadata",
    ):
        assert column_name in table.c

    assert table.c.fulltext_status.default is not None
    assert table.c.fulltext_status.default.arg == "missing"


def test_paper_identifier_has_global_unique_constraint() -> None:
    table = PaperIdentifier.__table__

    unique_constraints = {tuple(column.name for column in constraint.columns) for constraint in table.constraints}
    assert ("scheme", "normalized_value") in unique_constraints


def test_paper_asset_and_content_models_capture_status_columns() -> None:
    asset_table = PaperAsset.__table__
    content_table = PaperContent.__table__

    assert asset_table.c.fetch_status.default is not None
    assert asset_table.c.fetch_status.default.arg == "pending"
    assert content_table.c.extraction_status.default is not None
    assert content_table.c.extraction_status.default.arg == "pending"
    assert content_table.c.format.default is not None
    assert content_table.c.format.default.arg == "markdown"
