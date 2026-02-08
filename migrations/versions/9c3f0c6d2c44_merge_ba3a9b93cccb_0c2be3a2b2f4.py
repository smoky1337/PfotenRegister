"""Merge heads ba3a9b93cccb and 0c2be3a2b2f4.

Revision ID: 9c3f0c6d2c44
Revises: ba3a9b93cccb, 0c2be3a2b2f4
Create Date: 2025-12-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c3f0c6d2c44"
down_revision: Union[str, None] = ("ba3a9b93cccb", "0c2be3a2b2f4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
