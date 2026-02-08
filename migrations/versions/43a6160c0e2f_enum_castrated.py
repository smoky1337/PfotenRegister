"""enum_castrated

Revision ID: 43a6160c0e2f
Revises: d9d5662de244
Create Date: 2025-07-09 17:53:52.840018

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '43a6160c0e2f'
down_revision: Union[str, None] = 'd9d5662de244'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    # 1. Add new column with corrected ENUM
    op.add_column('animals', sa.Column('castrated_tmp', sa.Enum('Ja', 'Nein', 'Unbekannt'), nullable=True))

    # 2. Copy data from old to new, converting text case
    op.execute("""
               UPDATE animals
               SET castrated_tmp =
                       CASE LOWER(castrated)
                           WHEN 'ja' THEN 'Ja'
                           WHEN 'nein' THEN 'Nein'
                           ELSE 'Unbekannt'
                           END
               """)

    # 3. Drop old column
    op.drop_column('animals', 'castrated')

    # 4. Rename new column
    op.alter_column('animals', 'castrated_tmp', new_column_name='castrated', existing_type=sa.Enum('Ja', 'Nein', 'Unbekannt'))


def downgrade():
    op.add_column('animals', sa.Column('castrated_old', sa.Enum('ja', 'nein', 'unbekannt'), nullable=True))

    op.execute("""
        UPDATE animals
        SET castrated_old = 
            CASE castrated
                WHEN 'Ja' THEN 'ja'
                WHEN 'Nein' THEN 'nein'
                ELSE 'unbekannt'
            END
    """)

    op.drop_column('animals', 'castrated')
    op.alter_column('animals', 'castrated_old', new_column_name='castrated', existing_type=sa.Enum('ja', 'nein', 'unbekannt'))
