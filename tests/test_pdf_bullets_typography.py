import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from app.ocr import separate_list_markers, paragraphs, join_label_fragments
from app.pdf_layout import export_pdf, estimated_source_size


class BulletsAndTypography(unittest.TestCase):
    def test_complete_heading_fragments_join_without_guessing_capa(self):
        cell=[0,0,200,50]
        a=dict(text='Capa.',box=[10,10,50,30],table_cell=cell,confidence=.9,page=1)
        b=dict(text='bility',box=[55,11,95,30],table_cell=cell,confidence=.9,page=1)
        joined=join_label_fragments([a,b])
        self.assertEqual(joined[0]['text'],'Capability')
        self.assertEqual(joined[0]['box'],[10,10,95,30])
        self.assertEqual(len(joined),1)
        self.assertEqual(join_label_fragments([a])[0]['text'],'Capa.')

    def test_false_bullet_is_excluded_from_text_and_ink_box(self):
        grey = Image.new('L', (400,100), 255)
        line = dict(text='» File transfer', box=[13,10,180,30], confidence=.95,
                    table_cell=[0,0,390,90], page=1, ocr_group=[1,1], cell_part=0,
                    words=[dict(text='»',box=[13,17,19,23]),
                           dict(text='File',box=[27,10,70,30]),
                           dict(text='transfer',box=[80,10,180,30])])
        separate_list_markers([line], grey)
        self.assertEqual(line['text'], 'File transfer')
        self.assertEqual(line['box'], [27,10,180,30])
        self.assertEqual(line['list_marker'], [13,17,19,23])

    def test_attached_marker_uses_real_pixel_gap(self):
        grey = Image.new('L', (150,60), 255)
        draw = ImageDraw.Draw(grey)
        draw.rectangle((10,20,15,25), fill=100)
        draw.rectangle((24,10,30,30), fill=0)
        line = dict(text='~Chat', box=[10,10,80,31], table_cell=[0,0,140,50],
                    words=[dict(text='~Chat',box=[10,10,80,31])])
        separate_list_markers([line], grey)
        self.assertEqual(line['text'],'Chat')
        self.assertEqual(line['box'][0],24)

    def test_math_operator_inside_text_is_not_a_bullet(self):
        line = dict(text='Power = 12 W', box=[10,10,160,30],table_cell=[0,0,190,90],
                    words=[dict(text='Power',box=[10,10,50,30]),
                           dict(text='=',box=[60,10,70,30]),dict(text='12 W',box=[80,10,160,30])])
        separate_list_markers([line], Image.new('L',(200,100),255))
        self.assertEqual(line['text'],'Power = 12 W')
        self.assertNotIn('list_marker',line)

    def test_separate_list_items_are_not_merged_after_marker_removal(self):
        lines = [dict(text=text, box=[20,y,160,y+20], confidence=.9, page=1,
                      ocr_group=[1,1],cell_part=0,table_cell=[0,0,180,100],list_marker=[5,y,10,y+5])
                 for text,y in [('SD and HD video',10),('Chat',35)]]
        self.assertEqual(len(paragraphs(lines)),2)

    def test_source_advance_controls_size_instead_of_ink_height(self):
        from reportlab.pdfbase import pdfmetrics
        text='Frequencies'
        width=pdfmetrics.stringWidth(text,'Helvetica',8)
        segment=dict(text=text,box=[0,0,width,12])
        self.assertAlmostEqual(estimated_source_size(segment,1,1,'Helvetica'),8)

    def test_bullet_pixels_survive_export_without_false_character(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source.pdf';target=root/'target.pdf'
            c=canvas.Canvas(str(source),pagesize=(612,792))
            c.setFillColorRGB(1,.5,0);c.rect(30,695,3,3,fill=1,stroke=0)
            c.setFillColorRGB(0,0,0);c.drawString(40,690,'File transfer');c.save()
            segment=dict(text='File transfer',page=1,box=[126,280,370,330],
                         confidence=.99,list_marker=[95,295,104,304])
            export_pdf(source,['» Transfert de fichiers'],[segment],target)
            page=PdfReader(target).pages[0]
            self.assertNotIn('»',page.extract_text())
            self.assertIn('Transfert de fichiers',page.extract_text())
            # The orange original square lives in the retained background.
            im=page.images[0].image.convert('RGB')
            self.assertEqual(im.getpixel((int(31/612*im.width),int(96/792*im.height))),(255,128,0))


if __name__ == '__main__': unittest.main()
