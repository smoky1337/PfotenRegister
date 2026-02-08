"""enum_gender

Revision ID: f46862514135
Revises: 43a6160c0e2f
Create Date: 2025-07-09 17:57:35.029155

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'f46862514135'
down_revision: Union[str, None] = '43a6160c0e2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new column with corrected ENUM
    op.add_column('guests', sa.Column('gender_tmp', sa.Enum('Frau', 'Mann', 'Divers','Unbekannt')))

    # 2. Copy data from old to new, converting text case
    op.execute("""
               UPDATE guests
               SET gender_tmp =
                       CASE LOWER(gender)
                           WHEN 'male' THEN 'Frau'
                           WHEN 'female' THEN 'Mann'
                           WHEN 'other' THEN 'Divers'
                           ELSE 'Unbekannt'
                       END
               """)

    # 3. Drop old column
    op.drop_column('guests', 'gender')

    # 4. Rename new column
    op.alter_column('guests', 'gender_tmp', new_column_name='gender',
                    existing_type=sa.Enum('Frau', 'Mann', 'Divers','Unbekannt'))



def downgrade() -> None:
    # 1. Add temp column with old ENUM values
    op.add_column('guests', sa.Column('gender_tmp', sa.Enum('male', 'female', 'other', 'unknown')))

    # 2. Copy values back with reversed case logic
    op.execute("""
        UPDATE guests
        SET gender_tmp = 
            CASE LOWER(gender)
                WHEN 'frau' THEN 'female'
                WHEN 'mann' THEN 'male'
                WHEN 'divers' THEN 'other'
                ELSE 'unknown'
            END
    """)

    # 3. Drop current gender column
    op.drop_column('guests', 'gender')

    # 4. Rename tmp column back to gender
    op.alter_column('guests', 'gender_tmp', new_column_name='gender',
                    existing_type=sa.Enum('male', 'female', 'other', 'unknown'))
