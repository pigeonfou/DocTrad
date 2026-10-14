import tempfile
import unittest
from pathlib import Path
import fitz
from reportlab.pdfgen import canvas
from app.ocr import scan_pdf, paragraphs
from app.pdf_layout import export_pdf


class ContextReflowTests(unittest.TestCase):
    def render_cell(self, root, obstacle=False):
        source=root/'source.pdf'; output=root/'output.pdf'
        c=canvas.Canvas(str(source),pagesize=(612,792))
        c.rect(30,600,120,100);c.rect(150,600,130,100)
        c.setFont('Helvetica',10)
        c.drawString(35,680,'Description');c.drawString(155,680,'Short text')
        c.setFillColorRGB(1,0,0)
        c.rect(150,645 if obstacle else 600,130,6,fill=1)
        c.save()
        blocks=paragraphs(scan_pdf(source))
        translation='Une description plus longue pour vérifier la lisibilité du texte dans la cellule.'
        report=export_pdf(source,[translation if 'Short' in b['text'] else b['text'] for b in blocks],blocks,output)
        with fitz.open(output) as doc:
            spans=[s for block in doc[0].get_text('dict')['blocks'] for line in block.get('lines',[]) for s in line['spans']
                   if s['bbox'][0]>150]
            # Sample the coloured obstacle in the rendered output, not just metadata.
            pix=doc[0].get_pixmap(matrix=fitz.Matrix(2,2))
            sample=pix.pixel(320,288 if obstacle else 378)
        return spans,report,sample

    def test_free_cell_space_keeps_four_lines_near_original_font_size(self):
        with tempfile.TemporaryDirectory() as temp:
            spans,report,_=self.render_cell(Path(temp))
            self.assertGreaterEqual(len(spans),4)
            self.assertGreaterEqual(min(s['size'] for s in spans),9.5)
            self.assertTrue(all(s['bbox'][2]<280 and s['bbox'][3]<192 for s in spans))
            self.assertFalse(any('conservée' in w['reason'] for w in report['warnings']))

    def test_visible_artwork_stops_extension_and_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            spans,_,sample=self.render_cell(Path(temp),obstacle=True)
            self.assertTrue(spans)
            self.assertLess(max(s['bbox'][3] for s in spans),141)
            self.assertGreater(sample[0],200)
            self.assertLess(sample[1],80)
            self.assertLess(sample[2],80)
