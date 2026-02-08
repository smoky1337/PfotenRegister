"""complete_care

Revision ID: 35580c9c7eac
Revises: e1f46d367a5d
Create Date: 2025-07-10 10:05:57.138805

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35580c9c7eac'
down_revision: Union[str, None] = 'e1f46d367a5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Create enum type
    completecare_enum = sa.Enum('Ja', 'Nein', 'Unbekannt', name='completecareenum')
    completecare_enum.create(op.get_bind())

    # Step 2: Add new temporary column
    op.add_column('animals', sa.Column('complete_care_tmp', completecare_enum, server_default='Unbekannt'))

    # Step 3: Migrate data from old column to new enum column
    op.execute("""
               UPDATE animals
               SET complete_care_tmp =
                       CASE LOWER(complete_care)
                           WHEN 'ja' THEN 'Ja'
                           WHEN 'nein' THEN 'Nein'
                           WHEN 'unbekannt' THEN 'Unbekannt'
                           ELSE 'Unbekannt'
                           END
               """)

    # Step 4: Drop old column
    op.drop_column('animals', 'complete_care')

    # Step 5: Rename tmp column to final name
    op.alter_column('animals', 'complete_care_tmp', existing_type=completecare_enum,new_column_name='complete_care')


def downgrade() -> None:
    # Step 1: Add text column to hold original values
    op.add_column('animals', sa.Column('complete_care_tmp', sa.Enum('ja', 'nein', 'unbekannt'),default='unbekannt'))

    # Step 2: Migrate values back to string
    op.execute("""
        UPDATE animals
        SET complete_care_tmp =
            CASE complete_care
                WHEN 'Ja' THEN 'ja'
                WHEN 'Nein' THEN 'nein'
                WHEN 'Unbekannt' THEN 'unbekannt'
                ELSE 'unbekannt'
            END
    """)

    # Step 3: Drop enum column
    op.drop_column('animals', 'complete_care')

    # Step 4: Rename tmp column to original
    op.alter_column('animals', 'complete_care_tmp', new_column_name='complete_care')

    # Step 5: Drop enum type
    completecare_enum = sa.Enum('Ja', 'Nein', 'Unbekannt', name='completecareenum')
    completecare_enum.drop(op.get_bind())
