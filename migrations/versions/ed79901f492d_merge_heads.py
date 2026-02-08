"""merge heads

Revision ID: ed79901f492d
Revises: 8c2d7b4a9e1f, b5f198fa3046
Create Date: 2026-02-08 22:52:42.837868

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ed79901f492d'
down_revision: Union[str, None] = ('8c2d7b4a9e1f', 'b5f198fa3046')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
