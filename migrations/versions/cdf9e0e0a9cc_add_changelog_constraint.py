"""add changelog constraint

Revision ID: cdf9e0e0a9cc
Revises: b44cf1a07429
Create Date: 2025-07-09 10:07:21.412077

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cdf9e0e0a9cc'
down_revision: Union[str, None] = 'b44cf1a07429'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key("FK_changelog_guests", 'changelog', 'guests', ['guest_id'], ['id'])
    pass


def downgrade() -> None:
    op.drop_constraint("FK_changelog_guests", 'changelog', type_='foreignkey')

    pass
