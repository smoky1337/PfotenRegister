"""Clean Up 2

Revision ID: b6a32da6a007
Revises: ff2cac1d9c0d
Create Date: 2025-07-09 17:27:29.953163

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'b6a32da6a007'
down_revision: Union[str, None] = 'ff2cac1d9c0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Drop FKs
    op.drop_constraint('animals_ibfk_1', 'animals', type_='foreignkey')

    op.drop_constraint('fk_animals_guest_id', 'animals', type_='foreignkey')

    # Step 2: Drop index
    op.drop_index('gast_id', table_name='animals')

    # Step 3: Recreate with better name
    op.create_index('ix_animals_guest_id', 'animals', ['guest_id'])

    # Step 4: Recreate FK
    op.create_foreign_key(
        'fk_animals_guest_id',
        source_table='animals',
        referent_table='guests',
        local_cols=['guest_id'],
        remote_cols=['id'],
        ondelete='CASCADE'
    )

    # ### end Alembic commands ###


def downgrade() -> None:
    op.drop_constraint('fk_animals_guest_id', 'animals', type_='foreignkey')
    op.drop_index('ix_animals_guest_id', table_name='animals')
    op.create_index('gast_id', 'animals', ['guest_id'])
    op.create_foreign_key('animals_ibfk_1', 'animals', 'guests', ['guest_id'], ['id'])
    op.create_foreign_key('fk_animals_guest_id', 'animals', 'guests', ['guest_id'], ['id'], ondelete='CASCADE')
