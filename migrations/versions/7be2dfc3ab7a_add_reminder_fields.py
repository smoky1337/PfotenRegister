"""Add reminder metadata to FieldRegistry

Revision ID: 7be2dfc3ab7a
Revises: 21fa94f79d22
Create Date: 2025-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7be2dfc3ab7a"
down_revision: Union[str, None] = "21fa94f79d22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "field_registry",
        sa.Column("remindable", sa.Boolean(), nullable=True, server_default=sa.text("0")),
    )
    op.add_column(
        "field_registry",
        sa.Column("reminder_interval_days", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("field_registry", "reminder_interval_days")
    op.drop_column("field_registry", "remindable")

