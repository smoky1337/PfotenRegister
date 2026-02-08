"""remaining dbs

Revision ID: b44cf1a07429
Revises: 1f719c236b66
Create Date: 2025-07-07 15:57:26.529776

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b44cf1a07429'
down_revision: Union[str, None] = '1f719c236b66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table('futterhistorie', "food_history")
    with op.batch_alter_table('food_history') as batch_op:
        batch_op.alter_column("entry_id", new_column_name="id", type_=sa.Integer())
        batch_op.alter_column("gast_id", new_column_name="guest_id", type_=sa.String(length=255))
        batch_op.alter_column("futtertermin", new_column_name="distributed_on", type_=sa.Date())
        batch_op.alter_column("notiz", new_column_name="comment", type_=sa.Text())
    op.create_foreign_key("FK_food_guests", 'food_history', 'guests', ['guest_id'], ['id'], ondelete='CASCADE')

    op.rename_table('zahlungshistorie', "payments")
    with op.batch_alter_table('payments') as batch_op:
        batch_op.alter_column("gast_id", new_column_name="guest_id", type_=sa.String(length=255))
        batch_op.alter_column("zahlungstag", new_column_name="paid_on", type_=sa.Date())
        batch_op.alter_column("futter_betrag", new_column_name="food_amount", type_=sa.Float())
        batch_op.alter_column("zubehoer_betrag", new_column_name="other_amount", type_=sa.Float())
        batch_op.alter_column("kommentar", new_column_name="comment", type_=sa.Text())
        batch_op.alter_column("erstellt_am", new_column_name="created_at", server_default=sa.text('CURRENT_TIMESTAMP'), type_=sa.Date())
        batch_op.alter_column("payment_open", new_column_name="paid", existing_server_default=False,
                              server_default=sa.text('1'), type_=sa.Boolean())
    op.create_foreign_key("FK_payment_guests", 'payments', 'guests', ['guest_id'], ['id'], ondelete='CASCADE')

    op.rename_table('einstellungen', "settings")

    op.create_table('visible_fields',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('model_name', sa.String(length=255), nullable=False),
                    sa.Column('field_name', sa.String(length=255), nullable=False),
                    sa.Column('is_visible', sa.Boolean(), nullable=False),
                    sa.Column('label', sa.String(length=255), nullable=True),
                    sa.PrimaryKeyConstraint('id')
                    )

    with op.batch_alter_table('changelog') as batch_op:
        batch_op.alter_column('gast_id', new_column_name="guest_id", type_=sa.String(length=255))

    op.add_column('changelog', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_foreign_key("FK_changelog_users", 'changelog', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint("FK_changelog_users", 'changelog', type_='foreignkey')
    op.drop_column('changelog', 'user_id')
    with op.batch_alter_table('changelog') as batch_op:
        batch_op.alter_column("guest_id", new_column_name="gast_id")

    op.drop_table('visible_fields')

    op.rename_table("settings", 'einstellungen')

    op.drop_constraint("FK_payment_guests", 'payments', type_='foreignkey')
    with op.batch_alter_table('payments') as batch_op:
        batch_op.alter_column("guest_id", new_column_name="gast_id", type_=sa.String(length=255))
        batch_op.alter_column("paid_on", new_column_name="zahlungstag", type_=sa.Date())
        batch_op.alter_column("food_amount", new_column_name="futter_betrag", type_=sa.Float())
        batch_op.alter_column("other_amount", new_column_name="zubehoer_betrag", type_=sa.Float())
        batch_op.alter_column("comment", new_column_name="kommentar", type_=sa.Text())
        batch_op.alter_column("created_at", new_column_name="erstellt_am", server_default=None, type_=sa.Date())
        batch_op.alter_column("paid", new_column_name="payment_open", server_default=None, type_=sa.Boolean())
    op.rename_table("payments", 'zahlungshistorie')

    op.drop_constraint("FK_food_guests", 'food_history', type_='foreignkey')
    with op.batch_alter_table('food_history') as batch_op:
        batch_op.alter_column("id", new_column_name="entry_id", type_=sa.Integer())
        batch_op.alter_column("guest_id", new_column_name="gast_id", type_=sa.String(length=255))
        batch_op.alter_column("distributed_on", new_column_name="futtertermin", type_=sa.Date())
        batch_op.alter_column("comment", new_column_name="notiz", type_=sa.Text())
    op.rename_table("food_history", 'futterhistorie')
