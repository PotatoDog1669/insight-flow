"""replace depth with report_type on reports and monitors

Revision ID: 20260302_0005
Revises: 20260302_0004
Create Date: 2026-03-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260302_0005"
down_revision = "20260302_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("report_type", sa.String(length=16), nullable=True))
    op.add_column("monitors", sa.Column("report_type", sa.String(length=16), nullable=True))

    op.execute(
        """
        UPDATE reports
        SET report_type = CASE
            WHEN time_period = 'weekly' THEN 'weekly'
            ELSE 'daily'
        END
        """
    )
    op.execute(
        """
        UPDATE monitors
        SET report_type = CASE
            WHEN time_period = 'weekly' THEN 'weekly'
            WHEN time_period = 'daily' THEN 'daily'
            ELSE 'daily'
        END
        """
    )

    op.alter_column("reports", "report_type", existing_type=sa.String(length=16), nullable=False)
    op.alter_column("monitors", "report_type", existing_type=sa.String(length=16), nullable=False)

    op.drop_index("idx_reports_dimensions", table_name="reports")
    op.create_index("idx_reports_dimensions", "reports", ["time_period", "report_type"], unique=False)

    op.drop_column("reports", "depth")
    op.drop_column("monitors", "depth")


def downgrade() -> None:
    op.add_column("reports", sa.Column("depth", sa.String(length=16), nullable=True))
    op.add_column("monitors", sa.Column("depth", sa.String(length=16), nullable=True))

    op.execute(
        """
        UPDATE reports
        SET depth = CASE
            WHEN report_type = 'daily' THEN 'brief'
            ELSE 'deep'
        END
        """
    )
    op.execute(
        """
        UPDATE monitors
        SET depth = CASE
            WHEN report_type = 'daily' THEN 'brief'
            ELSE 'deep'
        END
        """
    )

    op.alter_column("reports", "depth", existing_type=sa.String(length=16), nullable=False)
    op.alter_column("monitors", "depth", existing_type=sa.String(length=16), nullable=False)

    op.drop_index("idx_reports_dimensions", table_name="reports")
    op.create_index("idx_reports_dimensions", "reports", ["time_period", "depth"], unique=False)

    op.drop_column("reports", "report_type")
    op.drop_column("monitors", "report_type")
