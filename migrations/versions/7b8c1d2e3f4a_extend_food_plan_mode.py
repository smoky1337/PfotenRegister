"""extend food plan mode

Revision ID: 7b8c1d2e3f4a
Revises: 2f7c1a9d0b4e
Create Date: 2026-01-09 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7b8c1d2e3f4a"
down_revision: Union[str, None] = "2f7c1a9d0b4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


mode_enum_old = sa.Enum("guest_view", "type_view", name="food_plan_mode")
mode_enum_new = sa.Enum("guest_view", "type_view", "type_summary", name="food_plan_mode")


def upgrade() -> None:
    bind = op.get_bind()
    mode_enum_new.create(bind, checkfirst=True)
    op.alter_column(
        "food_plans",
        "mode",
        existing_type=mode_enum_old,
        type_=mode_enum_new,
        existing_nullable=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    mode_enum_old.create(bind, checkfirst=True)
    op.alter_column(
        "food_plans",
        "mode",
        existing_type=mode_enum_new,
        type_=mode_enum_old,
        existing_nullable=False,
    )

