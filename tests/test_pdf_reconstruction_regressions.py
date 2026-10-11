import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image, ImageDraw

from app.pdf_layout import export_pdf, heading, page_typography, clean_text_patch, harmonize_text_draws
from app.terminology import reference_label


class ReconstructionRegressions(unittest.TestCase):
    def test_small_print_can_be_translated_at_its_original_scale(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'source.pdf'; target=root/'target.pdf'
            c=canvas.Canvas(str(source),pagesize=(612,792))
            c.setFont('Helvetica',4.5)
            text='Registered trademarks belong to their respective owners.'
            c.drawString(320,25,text);c.save()
            scale=2500/792
            width=pdfmetrics.stringWidth(text,'Helvetica',4.5)
            segment=dict(page=1,text=text,confidence=.95,
                         box=[int(320*scale),int(763*scale),int((320+width)*scale),int(768*scale)])
            segment['lines']=[dict(segment)]
            report=export_pdf(source,['Les marques déposées appartiennent à leurs propriétaires.'],[segment],target)
            self.assertIn('marques déposées',PdfReader(target).pages[0].extract_text())
            self.assertFalse(any('zone originale conservée' in w['reason'] for w in report['warnings']))

    def test_ink_cleanup_preserves_pale_artwork_and_erases_glyph_fringe(self):
        image = Image.new('RGB',(100,60),'white')
        draw = ImageDraw.Draw(image)
        draw.rectangle((45,0,55,59),fill=(235,235,235))
        draw.rectangle((20,20,80,35),fill=(10,10,10))
        draw.rectangle((20,36,80,37),fill=(195,195,195))
        patch = clean_text_patch(image,(15,17,85,40),(255,255,255))
        self.assertEqual(patch.getpixel((35,10)),(235,235,235))
        self.assertEqual(patch.getpixel((10,20)),(255,255,255))
        self.assertEqual(patch.getpixel((35,0)),(235,235,235))

    def test_fitted_body_fonts_share_size_without_enlarging_text(self):
        font='RegressionDejaVu'
        pdfmetrics.registerFont(TTFont(font,'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        segments=[dict(text='Body paragraph'),dict(text='Other paragraph')]
        draws=[(0,100,font,8,'Corps de texte',1,(0,0,0),False,0),
               (0,50,font,7.5,'Autre paragraphe',1,(0,0,0),False,1)]
        output=harmonize_text_draws(draws,segments,{0:8,1:8},set())
        self.assertEqual([d[3] for d in output],[7.5,7.5])
        self.assertGreater(output[0][1],100)

    def test_neighbouring_rule_is_not_interpolated_into_erased_text(self):
        image=Image.new('RGB',(100,60),'white')
        draw=ImageDraw.Draw(image)
        draw.rectangle((20,20,80,35),fill='black')
        draw.line((0,40,99,40),fill=(220,220,220))
        patch=clean_text_patch(image,(15,17,85,40),(255,255,255))
        self.assertEqual(patch.getpixel((35,10)),(255,255,255))
        self.assertEqual(image.getpixel((50,40)),(220,220,220))

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
            masks=[i for i,(_,op) in enumerate(operations) if op in (b'Do',b'f',b'f*',b'B',b'B*')]
            text=[i for i,(_,op) in enumerate(operations) if op in (b'Tj',b'TJ')]
            self.assertTrue(masks and text)
            self.assertLess(max(masks),min(text))


if __name__ == '__main__': unittest.main()
