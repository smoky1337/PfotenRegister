from app.routes.admin import import_export_routes as ier


def test_map_animal_sex_maps_known_values():
    assert ier._map_animal_sex("m") == "M"
    assert ier._map_animal_sex("male") == "M"
    assert ier._map_animal_sex("w") == "F"
    assert ier._map_animal_sex("female") == "F"
    assert ier._map_animal_sex("unbekannt") == "Unbekannt"


def test_map_choice_returns_default_for_unknown():
    assert ier._map_choice("X", {"A", "B"}, default="A") == "A"


def test_map_yes_no_unknown():
    assert ier._map_yes_no_unknown("Ja") == "Ja"
    assert ier._map_yes_no_unknown("Nein") == "Nein"
    assert ier._map_yes_no_unknown("foo") == "Unbekannt"


def test_map_species():
    assert ier._map_species("Hund") == "Hund"
    assert ier._map_species("Katze") == "Katze"
    assert ier._map_species("X") is None


def test_map_food_type():
    assert ier._map_food_type("Trocken") == "Trocken"
    assert ier._map_food_type("Nass") == "Nass"
    assert ier._map_food_type("X") is None
