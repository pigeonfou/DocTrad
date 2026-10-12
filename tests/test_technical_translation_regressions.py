import unittest
from unittest.mock import patch
from types import SimpleNamespace
from PIL import Image
from app.ocr import recover_legal_small_print
from app.terminology import correct_network_terms

class TechnicalTranslationRegressions(unittest.TestCase):
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
