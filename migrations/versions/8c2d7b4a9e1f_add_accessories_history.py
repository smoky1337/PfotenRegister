"""add accessories history

Revision ID: 8c2d7b4a9e1f
Revises: 7b8c1d2e3f4a
Create Date: 2026-02-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8c2d7b4a9e1f"
down_revision: Union[str, None] = "7b8c1d2e3f4a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "accessories_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guest_id", sa.String(length=255), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("distributed_on", sa.Date(), nullable=True),
        sa.Column("item", sa.String(length=255), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["guest_id"], ["guests.id"], name="fk_accessories_history_guest_id"),
        sa.ForeignKeyConstraint(["location_id"], ["drop_off_locations.id"], name="fk_accessories_history_location_id"),
    )
    op.create_index("ix_accessories_history_guest_id", "accessories_history", ["guest_id"])
    op.create_index("ix_accessories_history_location_id", "accessories_history", ["location_id"])
    op.create_index("ix_accessories_history_distributed_on", "accessories_history", ["distributed_on"])


def downgrade() -> None:
    op.drop_index("ix_accessories_history_distributed_on", table_name="accessories_history")
    op.drop_index("ix_accessories_history_location_id", table_name="accessories_history")
    op.drop_index("ix_accessories_history_guest_id", table_name="accessories_history")
    op.drop_table("accessories_history")
