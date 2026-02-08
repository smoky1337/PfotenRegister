"""add drop off locations table

Revision ID: 0a3d1bcf0d28
Revises: cfb5472a0e63
Create Date: 2025-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0a3d1bcf0d28"
down_revision: Union[str, None] = "cfb5472a0e63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "drop_off_locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("location_type", sa.Enum("dropbox", "donationbox", name="location_type"), nullable=False, server_default="dropbox"),
        sa.Column("responsible_person", sa.String(length=255), nullable=True),
        sa.Column("last_emptied", sa.Date(), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("created_on", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_on", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("drop_off_locations")
