from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql.functions import now

class DictMixin:
    """Provide dictionary style access to model attributes."""

    def __getitem__(self, key):
        return getattr(self, key)

# SQLAlchemy database instance
# This will be initialized in app.__init__.create_app

db = SQLAlchemy()

# Association table for many-to-many relationship between Animal and FoodTag
animal_food_tags = db.Table(
    'animal_food_tags',
    db.Column('animal_id', db.Integer, db.ForeignKey('animals.id'), primary_key=True),
    db.Column('food_tag_id', db.Integer, db.ForeignKey('food_tags.id'), primary_key=True)
)


class FoodHistoryTag(db.Model):
    __tablename__ = 'food_history_tags'
    id = db.Column(db.Integer, primary_key=True)
    food_history_id = db.Column(db.Integer, db.ForeignKey('food_history.id'), nullable=False)
    food_tag_id = db.Column(db.Integer, db.ForeignKey('food_tags.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    # Relationships
    food_history = db.relationship('FoodHistory', back_populates='tag_assocs')
    food_tag = db.relationship('FoodTag', back_populates='history_assocs')

class Guest(DictMixin, db.Model):
    __tablename__ = 'guests'

    id = db.Column(db.String(255), primary_key=True, index=True)
    number = db.Column(db.String(255), nullable=False, index=True)
    firstname = db.Column(db.String(255), nullable=False, index=True)
    lastname = db.Column(db.String(255), nullable=False, index=True)
    address = db.Column(db.String(255))
    city = db.Column(db.String(255))
    zip = db.Column(db.String(255))
    phone = db.Column(db.String(255))
    mobile = db.Column(db.String(255))
    email = db.Column(db.String(255))
    birthdate = db.Column(db.Date)
    gender = db.Column(db.Enum('Frau', 'Mann', 'Divers', 'Unbekannt'), default='Unbekannt')
    member_since = db.Column(db.Date, nullable=False)
    member_until = db.Column(db.Date)
    status = db.Column(db.Boolean, default=1)
    indigence = db.Column(db.String(255))
    indigent_until = db.Column(db.Date)
    documents = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_on = db.Column(db.Date, nullable=False)
    updated_on = db.Column(db.Date, nullable=False)
    guest_card_printed_on = db.Column(db.Date)
    guest_card_emailed_on = db.Column(db.Date)
    dispense_location_id = db.Column(
        db.Integer,
        db.ForeignKey("drop_off_locations.id", name="fk_guests_dispense_location"),
        nullable=True,
    )
    dispense_location = db.relationship("DropOffLocation", foreign_keys=[dispense_location_id])

    animals = db.relationship('Animal', back_populates='guest', cascade='all, delete')
    representative = db.relationship('Representative', back_populates='guest', cascade='all, delete-orphan')

    attachments = db.relationship(
        "Attachment",
        primaryjoin="Attachment.owner_id==Guest.id",
        foreign_keys="[Attachment.owner_id]",
        backref=db.backref("guest", lazy="joined"),
        cascade="all, delete-orphan",
        viewonly=True
    )


class Representative(DictMixin, db.Model):
    __tablename__ = 'representative'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    phone = db.Column(db.String(255))
    email = db.Column(db.String(255))
    address = db.Column(db.String(255))

    guest_id = db.Column(
        db.String(255),
        db.ForeignKey('guests.id', name='fk_representative_guest_id'),
        nullable=False,
        index=True
    )
    guest = db.relationship('Guest', back_populates='representative')

class Animal(DictMixin, db.Model):
    __tablename__ = 'animals'

    id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(
        db.String(255),
        db.ForeignKey('guests.id', name='fk_animals_guest_id'),
        nullable=False,
        index=True
    )
    species = db.Column(db.Enum('Hund','Katze','Vogel','Nager','Sonstige'))
    breed = db.Column(db.String(255))
    name = db.Column(db.String(255))
    sex = db.Column(db.Enum('M','F','Unbekannt'), default='Unbekannt')
    color = db.Column(db.String(255))
    castrated = db.Column(db.Enum('Ja','Nein','Unbekannt'), default='Unbekannt')
    identification = db.Column(db.String(255))
    birthdate = db.Column(db.Date)
    weight_or_size = db.Column(db.String(255))
    illnesses = db.Column(db.Text)
    allergies = db.Column(db.Text)
    food_type = db.Column(db.Enum('Misch','Trocken','Nass','Barf'))
    complete_care = db.Column(db.Enum('Ja','Nein', 'Unbekannt'), default='Unbekannt')
    last_seen = db.Column(db.Date)
    veterinarian = db.Column(db.String(255))
    food_amount_note = db.Column(db.Text)
    note = db.Column(db.Text)
    created_on = db.Column(db.Date, nullable=False)
    updated_on = db.Column(db.Date, nullable=False)
    status = db.Column(db.Boolean, default="1")
    tax_until = db.Column(db.Date)
    pet_registry = db.Column(db.Text)
    died_on = db.Column(db.Date, default=None)

    guest = db.relationship('Guest', back_populates='animals')


    # Many-to-many: which food tags apply to this animal
    food_tags = db.relationship(
        'FoodTag',
        secondary=animal_food_tags,
        back_populates='animals'
    )

    profile_attachment_id = db.Column(
        db.Integer,
        db.ForeignKey("attachments.id", ondelete="SET NULL"),
        nullable=True,
    )
    profile_attachment = db.relationship(
        "Attachment",
        foreign_keys=[profile_attachment_id],
        uselist=False,
    )


class User(DictMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(255), nullable=False)
    realname = db.Column(db.String(255), nullable=False)


class Setting(DictMixin, db.Model):
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(255), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)


class Payment(DictMixin, db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(
        db.String(255),
        db.ForeignKey('guests.id', name='fk_payments_guest_id'),
        nullable=False,
        index=True
    )
    paid_on = db.Column(db.Date, index=True)
    food_amount = db.Column(db.Numeric(10, 2), default=0.00)
    other_amount = db.Column(db.Numeric(10, 2), default=0.00)
    comment = db.Column(db.Text)
    created_on = db.Column(db.Date, nullable=False)
    paid = db.Column(db.Boolean, nullable=False, default=True)

    guest = db.relationship('Guest')


class ChangeLog(DictMixin, db.Model):
    __tablename__ = 'changelog'

    changelog_id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(
        db.String(255),
        db.ForeignKey('guests.id', name='fk_changelog_guest_id'),
        nullable=False,
        index=True
    )
    change_type = db.Column(db.String(255))
    description = db.Column(db.Text)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', name='fk_changelog_user_id')
    )
    change_timestamp = db.Column(db.DateTime, index=True)

    guest = db.relationship('Guest')
    user = db.relationship('User')


class FoodHistory(DictMixin, db.Model):
    __tablename__ = 'food_history'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    guest_id = db.Column(
        db.String(255),
        db.ForeignKey('guests.id', name='fk_food_history_guest_id'),
        nullable=False,
        index=True
    )
    location_id = db.Column(
        db.Integer,
        db.ForeignKey("drop_off_locations.id", name="fk_food_history_location_id"),
        nullable=True,
        index=True,
    )
    distributed_on = db.Column(db.Date, index=True)
    comment = db.Column(db.Text)

    guest = db.relationship('Guest')
    location = db.relationship("DropOffLocation")
    # Association to distributed tags
    tag_assocs = db.relationship(
        'FoodHistoryTag',
        back_populates='food_history',
        cascade='all, delete-orphan'
    )
    # Proxy to access tags directly
    from sqlalchemy.ext.associationproxy import association_proxy
    distributed_tags = association_proxy('tag_assocs', 'food_tag',
                                         creator=lambda tag: FoodHistoryTag(food_tag=tag))


class FoodDispensePlan(DictMixin, db.Model):
    __tablename__ = "food_dispense_plans"

    id = db.Column(db.Integer, primary_key=True)
    plan_date = db.Column(db.Date, nullable=False, index=True)
    location_id = db.Column(
        db.Integer,
        db.ForeignKey("drop_off_locations.id", name="fk_food_plan_location"),
        nullable=True,
        index=True,
    )
    payload = db.Column(db.JSON, nullable=False)
    summary = db.Column(db.JSON, nullable=False)
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", name="fk_food_plan_created_by"),
        nullable=False,
    )
    created_on = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_on = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    location = db.relationship("DropOffLocation")
    created_by = db.relationship("User")


class FoodTag(DictMixin, db.Model):
    __tablename__ = 'food_tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    color = db.Column(db.String(7), nullable=False)

    # back-reference to animals
    animals = db.relationship(
        'Animal',
        secondary=animal_food_tags,
        back_populates='food_tags'
    )
    # Back-reference from history entries
    history_assocs = db.relationship(
        'FoodHistoryTag',
        back_populates='food_tag',
        cascade='all, delete-orphan'
    )

class FieldRegistry(db.Model):
    __tablename__ = "field_registry"

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(100), nullable=False)  # e.g. "Guest"
    field_name = db.Column(db.String(100), nullable=False)  # e.g. "indigence"
    globally_visible = db.Column(db.Boolean, default=True)
    visibility_level = db.Column(db.String(100), default="Admin") #"Admin", "Editor", "User"
    editability_level = db.Column(db.String(100), default="Admin")
    show_inline = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.SmallInteger, default=0)
    optional = db.Column(db.Boolean, default=False)
    ui_label = db.Column(db.String(255), nullable=False)
    remindable = db.Column(db.Boolean, default=False)
    reminder_interval_days = db.Column(db.Integer)
    reminder_species = db.Column(db.Text)



    __table_args__ = (
        db.UniqueConstraint("model_name", "field_name", name="uq_model_field"),
    )

class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(
        db.String(255),
        db.ForeignKey('guests.id', name='fk_message_guest_id')
    )
    created_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', name='fk_message_user_id')
    )
    created_on = db.Column(db.Date, index=True, nullable=False)
    completed = db.Column(db.Date, default=None)
    content = db.Column(db.Text)


class Attachment(db.Model):
    __tablename__ = "attachments"
    id = db.Column(db.Integer, primary_key=True)

    owner_id = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    gcs_path = db.Column(db.String(512), nullable=False)
    uploaded_on = db.Column(db.DateTime)

    __table_args__ = (
        db.Index("ix_attachments_owner", "owner_id"),
    )


class DropOffLocation(DictMixin, db.Model):
    __tablename__ = "drop_off_locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(255))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    location_type = db.Column(
        db.Enum(
            "dropbox",
            "donationbox",
            "office",
            "storage",
            "dispense",
            name="location_type",
        ),
        nullable=False,
        default="dropbox",
    )
    is_dispense_location = db.Column(db.Boolean, nullable=False, default=False)
    responsible_person = db.Column(db.String(255))
    last_emptied = db.Column(db.Date)
    comments = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_on = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_on = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "city": self.city,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "location_type": self.location_type,
            "is_dispense_location": self.is_dispense_location,
            "responsible_person": self.responsible_person,
            "last_emptied": self.last_emptied.isoformat() if self.last_emptied else None,
            "comments": self.comments,
            "active": self.active,
        }
