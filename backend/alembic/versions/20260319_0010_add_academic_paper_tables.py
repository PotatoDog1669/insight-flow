"""add academic paper tables

Revision ID: 20260319_0010
Revises: 20260304_0009
Create Date: 2026-03-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260319_0010"
down_revision = "20260304_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "papers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("normalized_title", sa.String(length=512), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("venue", sa.String(length=256), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("first_author", sa.String(length=256), nullable=True),
        sa.Column("best_landing_url", sa.Text(), nullable=True),
        sa.Column("best_pdf_url", sa.Text(), nullable=True),
        sa.Column("fulltext_status", sa.String(length=16), nullable=False, server_default="missing"),
        sa.Column("best_content_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_papers_normalized_title", "papers", ["normalized_title"], unique=False)

    op.create_table(
        "paper_identifiers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("paper_id", sa.Uuid(), nullable=False),
        sa.Column("scheme", sa.String(length=32), nullable=False),
        sa.Column("value", sa.String(length=512), nullable=False),
        sa.Column("normalized_value", sa.String(length=512), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scheme", "normalized_value", name="idx_paper_identifiers_scheme_value"),
    )
    op.create_index("idx_paper_identifiers_paper_id", "paper_identifiers", ["paper_id"], unique=False)

    op.create_table(
        "paper_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("paper_id", sa.Uuid(), nullable=False),
        sa.Column("asset_type", sa.String(length=16), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("resolved_url", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("fetch_status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paper_id", "checksum", name="idx_paper_assets_paper_checksum"),
    )
    op.create_index("idx_paper_assets_checksum", "paper_assets", ["checksum"], unique=False)
    op.create_index("idx_paper_assets_paper_id", "paper_assets", ["paper_id"], unique=False)

    op.create_table(
        "paper_contents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("paper_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("content_tier", sa.String(length=16), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False, server_default="markdown"),
        sa.Column("markdown_content", sa.Text(), nullable=True),
        sa.Column("plain_text", sa.Text(), nullable=True),
        sa.Column("sections_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("converter_name", sa.String(length=64), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("extraction_status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["asset_id"], ["paper_assets.id"]),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_paper_contents_asset_id", "paper_contents", ["asset_id"], unique=False)
    op.create_index("idx_paper_contents_paper_id", "paper_contents", ["paper_id"], unique=False)

    op.add_column("articles", sa.Column("paper_id", sa.Uuid(), nullable=True))
    op.add_column(
        "articles",
        sa.Column("content_type", sa.String(length=16), nullable=False, server_default="metadata"),
    )
    op.create_foreign_key("fk_articles_paper_id_papers", "articles", "papers", ["paper_id"], ["id"])
    op.create_index("ix_articles_paper_id", "articles", ["paper_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_articles_paper_id", table_name="articles")
    op.drop_constraint("fk_articles_paper_id_papers", "articles", type_="foreignkey")
    op.drop_column("articles", "content_type")
    op.drop_column("articles", "paper_id")

    op.drop_index("idx_paper_contents_paper_id", table_name="paper_contents")
    op.drop_index("idx_paper_contents_asset_id", table_name="paper_contents")
    op.drop_table("paper_contents")

    op.drop_index("idx_paper_assets_paper_id", table_name="paper_assets")
    op.drop_index("idx_paper_assets_checksum", table_name="paper_assets")
    op.drop_table("paper_assets")

    op.drop_index("idx_paper_identifiers_paper_id", table_name="paper_identifiers")
    op.drop_table("paper_identifiers")

    op.drop_index("idx_papers_normalized_title", table_name="papers")
    op.drop_table("papers")
