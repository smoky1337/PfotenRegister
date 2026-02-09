from app.routes import food_plan_routes as fpr


def test_normalize_text():
    assert fpr._normalize_text(None) == ""
    assert fpr._normalize_text("  hi ") == "hi"


def test_combo_label():
    assert fpr._combo_label(tuple()) == "Ohne Tags"
    assert fpr._combo_label((("Tag", "#fff"),)) == "Tag"


def test_normalize_recent_food_filter():
    assert fpr._normalize_recent_food_filter("all") == "all"
    assert fpr._normalize_recent_food_filter("only_recent") == "only_recent"
    assert fpr._normalize_recent_food_filter("bad") == "all"
