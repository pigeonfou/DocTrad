import tempfile
import unittest
from pathlib import Path
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from app.pdf_layout import export_pdf, content_right, page_typography
from app.ocr import scan_pdf


class SelectableLayout(unittest.TestCase):
    def test_unchanged_product_references_are_real_pdf_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'source.pdf'; target=root/'target.pdf'
            c=canvas.Canvas(str(source),pagesize=(612,792))
            c.drawString(40,700,'TW-950 TSM Shadow Radio');c.save()
            segments=scan_pdf(source)
            export_pdf(source,[s['text'] for s in segments],segments,target)
            self.assertEqual(' '.join(s['text'] for s in segments),
                             ' '.join(PdfReader(target).pages[0].extract_text().split()))

    def test_short_words_fit_using_visible_ink_not_full_font_height(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'source.pdf'; target=root/'target.pdf'
            c=canvas.Canvas(str(source),pagesize=(612,792))
            c.setFont('Helvetica',10);c.drawString(40,700,'Chat');c.save()
            segments=scan_pdf(source)
            for segment in segments: segment['confidence']=1
            export_pdf(source,['Discussion' for _ in segments],segments,target)
            import fitz
            spans=[span for block in fitz.open(target)[0].get_text('dict')['blocks']
                   for line in block.get('lines',[]) for span in line['spans']]
            self.assertTrue(spans)
            self.assertGreater(spans[0]['size'],8)

    def test_uncertain_short_word_is_confirmed_by_a_second_reading(self):
        from PIL import Image, ImageDraw, ImageFont
        from app.ocr import recover_uncertain_short_lines
        image=Image.new('L',(200,80),255)
        ImageDraw.Draw(image).text((20,20),'Chat',font=ImageFont.truetype(
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',24),fill=0)
        lines=[dict(text='Chat',box=[20,24,78,48],confidence=.28)]
        recover_uncertain_short_lines(lines,image)
        self.assertGreaterEqual(lines[0]['confidence'],.65)
        self.assertEqual(lines[0]['text'],'Chat')

    def test_text_keeps_clearance_above_a_footer_on_its_right(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'source.pdf'; target=root/'target.pdf'
            c=canvas.Canvas(str(source),pagesize=(612,792))
            c.setFont('Helvetica',10)
            c.drawString(40,100,'Ease of use')
            c.drawString(200,89,'EXAMPLE.COM');c.save()
            segments=scan_pdf(source)
            translations=['Une interface facile à utiliser pour tous les utilisateurs'
                          if 'Ease' in x['text'] else x['text'] for x in segments]
            export_pdf(source,translations,segments,target)
            import fitz
            spans=[span for block in fitz.open(target)[0].get_text('dict')['blocks']
                   for line in block.get('lines',[]) for span in line['spans']]
            translated=[span for span in spans if 'Une interface' in span['text']]
            self.assertTrue(translated)
            self.assertLess(translated[0]['bbox'][2],200)

    def test_content_margin_is_not_the_page_edge(self):
        segments=[dict(page=1,box=[60,100,920,180],lines=[{}]),
                  dict(page=1,box=[700,850,950,900])]
        self.assertEqual(content_right(segments,1,1000),920)

    def test_similar_source_sizes_share_a_common_size(self):
        text='Reliable communications'
        advance=pdfmetrics.stringWidth(text,'Helvetica',1)
        segments=[dict(page=1,text=text,box=[20,100+i*30,20+advance*size,120+i*30])
                  for i,size in enumerate([7,7.4])]
        sizes=page_typography(segments,1,1,1,'Helvetica','Helvetica-Bold')
        self.assertEqual(sizes[0],sizes[1])
        self.assertAlmostEqual(sizes[0],7.2)

    def test_different_source_heading_sizes_are_not_flattened(self):
        text='Reliable communications'
        advance=pdfmetrics.stringWidth(text,'Helvetica',1)
        segments=[dict(page=1,text=text,box=[20,100+i*30,20+advance*size,125+i*30])
                  for i,size in enumerate([7,14])]
        sizes=page_typography(segments,1,1,1,'Helvetica','Helvetica-Bold')
        self.assertNotEqual(sizes[0],sizes[1])


if __name__ == '__main__': unittest.main()
