import unittest
from unittest.mock import patch
from types import SimpleNamespace
from PIL import Image
from app.ocr import recover_legal_small_print
from app.terminology import correct_network_terms

class TechnicalTranslationRegressions(unittest.TestCase):
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

if __name__=='__main__':unittest.main()
