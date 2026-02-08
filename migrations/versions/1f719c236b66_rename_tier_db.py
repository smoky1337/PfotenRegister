"""rename tier db

Revision ID: 1f719c236b66
Revises: e6fbf57cdeb7
Create Date: 2025-07-07 15:52:57.562173

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f719c236b66'
down_revision: Union[str, None] = 'e6fbf57cdeb7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("tiere", "animals")
    op.add_column('animals', sa.Column('status_temp', sa.Boolean(), server_default=sa.text('1'), nullable=False))
    op.execute("""
               UPDATE animals
               SET status_temp = CASE
                                     WHEN active = 'Aktiv' THEN TRUE
                                     WHEN active = 'Inaktiv' THEN FALSE
                                     ELSE FALSE
                   END
               """)
    with op.batch_alter_table('animals') as batch_op:
        batch_op.alter_column('gast_id', new_column_name='guest_id', existing_type=sa.String(length=255))
        batch_op.alter_column('art', new_column_name='species', existing_type=sa.Enum('Hund', 'Katze', 'Vogel', 'Nager', 'Sonstige', 'Unbekannt'))
        batch_op.alter_column('rasse', new_column_name='breed', existing_type=sa.String(length=100))
        batch_op.alter_column('geschlecht', new_column_name='sex', existing_type=sa.Enum('M', 'F', 'Unbekannt'))
        batch_op.alter_column('farbe', new_column_name='color', existing_type=sa.String(length=100))
        batch_op.alter_column('kastriert', new_column_name='castrated', existing_type=sa.Enum('ja', 'nein', 'unbekannt'))
        batch_op.alter_column('identifikation', new_column_name='identification', existing_type=sa.String(length=100))
        batch_op.alter_column('geburtsdatum', new_column_name='birthdate', existing_type=sa.Date())
        batch_op.alter_column('gewicht_oder_groesse', new_column_name='weight_or_size', existing_type=sa.String(length=50))
        batch_op.alter_column('krankheiten', new_column_name='illnesses', existing_type=sa.Text())
        batch_op.alter_column('unvertraeglichkeiten', new_column_name='allergies', existing_type=sa.Text())
        batch_op.alter_column('futter', new_column_name='food_type', existing_type=sa.Enum('Misch', 'Trocken', 'Nass', 'Barf'))
        batch_op.alter_column('vollversorgung', new_column_name='complete_care', existing_type=sa.Enum('ja', 'nein', 'unbekannt'))
        batch_op.alter_column('zuletzt_gesehen', new_column_name='last_seen', existing_type=sa.Date())
        batch_op.alter_column('tierarzt', new_column_name='veterinarian', existing_type=sa.String(length=255))
        batch_op.alter_column('futtermengeneintrag', new_column_name='food_amount_note', existing_type=sa.Text())
        batch_op.alter_column('notizen', new_column_name='note', existing_type=sa.Text())
        batch_op.alter_column('erstellt_am', new_column_name='created_at', existing_type=sa.Date(), server_default=sa.text('CURRENT_TIMESTAMP'))
        batch_op.alter_column('aktualisiert_am', new_column_name='updated_at', existing_type=sa.Date())
        batch_op.drop_column('active')
        batch_op.alter_column('status_temp', new_column_name='status', existing_type=sa.Boolean())
        batch_op.alter_column('status', nullable=False, server_default=sa.text('1'), existing_type=sa.Boolean())
        batch_op.alter_column('steuerbescheid_bis', new_column_name='tax_until', existing_type=sa.Date())
    op.add_column("animals", sa.Column("pet_registry", sa.Text(), nullable=True), )
    op.add_column("animals", sa.Column("died_at", sa.Date(), nullable=True), )
    op.create_foreign_key('fk_animals_guest_id', 'animals', 'guests', ['guest_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    op.drop_constraint('fk_animals_guest_id', 'animals', type_='foreignkey')
    op.drop_column("animals", "pet_registry")
    op.drop_column("animals", "died_at")
    op.rename_table("animals", "tiere")
    with op.batch_alter_table('tiere') as batch_op:
        batch_op.alter_column('guest_id', new_column_name='gast_id', type_=sa.String(255))
        batch_op.alter_column('species', new_column_name='art', type_=sa.Enum('Hund', 'Katze', 'Vogel', 'Nager','Sonstige','Unbekannt'))
        batch_op.alter_column('breed', new_column_name='rasse', type_=sa.String(255))
        batch_op.alter_column('sex', new_column_name='geschlecht', type_=sa.Enum('M', 'F', 'Unbekannt'))
        batch_op.alter_column('color', new_column_name='farbe', type_=sa.String(255))
        batch_op.alter_column('castrated', new_column_name='kastriert', type_=sa.Boolean())
        batch_op.alter_column('identification', new_column_name='identifikation', type_=sa.String(255))
        batch_op.alter_column('birthdate', new_column_name='geburtsdatum', type_=sa.Date())
        batch_op.alter_column('weight_or_size', new_column_name='gewicht_oder_groesse', type_=sa.String(255))
        batch_op.alter_column('illnesses', new_column_name='krankheiten', type_=sa.String(255))
        batch_op.alter_column('allergies', new_column_name='unvertraeglichkeiten', type_=sa.String(255))
        batch_op.alter_column('food_type', new_column_name='futter', type_=sa.String(255))
        batch_op.alter_column('complete_care', new_column_name='vollversorgung', type_=sa.Boolean())
        batch_op.alter_column('last_seen', new_column_name='zuletzt_gesehen', type_=sa.Date())
        batch_op.alter_column('veterinarian', new_column_name='tierarzt', type_=sa.String(255))
        batch_op.alter_column('food_amount_note', new_column_name='futtermengeneintrag', type_=sa.String(255))
        batch_op.alter_column('note', new_column_name='notizen', type_=sa.Text())
        batch_op.alter_column('created_at', new_column_name='erstellt_am', server_default=None, type_=sa.DateTime())
        batch_op.alter_column('updated_at', new_column_name='aktualisiert_am', type_=sa.DateTime())
        batch_op.alter_column('status', new_column_name='status_temp', server_default=None, type_=sa.Boolean())
        batch_op.alter_column('status_temp', new_column_name='active', type_=sa.String(255))
        batch_op.alter_column('tax_until', new_column_name='steuerbescheid_bis', type_=sa.Date())
    op.execute("""
               UPDATE tiere
               SET active = CASE
                                WHEN status = TRUE THEN 'Aktiv'
                                WHEN status = FALSE THEN 'Inaktiv'
                                ELSE 'Inaktiv'
                   END
               """)
    op.drop_column('tiere', 'status')
