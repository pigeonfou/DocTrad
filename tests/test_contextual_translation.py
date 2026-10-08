from app.translation import TransformersEngine
from app.terminology import terminology
from app.translation_audit import audit_translation


def test_model_receives_complete_sentence_with_values_and_product_names(monkeypatch):
    engine = TransformersEngine()
    seen = []
    def infer(text):
        seen.append(text)
        return 'Shadow Radio fonctionne à 12 VDC sur 26 miles.'
    monkeypatch.setattr(engine, '_translate_prose', infer)
    source = 'Shadow Radio operates at 12 VDC over 26 miles.'
    assert engine.translate_contextual(source, terminology()) == 'Shadow Radio fonctionne à 12 VDC sur 26 miles.'
    assert seen == [source]


def test_exact_heading_uses_glossary_without_inference(monkeypatch):
    engine = TransformersEngine()
    monkeypatch.setattr(engine, '_translate_prose', lambda _: (_ for _ in ()).throw(AssertionError('Unnecessary inference')))
    assert engine.translate_contextual('Spatial Hops', terminology()) == 'Sauts spatiaux'
    assert engine.translate_contextual('26', terminology()) == '26'


def test_unit_change_detected_even_when_digits_unchanged():
    warnings = audit_translation('Range: 26 miles (41.8 km)', 'Portée : 26 kilomètres (41.8 km)')
    assert any('26 miles' in warning for warning in warnings)
    assert not audit_translation('Range: 26 miles (41.8 km)', 'Portée : 26 miles (41.8 km)')


def test_inline_glossary_is_one_pass_and_scoped_to_source(monkeypatch):
    engine = TransformersEngine()
    monkeypatch.setattr(engine, '_translate_prose', lambda _: 'Software Defined Radio et Data')
    assert engine.translate_contextual('Software Defined Radio supports transmission.', {'Software Defined Radio': 'radio Data', 'Data':'Données'}) == 'radio Data et Data'
