from app.field_registry_defaults import (
    FIELD_UI_LABELS,
    ensure_field_registry,
    legacy_field_label,
)
from app.models import Animal, FieldRegistry, Guest, Representative, db


def test_field_registry_uses_german_defaults_and_preserves_custom_labels(app):
    with app.app_context():
        firstname = FieldRegistry.query.filter_by(
            model_name="Guest",
            field_name="firstname",
        ).one()
        lastname = FieldRegistry.query.filter_by(
            model_name="Guest",
            field_name="lastname",
        ).one()
        firstname.ui_label = legacy_field_label("firstname")
        lastname.ui_label = "Familienname (individuell)"
        db.session.commit()

        created_count, translated_count = ensure_field_registry(
            (Guest, Animal, Representative)
        )

        assert created_count == 0
        assert translated_count == 1
        assert firstname.ui_label == FIELD_UI_LABELS["Guest"]["firstname"]
        assert lastname.ui_label == "Familienname (individuell)"


def test_missing_field_registry_row_is_created_with_german_label(app):
    with app.app_context():
        FieldRegistry.query.filter_by(
            model_name="Animal",
            field_name="species",
        ).delete()
        db.session.commit()

        created_count, _ = ensure_field_registry((Guest, Animal, Representative))
        species = FieldRegistry.query.filter_by(
            model_name="Animal",
            field_name="species",
        ).one()

        assert created_count == 1
        assert species.ui_label == "Tierart"


def test_all_configurable_model_fields_have_german_labels():
    for model in (Guest, Animal, Representative):
        assert set(model.__table__.columns.keys()) <= set(
            FIELD_UI_LABELS[model.__name__]
        )
