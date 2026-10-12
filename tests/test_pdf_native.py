import tempfile
import unittest
from pathlib import Path
from reportlab.pdfgen import canvas
from PIL import Image,ImageDraw
from app.ocr import scan_pdf,paragraphs,separate_list_markers
from app.pdf_layout import clean_text_patch

class NativePdfTests(unittest.TestCase):
    def test_translated_native_cell_leaves_no_old_second_line(self):
        import subprocess
        from app.pdf_layout import export_pdf
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'source.pdf';out=Path(temp)/'translated.pdf'
            c=canvas.Canvas(str(path),pagesize=(612,792))
            c.setFillColorRGB(.9,.9,.9)
            c.rect(30,600,120,60,fill=1);c.rect(150,600,300,60,fill=1)
            c.setFillColorRGB(.5,.5,.5);c.setFont('Helvetica',10)
            c.drawString(155,642,'First source line')
            c.drawString(155,625,'Second source line');c.save()
            blocks=paragraphs(scan_pdf(path));body=next(x for x in blocks if 'Second' in x['text'])
            old=body['lines'][1]['box']
            export_pdf(path,['Texte traduit' for x in blocks],blocks,out)
            subprocess.run(['pdftoppm','-scale-to','2500','-singlefile','-png',str(out),str(Path(temp)/'render')],check=True,capture_output=True)
            image=Image.open(Path(temp)/'render.png').convert('RGB')
            patch=image.crop(tuple(old))
            # The translated text occupies only the first line. Any dark pixels
            # in the old second line would be surviving source letters.
            self.assertTrue(all(min(pixel)>210 for pixel in patch.getdata()))

    def test_native_cells_numbers_fonts_and_paragraphs(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'source.pdf';c=canvas.Canvas(str(path),pagesize=(612,792))
            c.setFont('Helvetica',10)
            c.drawString(30,750,'Complete sentences preserve their context')
            c.drawString(30,738,'across multiple lines of a paragraph.')
            for y in (650,610):
                c.setFillColorRGB(.95,.95,.95);c.rect(30,y,120,40,fill=1);c.rect(150,y,300,40,fill=1)
            c.setFillColorRGB(0,0,0);c.setFont('Helvetica-Bold',8)
            c.drawString(35,675,'Suppression');c.drawString(35,635,'Volume')
            c.setFont('Helvetica',8);c.drawString(155,675,'> -53 dBc');c.drawString(155,635,'167 in 3 (without battery)');c.save()
            blocks=paragraphs(scan_pdf(path))
            text=' '.join(x['text'] for x in blocks)
            self.assertIn('Complete sentences preserve their context across multiple lines',text)
            self.assertIn('> -53 dBc',text);self.assertIn('167 in³',text)
            numeric=next(x for x in blocks if '-53' in x['text'])
            self.assertNotIn('list_marker',numeric)
            self.assertTrue(numeric.get('table_cell'));self.assertTrue(numeric['native_text'])
            self.assertEqual(numeric['source_font_size'],8)

    def test_native_chevron_before_prose_is_a_marker(self):
        grey=Image.new('L',(200,50),240);ImageDraw.Draw(grey).line((10,15,15,20,10,25),fill=80,width=2)
        row=dict(native_text=True,text='> High-speed networks',box=[10,10,190,30],
                 words=[dict(text='>',box=[10,10,18,30]),dict(text='High-speed networks',box=[25,10,190,30])])
        separate_list_markers([row],grey)
        self.assertEqual(row['list_marker_text'],'›');self.assertEqual(row['text'],'High-speed networks')

    def test_native_text_next_to_photo_is_not_a_gutter_bullet(self):
        grey=Image.new('L',(200,50),255);ImageDraw.Draw(grey).rectangle((10,15,15,20),fill=0)
        row=dict(native_text=True,text='Normal prose',box=[25,10,180,30],words=[dict(text='Normal prose',box=[25,10,180,30])])
        separate_list_markers([row],grey);self.assertNotIn('list_marker',row)

    def test_text_cleaning_does_not_erase_another_colour_underline(self):
        image=Image.new('RGB',(100,60),'white');draw=ImageDraw.Draw(image)
        draw.rectangle((20,20,70,30),fill='black');draw.line((5,35,90,35),fill='red',width=2)
        patch=clean_text_patch(image,(0,15,100,40),(255,255,255),(0,0,0))
        self.assertEqual(patch.getpixel((50,20)),(255,0,0))

if __name__=='__main__':unittest.main()
