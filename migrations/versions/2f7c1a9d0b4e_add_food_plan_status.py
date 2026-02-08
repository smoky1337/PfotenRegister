"""add food plan status

Revision ID: 2f7c1a9d0b4e
Revises: 6e2d9f0c4a3b
Create Date: 2026-01-09 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2f7c1a9d0b4e"
down_revision: Union[str, None] = "6e2d9f0c4a3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "food_plans",
        sa.Column(
            "status",
            sa.Enum("Planen", "Packen", "Gepackt", "Fertig", name="food_plan_status"),
            nullable=False,
            server_default="Planen",
        ),
    )
    op.alter_column("food_plans", "status", server_default=None)


def downgrade() -> None:
    op.drop_column("food_plans", "status")
    try:
        sa.Enum(name="food_plan_status").drop(op.get_bind(), checkfirst=True)
    except Exception:
        pass

