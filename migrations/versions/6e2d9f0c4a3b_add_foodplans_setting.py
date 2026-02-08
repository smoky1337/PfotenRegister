"""add foodplans setting

Revision ID: 6e2d9f0c4a3b
Revises: 4b2c7f6e9a1d
Create Date: 2026-01-09 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6e2d9f0c4a3b"
down_revision: Union[str, None] = "4b2c7f6e9a1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO settings (setting_key, value, description)
            SELECT 'foodplans', 'Aktiv', 'Futterpläne'
            WHERE NOT EXISTS (
                SELECT 1 FROM settings WHERE setting_key = 'foodplans'
            )
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM settings WHERE setting_key = 'foodplans'"))

