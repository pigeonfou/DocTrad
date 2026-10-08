from app.translation_audit import audit_translation

def test_bad_literal_translations_are_flagged():
    warnings = audit_translation("Spatial Hops", "Houblon spatial")
    assert any("sauts spatiaux" in w for w in warnings)

def test_missing_radio_name_is_flagged():
    warnings = audit_translation("Shadow Radio supports TSM.", "La Radio Ombre prend en charge TSM.")
    assert any("Shadow Radio" in w for w in warnings)

def test_identifier_preservation():
    assert any("TW-950" in w for w in audit_translation("TW-950 radio", "Radio autre"))
    assert not audit_translation("TW-950 Shadow Radio", "TW-950 Shadow Radio")

def test_correct_translation_no_warning():
    assert not audit_translation("Spatial Hops", "Sauts spatiaux")

