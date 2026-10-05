def test_protected_values_never_enter_translation_model():
    from app.translation import TransformersEngine
    from app.quality import protect, restore, check
    engine = TransformersEngine()
    seen = []
    translations = {
        "Power supply voltage:": "Tension d'alimentation :",
        "Connect": "Connectez",
        "to the": "à la",
        "control board.": "carte de commande.",
    }
    def translate_prose(text):
        assert "ZXQ" not in text
        seen.append(text)
        return translations.get(text, text)
    engine._translate_prose = translate_prose
    for source in ["Power supply voltage: 12 VDC.", "Connect J3 to the STM32F407 control board.", "12 VDC", "12 VDC 12 VDC"]:
        protected, mapping = protect(source)
        target = restore(engine.translate(protected), mapping)
        assert check(source, target) == []
    assert restore(engine.translate("Power supply voltage: ZXQabcdef12Q0QXZ."), {"ZXQabcdef12Q0QXZ": "12 VDC"}) == "Tension d'alimentation : 12 VDC."
    assert seen
