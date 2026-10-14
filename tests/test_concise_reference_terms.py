import unittest
from unittest.mock import patch
from app.terminology import correct_network_terms, reference_label, structured_technical_text
from app.translation import RemoteEngine


class ConciseReferenceTermsTests(unittest.TestCase):
    def test_keypad_caption_keeps_notation_and_user_glossary(self):
        source = 'HW: Remote Keypad Display Unit (RKDU)'
        with patch.object(RemoteEngine, '_translate_prose') as inference:
            target = RemoteEngine().translate_contextual(source)
        self.assertEqual(target, 'HW : clavier-afficheur distant (RKDU)')
        inference.assert_not_called()
        self.assertEqual(structured_technical_text(source, {'Remote Keypad Display Unit': 'terminal distant'}),
                         'HW : terminal distant (RKDU)')
        self.assertIsNone(structured_technical_text(source + ' with optional configuration'))

    def test_bare_frequency_ranges_are_references_but_prose_is_not(self):
        self.assertTrue(reference_label('30-512 MHz 764-2600 MHz', {}))
        self.assertTrue(reference_label('0,5–2,5 GHz', {}))
        self.assertFalse(reference_label('Supports 30-512 MHz under specified conditions', {}))

    def test_crossbanding_repair_requires_unambiguous_source(self):
        target = "Grâce à un système de routage avancé et à un réseau MANET."
        self.assertEqual(correct_network_terms('Advanced crossbanding and MANET', target),
                         'Grâce à une interconnexion interbande avancée et à un réseau MANET.')
        self.assertEqual(correct_network_terms('Advanced routing and MANET', target), target)
        self.assertEqual(correct_network_terms('Crossbanding and routing', target), target)

    def test_development_version_is_derived_from_source(self):
        target = 'Le système 4.7 est en développement.'
        self.assertEqual(correct_network_terms('Communications with 4.7 in development', target),
                         'La version 4.7 est en développement.')
        self.assertEqual(correct_network_terms('The system with 4.7 in development', target), target)
        self.assertEqual(correct_network_terms('Communications with 4.8 in development', target), target)
