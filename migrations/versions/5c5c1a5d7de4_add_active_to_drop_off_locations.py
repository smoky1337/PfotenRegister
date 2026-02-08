"""add active flag to drop_off_locations

Revision ID: 5c5c1a5d7de4
Revises: 0c2be3a2b2f4
Create Date: 2025-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5c5c1a5d7de4"
down_revision: Union[str, None] = "0a3d1bcf0d28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("drop_off_locations", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")))


def downgrade() -> None:

    op.drop_column("drop_off_locations", "active")
