"""add payment packages

Revision ID: 2d6c9b5e8a10
Revises: c41d5a1f0c29
Create Date: 2026-05-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2d6c9b5e8a10"
down_revision: Union[str, None] = "c41d5a1f0c29"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_packages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "category",
            sa.Enum("food", "others", name="payment_package_category"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_on", sa.DateTime(), nullable=False),
        sa.Column("updated_on", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payment_packages_active"), "payment_packages", ["active"], unique=False)
    op.create_index(op.f("ix_payment_packages_category"), "payment_packages", ["category"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_payment_packages_category"), table_name="payment_packages")
    op.drop_index(op.f("ix_payment_packages_active"), table_name="payment_packages")
    op.drop_table("payment_packages")
    sa.Enum(name="payment_package_category").drop(op.get_bind(), checkfirst=False)
