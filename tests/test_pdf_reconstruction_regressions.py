import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics

from app.pdf_layout import export_pdf, heading, page_typography
from app.terminology import reference_label


class ReconstructionRegressions(unittest.TestCase):
    def test_acronym_and_long_label_share_column_typography(self):
        cell = [0,0,150,100]
        text = 'Frequencies'
        width = pdfmetrics.stringWidth(text,'Helvetica-Bold',9)
        segments = [dict(page=1,text=text,box=[10,10,10+width,22],table_cell=cell),
                    dict(page=1,text='PLI',box=[10,40,25,64],table_cell=cell),
                    dict(page=1,text='Content',box=[160,10,210,22],table_cell=[150,0,700,100])]
        sizes = page_typography(segments,1,1,1,'Helvetica','Helvetica-Bold')
        self.assertAlmostEqual(sizes[0],9)
        self.assertEqual(sizes[0],sizes[1])

    def test_glossary_list_items_do_not_become_bold_headings(self):
        for text in ('Chat','File transfer','SD and HD video'):
            self.assertFalse(heading(dict(text=text,table_cell=[0,0,100,100],list_marker=[1,1,4,4])))
        self.assertTrue(heading(dict(text='TECHNICAL FEATURES')))

    def test_postal_metadata_is_preserved_without_protecting_prose(self):
        self.assertTrue(reference_label('10641 Scripps Summit Court, Suite 100, San Diego, CA 92131',{}))
        self.assertTrue(reference_label('Tel. 858.753.1600 | info@trellisware.com',{}))
        self.assertFalse(reference_label('32 groups can operate on a network.',{}))

    def test_reference_layer_does_not_hide_subsequent_translation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'source.pdf'; target=root/'target.pdf'
            c=canvas.Canvas(str(source),pagesize=(612,792))
            c.drawString(40,700,'TW-950 TSM Shadow Radio')
            c.drawString(40,650,'Reliable communications');c.save()
            segments=[dict(page=1,text='TW-950 TSM Shadow Radio',box=[126,260,800,300]),
                      dict(page=1,text='Reliable communications',box=[126,420,800,460])]
            export_pdf(source,[segments[0]['text'],'Communications fiables'],segments,target)
            page=PdfReader(target).pages[0]
            mode, stack, rendered = 0, [], []
            for operands,operator in page.get_contents().operations:
                if operator == b'q': stack.append(mode)
                elif operator == b'Q': mode=stack.pop()
                elif operator == b'Tr': mode=int(operands[0])
                elif operator in (b'Tj',b'TJ'): rendered.append(mode)
            self.assertEqual(rendered,[3,0])
            self.assertIn('Communications fiables',page.extract_text())

    def test_source_masks_cannot_clip_already_translated_glyphs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'source.pdf'; target=root/'target.pdf'
            c=canvas.Canvas(str(source),pagesize=(612,792))
            c.drawString(40,700,'First line');c.drawString(40,690,'Second line');c.save()
            segments=[dict(page=1,text='First line',box=[126,260,500,300]),
                      dict(page=1,text='Second line',box=[126,290,500,330])]
            export_pdf(source,['Première ligne','Deuxième ligne'],segments,target)
            operations=PdfReader(target).pages[0].get_contents().operations
            masks=[i for i,(_,op) in enumerate(operations) if op in (b'f',b'f*',b'B',b'B*')]
            text=[i for i,(_,op) in enumerate(operations) if op in (b'Tj',b'TJ')]
            self.assertTrue(masks and text)
            self.assertLess(max(masks),min(text))


if __name__ == '__main__': unittest.main()
