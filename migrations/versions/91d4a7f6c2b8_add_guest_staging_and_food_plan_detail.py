"""add guest staging and food plan detail view

Revision ID: 91d4a7f6c2b8
Revises: 2d6c9b5e8a10
Create Date: 2026-05-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "91d4a7f6c2b8"
down_revision: Union[str, None] = "2d6c9b5e8a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


mode_enum_old = sa.Enum("guest_view", "type_view", "type_summary", name="food_plan_mode")
mode_enum_new = sa.Enum("guest_view", "detail_view", "type_view", "type_summary", name="food_plan_mode")


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

    op.add_column(
        "guests",
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False, server_default="active"),
    )
    op.execute("UPDATE guests SET lifecycle_status = CASE WHEN status = 1 THEN 'active' ELSE 'inactive' END")
    op.create_index(op.f("ix_guests_lifecycle_status"), "guests", ["lifecycle_status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("UPDATE food_plans SET mode = 'guest_view' WHERE mode = 'detail_view'")
    mode_enum_old.create(bind, checkfirst=True)
    op.alter_column(
        "food_plans",
        "mode",
        existing_type=mode_enum_new,
        type_=mode_enum_old,
        existing_nullable=False,
    )

    op.drop_index(op.f("ix_guests_lifecycle_status"), table_name="guests")
    op.drop_column("guests", "lifecycle_status")
