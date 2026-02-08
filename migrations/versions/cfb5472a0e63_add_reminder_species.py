"""Add reminder_species column

Revision ID: cfb5472a0e63
Revises: 7be2dfc3ab7a
Create Date: 2025-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cfb5472a0e63"
down_revision: Union[str, None] = "7be2dfc3ab7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("field_registry", sa.Column("reminder_species", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("field_registry", "reminder_species")

