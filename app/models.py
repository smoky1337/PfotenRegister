from flask_sqlalchemy import SQLAlchemy

# SQLAlchemy database instance
# This will be initialized in app.__init__.create_app

db = SQLAlchemy()

class Guest(db.Model):
    __tablename__ = 'gaeste'

    id = db.Column(db.String(255), primary_key=True)
    nummer = db.Column(db.String(255), nullable=False)
    vorname = db.Column(db.String(255), nullable=False)
    nachname = db.Column(db.String(255), nullable=False)
    adresse = db.Column(db.String(255))
    ort = db.Column(db.String(255))
    plz = db.Column(db.String(255))
    festnetz = db.Column(db.String(50))
    mobil = db.Column(db.String(50))
    email = db.Column(db.String(255))
    geburtsdatum = db.Column(db.Date)
    geschlecht = db.Column(db.Enum('Frau', 'Herr', 'Divers', 'Unbekannt'), default='Unbekannt')
    eintritt = db.Column(db.Date, nullable=False)
    austritt = db.Column(db.Date)
    vertreter_name = db.Column(db.String(255))
    vertreter_telefon = db.Column(db.String(50))
    vertreter_email = db.Column(db.String(255))
    vertreter_adresse = db.Column(db.String(255))
    status = db.Column(db.Enum('Aktiv', 'Inaktiv'), default='Aktiv', nullable=False)
    beduerftigkeit = db.Column(db.String(255))
    beduerftig_bis = db.Column(db.Date)
    dokumente = db.Column(db.Text)
    notizen = db.Column(db.Text)
    erstellt_am = db.Column(db.Date, nullable=False)
    aktualisiert_am = db.Column(db.Date, nullable=False)

    animals = db.relationship('Animal', back_populates='guest', cascade='all, delete')

class Animal(db.Model):
    __tablename__ = 'tiere'

    id = db.Column(db.Integer, primary_key=True)
    gast_id = db.Column(db.String(255), db.ForeignKey('gaeste.id'), nullable=False)
    art = db.Column(db.Enum('Hund','Katze','Vogel','Nager','Sonstige'), nullable=False)
    rasse = db.Column(db.String(100))
    name = db.Column(db.String(100))
    geschlecht = db.Column(db.Enum('M','F','Unbekannt'), default='Unbekannt')
    farbe = db.Column(db.String(100))
    kastriert = db.Column(db.Enum('ja','nein','unbekannt'))
    identifikation = db.Column(db.String(100))
    geburtsdatum = db.Column(db.Date)
    gewicht_oder_groesse = db.Column(db.String(50))
    krankheiten = db.Column(db.Text)
    unvertraeglichkeiten = db.Column(db.Text)
    futter = db.Column(db.Enum('Misch','Trocken','Nass','Barf'))
    vollversorgung = db.Column(db.Enum('ja','nein'))
    zuletzt_gesehen = db.Column(db.Date)
    tierarzt = db.Column(db.String(255))
    futtermengeneintrag = db.Column(db.Text)
    notizen = db.Column(db.Text)
    erstellt_am = db.Column(db.Date, nullable=False)
    aktualisiert_am = db.Column(db.Date, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    steuerbescheid_bis = db.Column(db.Date)

    guest = db.relationship('Guest', back_populates='animals')
