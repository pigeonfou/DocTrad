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


def test_every_sentence_in_a_paragraph_is_translated(monkeypatch):
    engine = TransformersEngine(); seen = []
    def infer(text):
        seen.append(text)
        return {'TrellisWare Technologies, Inc. leads MANET development.':'TrellisWare Technologies, Inc. développe les MANET.', 'It supports 800 nodes.':'Il prend en charge 800 nœuds.', 'TRL 9 supports tactical missions.':'TRL 9 prend en charge les missions tactiques.'}[text]
    monkeypatch.setattr(engine, '_translate_prose', infer)
    source = 'TrellisWare Technologies, Inc. leads MANET development. It supports 800 nodes. TRL 9 supports tactical missions.'
    target = engine.translate_contextual(source)
    assert seen == ['TrellisWare Technologies, Inc. leads MANET development.', 'It supports 800 nodes.', 'TRL 9 supports tactical missions.']
    assert '800' in target and 'TRL 9' in target


def test_network_repairs_are_scoped_to_english_source(monkeypatch):
    engine = TransformersEngine()
    monkeypatch.setattr(engine, '_translate_prose', lambda _: 'Plusieurs houblons avec la radio définie par logiciel et les DTS.')
    target = engine.translate_contextual('Multiple hops with Software Defined Radio and SDRs.')
    assert target == 'Plusieurs sauts avec la radio logicielle et les SDR.'
    assert 'houblons' in engine.translate_contextual('Harvest the crop.')


def test_reference_only_labels_never_translate_product_names(monkeypatch):
    engine = TransformersEngine()
    monkeypatch.setattr(engine, '_translate_prose', lambda _: (_ for _ in ()).throw(AssertionError('Reference-only inference')))
    for source in ('» TW-135 TSM Shadow High Power Radio (HPR)',
                   '» TW-870 TSM Ghost Radio',
                   '«Thales Defense & Security - AN/PRC-148C, AN/PRC-148D',
                   '» Android™ Tactical Assault Kit (ATAK)', 'Trell isWa re'):
        assert engine.translate_contextual(source, terminology()) == source


def test_reference_names_do_not_bypass_real_prose_or_user_glossary(monkeypatch):
    engine = TransformersEngine(); seen = []
    monkeypatch.setattr(engine, '_translate_prose', lambda text: seen.append(text) or 'La radio fonctionne.')
    assert engine.translate_contextual('Ghost Radio operates.', terminology()) == 'La radio fonctionne.'
    assert seen == ['Ghost Radio operates.']
    assert engine.translate_contextual('Ghost Radio', terminology({'Ghost Radio':'Nom choisi'})) == 'Nom choisi'


def test_missing_number_is_restored_at_unique_acronym_without_guessing(monkeypatch):
    engine = TransformersEngine()
    monkeypatch.setattr(engine, '_translate_prose', lambda _: 'Technologie de niveau de maturité (TRL), utilisée mondialement.')
    target = engine.translate_contextual('Technology Readiness Level (TRL) 9 technology, used worldwide.')
    assert '(TRL) 9,' in target
    from app.terminology import restore_anchored_numbers
    assert restore_anchored_numbers('(TRL) 9 then (TRL) 8', '(TRL) et (TRL)') == '(TRL) et (TRL)'
    assert restore_anchored_numbers('(TRL) 9 technology', '(TRL) 8 technologie') == '(TRL) 8 technologie'


def test_heading_glossary_applies_without_fragmenting_model_input(monkeypatch):
    engine = TransformersEngine(); seen = []
    monkeypatch.setattr(engine, '_translate_prose', lambda text: seen.append(text) or 'Scalabilité et efficacité du spectre: Plus de 800 nœuds.')
    source = 'Scalability and Spectrum Efficiency: Over 800 nodes.'
    assert engine.translate_contextual(source, terminology()) == 'Évolutivité et efficacité spectrale : Plus de 800 nœuds.'
    assert seen == [source]


def test_bulleted_short_labels_use_glossary_without_inference(monkeypatch):
    engine = TransformersEngine()
    monkeypatch.setattr(engine, '_translate_prose', lambda _: (_ for _ in ()).throw(AssertionError('Label inference')))
    assert engine.translate_contextual('» Chat', terminology()) == '» Messagerie instantanée'
    assert engine.translate_contextual('» SD and HD video', terminology()) == '» Vidéo SD et HD'

def test_contact_metadata_and_observed_email_damage_are_preserved(monkeypatch):
    engine = TransformersEngine()
    monkeypatch.setattr(engine, '_translate_prose', lambda _: "Pour plus d'informations, envoyez un e-mail à salestrellisware.com")
    for source in ('TRELLISWARE.COM', '00 | info@trellisware.com',
                   'TrellisWare Technologies, Inc. 10641 Scripps Summit Court, Suite 100, San Diego, CA 9213'):
        assert engine.translate_contextual(source, terminology()) == source
    assert 'sales@trellisware.com' in engine.translate_contextual('For more information, email sales@trellisware.com')
    from app.terminology import correct_network_terms
    assert correct_network_terms('Android™ Apps integration', 'Applications AndroidTM') == 'Applications Android™'
    assert correct_network_terms('Unrelated text', 'salestrellisware.com') == 'salestrellisware.com'


def test_domain_phrase_repairs_are_source_scoped():
    from app.terminology import correct_network_terms
    target = 'niveau de préparation technologique ; huit programmes de radios tactiques record'
    assert correct_network_terms('Unrelated text.', target) == target
    fixed = correct_network_terms('Technology Readiness Level and eight program of record tactical radios', target)
    assert fixed == 'niveau de maturité technologique ; huit radios tactiques de programmes officiels'
    phrase = 'des informations de localisation simultanées de voix, de données, de vidéo et de position (PLI)'
    assert correct_network_terms('simultaneous voice, data, video, and Position Location Information (PLI)', phrase) == 'la transmission simultanée de la voix, des données, de la vidéo et des informations de position (PLI)'


def test_both_distance_units_survive_model_conversion_simplification(monkeypatch):
    engine = TransformersEngine()
    source = 'Supports up to 8 hops with up to 26 miles (41.8 km) per hop and over 200 miles (321.9 km).'
    monkeypatch.setattr(engine, '_translate_prose', lambda _: "Prend en charge jusqu'à 8 sauts avec jusqu'à 41,8 km par saut et plus de 321,9 km.")
    target = engine.translate_contextual(source)
    assert '26 miles (41,8 km)' in target and '200 miles (321,9 km)' in target
    from app.quality import check
    assert not (check(source, target) + audit_translation(source, target))


def test_dual_measurement_restoration_refuses_ambiguous_or_changed_anchors():
    from app.terminology import restore_dual_measurements
    source = '26 miles (41.8 km)'
    for target in ('26 km (41,8 km)', '41,8 km et 41,8 km', '42 km'):
        assert restore_dual_measurements(source, target) == target
    assert restore_dual_measurements(source + ' then 41.8 km', '41,8 km') == '41,8 km'
    assert restore_dual_measurements(source, '(41,8 km)') == '26 miles (41,8 km)'
    assert restore_dual_measurements('4 inches (101.6 mm)', '101,6 mm') == '4 inches (101,6 mm)'
