"""add food plans

Revision ID: 4b2c7f6e9a1d
Revises: ba3a9b93cccb
Create Date: 2026-01-09 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4b2c7f6e9a1d"
down_revision: Union[str, None] = "9c3f0c6d2c44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "food_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column(
            "mode",
            sa.Enum("guest_view", "type_view", name="food_plan_mode"),
            nullable=False,
            server_default="guest_view",
        ),
        sa.Column("general_note", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_on",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_on",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_food_plans_created_by_id",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["drop_off_locations.id"],
            name="fk_food_plans_location_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_food_plans_created_by_id"), "food_plans", ["created_by_id"], unique=False)
    op.create_index(op.f("ix_food_plans_location_id"), "food_plans", ["location_id"], unique=False)

    op.create_table(
        "food_plan_guests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("food_plan_id", sa.Integer(), nullable=False),
        sa.Column("guest_id", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["food_plan_id"],
            ["food_plans.id"],
            name="fk_food_plan_guests_food_plan_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["guest_id"],
            ["guests.id"],
            name="fk_food_plan_guests_guest_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("food_plan_id", "guest_id", name="uq_food_plan_guests"),
    )
    op.create_index(op.f("ix_food_plan_guests_food_plan_id"), "food_plan_guests", ["food_plan_id"], unique=False)
    op.create_index(op.f("ix_food_plan_guests_guest_id"), "food_plan_guests", ["guest_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_food_plan_guests_guest_id"), table_name="food_plan_guests")
    op.drop_index(op.f("ix_food_plan_guests_food_plan_id"), table_name="food_plan_guests")
    op.drop_table("food_plan_guests")

    op.drop_index(op.f("ix_food_plans_location_id"), table_name="food_plans")
    op.drop_index(op.f("ix_food_plans_created_by_id"), table_name="food_plans")
    op.drop_table("food_plans")
