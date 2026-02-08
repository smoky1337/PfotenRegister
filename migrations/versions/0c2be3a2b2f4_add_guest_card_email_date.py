"""add guest card emailed date

Revision ID: 0c2be3a2b2f4
Revises: ff2cac1d9c0d
Create Date: 2025-11-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0c2be3a2b2f4"
down_revision: Union[str, None] = "0a3d1bcf0d28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("guests", sa.Column("guest_card_emailed_on", sa.Date(), nullable=True))
    pass


def downgrade() -> None:
    op.drop_column("guests", "guest_card_emailed_on")
