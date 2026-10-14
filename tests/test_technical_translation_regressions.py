import unittest
from unittest.mock import patch
from types import SimpleNamespace
from PIL import Image
from app.ocr import recover_legal_small_print
from app.terminology import correct_network_terms

class TechnicalTranslationRegressions(unittest.TestCase):
    def test_mixed_frequency_units_do_not_become_negative(self):
        self.assertEqual(correct_network_terms('5 kHz-40 MHz','5 kHz à -40 MHz.'),'5 kHz à 40 MHz.')
        self.assertEqual(correct_network_terms('-40 MHz','40 MHz'),'-40 MHz')

    def test_manpack_wording_and_postal_metadata(self):
        from app.terminology import reference_label
        self.assertEqual(correct_network_terms('Multichannel Radio uses crossbanding','Le radio multifréquences utilise la bande croisée.'),
            'La radio multicanal utilise l’interconnexion interbande.')
        self.assertTrue(reference_label('1025 W. NASA Boulevard',{}))
        self.assertTrue(reference_label('Melbourne, FL 32919',{}))
        for literal in ('USB 2.0','SCA v2.2.2','60 dBm','AN/PRC-167, RT-2096'):
            self.assertTrue(reference_label(literal,{}))
        self.assertFalse(reference_label('GENERAL',{}))
        self.assertFalse(reference_label('60 years',{}))

    def test_security_suites_and_sinad_are_required_names(self):
        from app.terminology import missing_names
        self.assertEqual(set(missing_names('Suite A and Suite B, Type-1, 12 dB SINAD, 18 VDC','modèles A et B, type 1, 12 dB de bruit, 18 VCC')),
            {'Suite A','Suite B','Type-1','SINAD','VDC'})
    def test_ranges_never_acquire_a_negative_endpoint(self):
        for source in ('30-2600 MHz','30 - 2600 MHz','30–2600 MHz'):
            self.assertEqual(correct_network_terms(source,'30 à 2600 MHz'),'30 à 2600 MHz')
            self.assertEqual(correct_network_terms(source,'30 à -2600 MHz'),'30 à 2600 MHz')
        self.assertEqual(correct_network_terms('Value -53 dBc','Valeur 53 dBc'),'Valeur -53 dBc')

    def test_dimensions_recover_units_without_changing_axes_or_values(self):
        source='3.50H x 7.25W x 14.31D in (with battery)'
        target='3,50H x 7,25L x 14,31P (avec batterie)'
        result=correct_network_terms(source,target)
        self.assertEqual(result,'3,50H x 7,25L x 14,31P in (avec batterie)')
        self.assertEqual(correct_network_terms(source,result),result)
        self.assertEqual(correct_network_terms(source,'3,50H x 7,25L x 15,31P'),'3,50H x 7,25L x 15,31P')

    def test_classification_and_omitted_acronyms(self):
        from app.translation import TransformersEngine
        from app.terminology import terminology
        self.assertEqual(correct_network_terms('Up to TOP SECRET','Jusqu’à CONFIDENTIEL'),'Jusqu’à TOP SECRET')
        engine=TransformersEngine();seen=[]
        def prose(text):
            seen.append(text)
            return {'Internal SAASM GPS and ISR video.':'GPS interne et vidéo.',
                    'Internal':'Interne','GPS and':'GPS et','video.':'vidéo.'}.get(text,text)
        engine._translate_prose=prose
        result=engine.translate_contextual('Internal SAASM GPS and ISR video.',terminology())
        self.assertIn('SAASM',result);self.assertIn('ISR',result)
        self.assertFalse(any('ZXQ' in text for text in seen))

    def test_cached_name_validation_honors_glossary_and_repeated_names(self):
        from app.terminology import missing_names
        self.assertEqual(missing_names('SAASM GPS and ISR video','GPS et vidéo'),['ISR','SAASM'])
        self.assertEqual(missing_names('ISR video','vidéo RSR',{'ISR':'RSR'}),[])
        self.assertEqual(missing_names('ISR and ISR','ISR'),['ISR'])

    def test_signed_comparison_and_cubic_unit_are_preserved(self):
        self.assertEqual(correct_network_terms('> -53dBc','53 dBc'),'> -53 dBc')
        self.assertEqual(correct_network_terms('167 in³ (without battery)','167 pouces (sans batterie)'),
                         '167 in³ (sans batterie)')
        self.assertEqual(correct_network_terms('-40°C to +60°C','40°C à +60°C'),'-40°C à +60°C')
    def test_legal_reread_keeps_contacts_and_document_code_separate(self):
        lines=[dict(text='Marks are trademarks',box=[100,2400,190,2410],confidence=.9),
               dict(text='of their owners.',box=[100,2420,190,2430],confidence=.9),
               dict(text='DOC-2022',box=[130,2440,190,2450],confidence=.9),
               dict(text='info@example.com',box=[5,2400,80,2410],confidence=.9)]
        header='level\tblock_num\tpar_num\tline_num\tleft\ttop\twidth\theight\tconf\ttext\n'
        rows=[]
        for n,(top,text) in enumerate([(16,'Marks are trademarks'),(96,'of their owners.'),(176,'DOC-2022')],1):
            rows.append(f'5\t1\t1\t{n}\t16\t{top}\t360\t40\t95\t{text}\n')
        with patch('app.ocr.subprocess.run',return_value=SimpleNamespace(stdout=header+''.join(rows))):
            recover_legal_small_print(lines,Image.new('L',(200,2500),255))
        notice=next(s for s in lines if s.get('ocr_verified_by_reread'))
        self.assertEqual(notice['text'],'Marks are trademarks of their owners.')
        self.assertLess(notice['box'][3],2440)
        self.assertTrue(any(s['text']=='info@example.com' for s in lines))

    def test_verbal_comparison_is_not_duplicated(self):
        source='Fast join and merge (1 second to join, < 5 seconds to form/merge).'
        target='Rejoindre et fusionner rapidement (1 seconde pour la connexion, moins de < 5 secondes pour la formation/fusion).'
        result=correct_network_terms(source,target)
        self.assertIn('Connexion et fusion rapides des réseaux',result)
        self.assertIn('moins de 5 secondes',result)
        self.assertNotIn('<',result)
        self.assertEqual(correct_network_terms(source,result),result)

    def test_missing_symbol_is_restored_and_inequality_is_not_weakened(self):
        self.assertEqual(correct_network_terms('Value ≤ 5','Valeur 5'),'Valeur ≤ 5')
        self.assertEqual(correct_network_terms('Value < 5','Valeur 5'),'Valeur < 5')
        self.assertEqual(correct_network_terms('Value > 5','Valeur plus de > 5'),'Valeur plus de 5')

    def test_unrelated_prose_is_unchanged(self):
        self.assertEqual(correct_network_terms('Join the meeting','Rejoindre rapidement la réunion'),'Rejoindre rapidement la réunion')

    def test_join_prefix_is_corrected_with_a_bullet_or_whitespace(self):
        source='• Fast join & merge (1 second to join, < 5 seconds to merge)'
        for prefix in ('','  ','• ','▪ '):
            result=correct_network_terms(source,prefix+'Rejoindre et fusionner rapidement (1 seconde, moins de 5 secondes)')
            self.assertTrue(result.startswith(prefix+'Connexion et fusion rapides des réseaux'))

    def test_legal_alternative_preserves_registered_and_unregistered_marks(self):
        source='The names are trademarks or registered trademarks of the company.'
        for target in ('Les noms sont des marques déposées ou des marques de commerce de la société.',
                       'Les noms sont des marques de commerce de la société.'):
            result=correct_network_terms(source,target)
            self.assertIn('marques ou marques déposées',result)
            self.assertEqual(correct_network_terms(source,result),result)
        self.assertEqual(correct_network_terms('This is a trademark.','Une marque de commerce.'),'Une marque de commerce.')

    def test_join_ocr_spacing_and_repeated_markers(self):
        for source in ('Fastjoin and merge','Fast join&merge','Fast join andmerge'):
            for target in ('• • Rejoindre et fusionner rapidement (1 seconde)',
                           'Évolutivité : Rejoindre et fusionner rapidement (1 seconde)'):
                result=correct_network_terms(source,target)
                self.assertIn('Connexion et fusion rapides des réseaux',result)

    def test_android_registration_matches_source_even_with_ocr_ts(self):
        target='Android est une marque déposée de Google LLC.'
        for source in ('Android is a trademark of Google LLC.', 'Android ts a trademark of Google LLC.'):
            self.assertEqual(correct_network_terms(source,target),'Android est une marque de Google LLC.')
        self.assertEqual(correct_network_terms('Android is a registered trademark of Google LLC.',target),target)

if __name__=='__main__':unittest.main()


def test_crossbanding_articles_are_source_anchored():
    from app.terminology import correct_network_terms
    assert correct_network_terms('Uses crossbanding', 'Utilise le interconnexion interbande') == 'Utilise l’interconnexion interbande'
    assert correct_network_terms('Advanced crossbanding', 'Un système de interconnexion interbande') == 'Un système d’interconnexion interbande'
    assert correct_network_terms('Unrelated source', 'Utilise le interconnexion interbande') == 'Utilise le interconnexion interbande'


def test_security_identifier_spelling_repairs_are_source_anchored():
    assert correct_network_terms('Type-1 Suite A and Suite B', 'type 1 SuiteA et suite b') == 'Type-1 Suite A et Suite B'
    assert correct_network_terms('Another type', 'type 1 SuiteA') == 'type 1 SuiteA'

def test_radio_labels_keep_meaning_and_do_not_add_punctuation():
    from app.translation import RemoteEngine
    from app.terminology import terminology
    engine = RemoteEngine()
    with patch.object(engine, '_translate_prose', side_effect=AssertionError('Label should not need inference')):
        assert engine.translate_contextual('Power Input', terminology()) == 'Tension d’alimentation'
        assert engine.translate_contextual('Net Presets', terminology()) == 'Préréglages réseau'
        assert engine.translate_contextual('Squelch', terminology()) == 'Silencieux'
        assert engine.translate_contextual('Encryption', terminology()) == 'Chiffrement'
        assert engine.translate_contextual('Key Fill', terminology({'Key Fill': 'Injection des clés'})) == 'Injection des clés'


def test_security_suite_shorthand_keeps_both_source_suites():
    assert correct_network_terms('Denali Type-1 Suite A and Suite B', 'denali Type 1 suites A et B') == 'Denali Type-1 Suite A et Suite B'
    assert correct_network_terms('Another source', 'suites A et B') == 'suites A et B'

def test_small_photo_notice_preserves_agency_and_non_endorsement():
    from app.terminology import compact_image_notice
    source = 'The appearance of U.S. Department of War visual information does not imply or constitute DoW endorsement.'
    target = compact_image_notice(source)
    assert target == 'Ces images du ministère américain de la Guerre ne valent pas approbation du DoW.'
    assert len(target) < len(source)
    assert compact_image_notice(source.replace('DoW', 'DoD')) is None
    assert compact_image_notice('Other legal notice') is None


def test_structured_measurements_preserve_all_axes_numbers_and_units():
    from app.terminology import structured_technical_text
    source='3.50 H x 7.25 W x 14.31 D in (with battery) 8.89 H x 18.41 W x 36.34 D cm (with battery)'
    target=structured_technical_text(source)
    assert target == '3.50 H x 7.25 W x 14.31 D in (avec batterie)\n8.89 H x 18.41 W x 36.34 D cm (avec batterie)'
    assert structured_technical_text('167 in³ (without battery) 275 in³ (with battery)') == '167 in³ (sans batterie)\n275 in³ (avec batterie)'
    assert structured_technical_text(source+' Other qualification') is None
    assert structured_technical_text('3.50 H x 7.25 W in (with battery)') is None

def test_structured_encryption_label_keeps_source_names_and_glossary():
    from app.terminology import structured_technical_text
    source='Denali-based Type-1 Suite A and Suite B encryption (selections vary by waveform)'
    assert structured_technical_text(source) == 'Chiffrement Denali Type-1 Suite A et Suite B (selon la forme d’onde)'
    assert structured_technical_text(source, {'Denali':'Nom personnalisé'}).startswith('Chiffrement Nom personnalisé ')
    assert structured_technical_text(source.replace('Suite B','Suite C')) is None


def test_regulatory_notice_preserves_controlled_status_and_part_numbers():
    from app.terminology import structured_technical_text, reference_label
    from app.quality import check
    source='NON-EXPORT CONTROLLED: THIS DOCUMENT CONSISTS OF INFORMATION THAT IS NOT DEFINED AS CONTROLLED TECHNICAL DATA UNDER ITAR PART 120.33 OR TECHNOLOGY UNDER EAR PART 772.'
    target=structured_technical_text(source)
    assert 'DONNÉES TECHNIQUES CONTRÔLÉES' in target
    assert '120.33' in target and '772' in target
    assert not check(source,target)
    assert check(source,target.replace('120.33','120.34'))
    assert reference_label('© 2026 L3Harris Technologies, Inc. | 07/2026 | L33398',{})


def test_manpack_gender_and_release_grammar_are_source_anchored():
    source='The Multichannel Manpack radio supports modes, with 3.2 in development.'
    target='Le "radio portable multicanal" est disponible ; ce radio fonctionne. Les versions 3.2 sont en développement.'
    corrected=correct_network_terms(source,target)
    assert corrected=='La radio portable multicanal est disponible ; cette radio fonctionne. La version 3.2 est en développement.'
    assert correct_network_terms('Unrelated source',target)==target


def test_immersion_depth_is_not_a_quantity_of_water():
    from app.terminology import structured_technical_text
    from app.quality import check
    source = '2-meter salt water (MIL-STD-810G)'
    target = structured_technical_text(source)
    assert target == '2 m en eau salée (MIL-STD-810G)'
    assert not check(source, target)
    assert structured_technical_text('1.5-meter salt water (MIL-STD-810H)') == '1.5 m en eau salée (MIL-STD-810H)'
    assert structured_technical_text(source + ' for 30 minutes') is None
    assert structured_technical_text('2-meter fresh water (MIL-STD-810G)') is None


def test_battery_capability_preserves_all_three_models():
    from app.terminology import structured_technical_text, missing_names
    from app.quality import check
    source = 'BB-2590/U for full radio capability Can use BA-5590/U and BA-5390/U'
    target = structured_technical_text(source)
    assert target == 'BB-2590/U : toutes les fonctions radio\nBA-5590/U et BA-5390/U également utilisables'
    assert len(target) < len('BB-2590/U pour une compatibilité radio complète. Peut utiliser les modèles BA-5590/U et BA-5390/U.')
    assert not missing_names(source, target)
    assert not check(source, target)
    assert structured_technical_text(source + ' with restrictions') is None
    assert structured_technical_text(source.replace('full radio capability', 'limited radio capability')) is None


def test_precise_technical_cells_bypass_remote_inference_but_honor_exact_glossary():
    from app.translation import RemoteEngine
    from app.terminology import terminology
    engine = RemoteEngine()
    source = '2-meter salt water (MIL-STD-810G)'
    battery = 'BB-2590/U for full radio capability Can use BA-5590/U and BA-5390/U'
    with patch.object(engine, '_translate_prose', side_effect=AssertionError('No inference for exact cell grammar')):
        assert engine.translate_contextual(source, terminology()) == '2 m en eau salée (MIL-STD-810G)'
        assert 'toutes les fonctions radio' in engine.translate_contextual(battery, terminology())
        assert engine.translate_contextual(source, {source: 'Libellé utilisateur'}) == 'Libellé utilisateur'


def test_source_glossary_repairs_case_variants_but_honors_user_choice():
    from app.translation import RemoteEngine
    from app.terminology import terminology
    engine=RemoteEngine()
    with patch.object(engine,'_translate_prose',return_value='Ce MANPACK fonctionne.'):
        assert engine.translate_contextual('This manpack works.',terminology())=='Ce radio portable fonctionne.'
        assert engine.translate_contextual('This manpack works.',terminology({'manpack':'équipement portable'}))=='Ce équipement portable fonctionne.'
    with patch.object(engine,'_translate_prose',return_value='Un MANPACK fonctionne.'):
        assert engine.translate_contextual('Unrelated equipment works.',terminology())=='Un MANPACK fonctionne.'


def test_receive_only_cell_keeps_acronyms_and_every_frequency():
    from app.terminology import structured_technical_text
    from app.quality import check
    source='SBTW/SA RX only: 30-2600 MHz'
    target=structured_technical_text(source)
    assert target=='SBTW/SA RX uniquement : 30-2600 MHz'
    assert not check(source,target)
    assert structured_technical_text('RX only: 100–200 MHz')=='RX uniquement : 100–200 MHz'
    assert structured_technical_text(source+' under specified conditions') is None
    assert 'réception seule (RX)' in structured_technical_text(source, {'RX only':'réception seule (RX)'})


def test_acronym_checks_are_derived_from_source_for_unseen_documents():
    from app.terminology import missing_names,required_names
    assert set(missing_names('PLI, TRL and DSP improve performance.','Des informations de position et une maturité technologique élevée améliorent les performances.')) == {'PLI','TRL','DSP'}
    assert not missing_names('PLI, TRL and DSP improve performance.','PLI, TRL et DSP améliorent les performances.')
    assert required_names('THIS DOCUMENT IS FOR PUBLIC USE ONLY',{}) == {}
    assert not missing_names('DSP processing','traitement numérique',{'DSP':'traitement numérique'})


def test_all_caps_sentence_inside_mixed_block_does_not_create_false_identifiers():
    from app.terminology import required_names
    source = ('NON-EXPORT CONTROLLED: THIS DOCUMENT CONSISTS OF INFORMATION THAT IS NOT DEFINED AS '
              'CONTROLLED TECHNICAL DATA UNDER ITAR PART 120.33 OR TECHNOLOGY UNDER EAR PART 772. '
              'L3Harris develops secure radios.')
    names = required_names(source, {})
    assert 'ITAR' in names and 'EAR' in names and 'L3Harris' in names
    for ordinary in ('NON','PART','THIS','UNDER'):
        assert ordinary not in names


def test_mixed_regulatory_notice_is_translated_deterministically_before_prose():
    from app.translation import TransformersEngine
    from app.terminology import terminology
    legal = ('NON-EXPORT CONTROLLED: THIS DOCUMENT CONSISTS OF INFORMATION THAT IS NOT DEFINED AS '
             'CONTROLLED TECHNICAL DATA UNDER ITAR PART 120.33 OR TECHNOLOGY UNDER EAR PART 772.')
    prose = 'L3Harris develops secure radios.'
    engine = TransformersEngine()
    seen = []
    def translate(value):
        seen.append(value)
        return 'L3Harris développe des radios sécurisées.'
    engine._translate_prose = translate
    target = engine.translate_contextual(legal + ' ' + prose, terminology())
    assert target.startswith('NON SOUMIS AU CONTRÔLE DES EXPORTATIONS')
    assert 'ITAR' in target and 'EAR' in target and '120.33' in target and '772' in target
    assert seen == [prose]
