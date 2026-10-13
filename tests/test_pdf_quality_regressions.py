"""Offline regressions for uncertain words, branding and visible untranslated text."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from app.ocr import recognize, paragraphs
from app.pdf_layout import export_pdf
from app.terminology import preserved_name, correct_network_terms


class PDFQualityRegressions(unittest.TestCase):
    def test_one_uncertain_word_does_not_veto_a_reliable_line(self):
        tsv = 'level\tblock_num\tpar_num\tline_num\tleft\ttop\twidth\theight\tconf\ttext\n'
        tsv += '5\t1\t1\t1\t20\t20\t110\t20\t98\tCapabilities\n'
        tsv += '5\t1\t1\t1\t140\t20\t10\t20\t5\t:\n'
        tsv += '5\t1\t1\t1\t160\t20\t60\t20\t20\tSDR\n'
        with tempfile.TemporaryDirectory() as root:
            image = Path(root)/'ocr.png'
            Image.new('RGB', (400,100), 'white').save(image)
            with patch('app.ocr.subprocess.run', return_value=SimpleNamespace(stdout=tsv)):
                line = recognize(image)[0]
        self.assertGreater(line['confidence'], .65)
        self.assertEqual(line['minimum_confidence'], .2)

    def test_paragraph_confidence_retains_word_uncertainty(self):
        a = dict(text='Reliable communications across many nodes', box=[10,10,300,30],
                 confidence=.95, minimum_confidence=.4, page=1, ocr_group=[1,1], cell_part=0)
        b = dict(text='today.', box=[10,35,70,55], confidence=.5,
                 minimum_confidence=.5, page=1, ocr_group=[1,1], cell_part=0)
        result = paragraphs([a,b])[0]
        self.assertGreater(result['confidence'], .85)
        self.assertEqual(result['minimum_confidence'], .4)

    def test_logo_corruption_is_protected_without_matching_prose(self):
        self.assertTrue(preserved_name('Trel | estWare.'))
        self.assertFalse(preserved_name('TrellisWare provides secure communications.'))

    def test_trl_acronym_correction_requires_source_anchor(self):
        self.assertEqual(correct_network_terms('TRL 9 technology', 'Technologie TMT 9'), 'Technologie TRL 9')
        self.assertEqual(correct_network_terms('TMT module', 'Module TMT'), 'Module TMT')

    def test_export_reports_unchanged_prose_but_not_brand(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root/'source.pdf'
            c = canvas.Canvas(str(source), pagesize=(612,792))
            c.drawString(30,700,'Secure communications')
            c.save()
            segments = [dict(text='Secure communications', page=1, box=[95,255,800,310]),
                        dict(text='TrellisWare', page=1, box=[1000,255,1500,310])]
            report = export_pdf(source, [s['text'] for s in segments], segments, root/'output.pdf')
            self.assertEqual(len(report['warnings']), 1)
            self.assertEqual(report['warnings'][0]['segment'], 0)

    def test_uppercase_heading_uses_bold_font(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root/'source.pdf'
            c = canvas.Canvas(str(source), pagesize=(612,792))
            c.drawString(30,700,'TECHNICAL FEATURES')
            c.save()
            target = root/'output.pdf'
            export_pdf(source, ['CARACTÉRISTIQUES'], [dict(text='TECHNICAL FEATURES',
                       page=1, box=[95,255,850,310], confidence=.99)], target)
            fonts = PdfReader(target).pages[0]['/Resources']['/Font'].get_object()
            self.assertTrue(any('Bold' in str(f.get_object().get('/BaseFont')) for f in fonts.values()))


if __name__ == '__main__':
    unittest.main()


def test_unchanged_native_table_label_is_visible_and_uses_the_label_font(tmp_path):
    import re
    source=tmp_path/'source.pdf';target=tmp_path/'target.pdf'
    pdf=canvas.Canvas(str(source),pagesize=(612,792))
    pdf.setFont('Helvetica',7)
    pdf.drawString(40,740,'Dimensions');pdf.drawString(175,740,'7 cm');pdf.save()
    ratio=2500/792
    def scaled(box):return [round(v*ratio) for v in box]
    common=dict(page=1,confidence=.99,native_text=True,source_font_size=7,source_bold=False)
    segments=[dict(common,text='Dimensions',box=scaled([40,46,86,54]),table_cell=scaled([35,32,170,67])),
              dict(common,text='7 cm',box=scaled([175,46,200,54]),table_cell=scaled([170,32,310,67]))]
    report=export_pdf(source,['Dimensions','7 cm'],segments,target)
    page=PdfReader(target).pages[0]
    blocks=re.findall(r'BT(.*?)ET',page.get_contents().get_data().decode('latin-1'),re.S)
    label=next(block for block in blocks if '(Dimensions)' in block)
    assert '3 Tr' not in label
    font_name=re.findall(r'/(\S+)\s+[\d.]+\s+Tf',label)[-1]
    assert 'Bold' in str(page['/Resources']['/Font']['/'+font_name].get_object()['/BaseFont'])
    assert report['typography_groups'][0]['role']=='table_labels'
