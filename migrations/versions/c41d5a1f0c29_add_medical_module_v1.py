"""add medical module v1

Revision ID: c41d5a1f0c29
Revises: ed79901f492d
Create Date: 2026-03-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c41d5a1f0c29"
down_revision: Union[str, None] = "ed79901f492d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "medical_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guest_id", sa.String(length=255), nullable=False),
        sa.Column("animal_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum("Behandlung", "Operation", "Untersuchung", "Medikament", "Sonstiges", name="medical_event_type"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("Geplant", "Aktiv", "Abgeschlossen", "Abgesagt", name="medical_event_status"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum("Niedrig", "Mittel", "Hoch", "Notfall", name="medical_event_priority"),
            nullable=False,
        ),
        sa.Column("planned_for", sa.Date(), nullable=True),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("completed_on", sa.Date(), nullable=True),
        sa.Column("follow_up_on", sa.Date(), nullable=True),
        sa.Column("veterinarian", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("actual_cost", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("paid_amount", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_on", sa.DateTime(), nullable=False),
        sa.Column("updated_on", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["animal_id"], ["animals.id"], name="fk_medical_events_animal_id"),
        sa.ForeignKeyConstraint(["guest_id"], ["guests.id"], name="fk_medical_events_guest_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_medical_events_animal_id"), "medical_events", ["animal_id"], unique=False)
    op.create_index(op.f("ix_medical_events_completed_on"), "medical_events", ["completed_on"], unique=False)
    op.create_index(op.f("ix_medical_events_follow_up_on"), "medical_events", ["follow_up_on"], unique=False)
    op.create_index(op.f("ix_medical_events_guest_id"), "medical_events", ["guest_id"], unique=False)
    op.create_index(op.f("ix_medical_events_planned_for"), "medical_events", ["planned_for"], unique=False)
    op.create_index(op.f("ix_medical_events_started_on"), "medical_events", ["started_on"], unique=False)
    op.create_index(op.f("ix_medical_events_status"), "medical_events", ["status"], unique=False)

    op.create_table(
        "medical_event_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("medical_event_id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["attachments.id"],
            name="fk_medical_event_attachments_attachment_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["medical_event_id"],
            ["medical_events.id"],
            name="fk_medical_event_attachments_event_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("medical_event_id", "attachment_id", name="uq_medical_event_attachment"),
    )
    op.create_index(
        op.f("ix_medical_event_attachments_attachment_id"),
        "medical_event_attachments",
        ["attachment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_medical_event_attachments_medical_event_id"),
        "medical_event_attachments",
        ["medical_event_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_medical_event_attachments_medical_event_id"), table_name="medical_event_attachments")
    op.drop_index(op.f("ix_medical_event_attachments_attachment_id"), table_name="medical_event_attachments")
    op.drop_table("medical_event_attachments")

    op.drop_index(op.f("ix_medical_events_status"), table_name="medical_events")
    op.drop_index(op.f("ix_medical_events_started_on"), table_name="medical_events")
    op.drop_index(op.f("ix_medical_events_planned_for"), table_name="medical_events")
    op.drop_index(op.f("ix_medical_events_guest_id"), table_name="medical_events")
    op.drop_index(op.f("ix_medical_events_follow_up_on"), table_name="medical_events")
    op.drop_index(op.f("ix_medical_events_completed_on"), table_name="medical_events")
    op.drop_index(op.f("ix_medical_events_animal_id"), table_name="medical_events")
    op.drop_table("medical_events")

    sa.Enum(name="medical_event_priority").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="medical_event_status").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="medical_event_type").drop(op.get_bind(), checkfirst=False)
