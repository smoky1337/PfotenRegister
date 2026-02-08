"""extend locations with more types and dispense flags

Revision ID: ba3a9b93cccb
Revises: 5c5c1a5d7de4
Create Date: 2025-08-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ba3a9b93cccb"
down_revision: Union[str, None] = "5c5c1a5d7de4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


location_enum_old = sa.Enum("dropbox", "donationbox", name="location_type")
location_enum_new = sa.Enum("dropbox", "donationbox", "office", "storage", "dispense", name="location_type")


def upgrade() -> None:
    bind = op.get_bind()
    location_enum_new.create(bind, checkfirst=True)
    op.alter_column(
        "drop_off_locations",
        "location_type",
        existing_type=location_enum_old,
        type_=location_enum_new,
        existing_nullable=False,
    )

    op.add_column("drop_off_locations", sa.Column("is_dispense_location", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("guests", sa.Column("dispense_location_id", sa.Integer(), nullable=True))
    op.add_column("food_history", sa.Column("location_id", sa.Integer(), nullable=True))

    op.create_index(op.f("ix_guests_dispense_location_id"), "guests", ["dispense_location_id"], unique=False)
    op.create_index(op.f("ix_food_history_location_id"), "food_history", ["location_id"], unique=False)
    op.create_foreign_key("fk_guests_dispense_location", "guests", "drop_off_locations", ["dispense_location_id"], ["id"])
    op.create_foreign_key("fk_food_history_location_id", "food_history", "drop_off_locations", ["location_id"], ["id"])

    op.alter_column("drop_off_locations", "is_dispense_location", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_food_history_location_id", "food_history", type_="foreignkey")
    op.drop_constraint("fk_guests_dispense_location", "guests", type_="foreignkey")
    op.drop_index(op.f("ix_food_history_location_id"), table_name="food_history")
    op.drop_index(op.f("ix_guests_dispense_location_id"), table_name="guests")

    op.drop_column("food_history", "location_id")
    op.drop_column("guests", "dispense_location_id")
    op.drop_column("drop_off_locations", "is_dispense_location")

    bind = op.get_bind()
    location_enum_old.create(bind, checkfirst=True)
    op.alter_column(
        "drop_off_locations",
        "location_type",
        existing_type=location_enum_new,
        type_=location_enum_old,
        existing_nullable=False,
    )
