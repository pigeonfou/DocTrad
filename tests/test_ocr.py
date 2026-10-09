import shutil
import pytest
from app.ocr import recognize,scan_pdf

@pytest.fixture
def annotated(tmp_path):
    from PIL import Image,ImageDraw,ImageFont
    image=Image.new('RGB',(1400,500),'white')
    draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',42)
    draw.text((70,100),'Power supply voltage: 12 VDC.',font=font,fill='black')
    draw.text((70,200),'Connect J3 to the control board.',font=font,fill='black')
    path=tmp_path/'annotated.png';image.save(path);return path

@pytest.mark.skipif(not shutil.which('tesseract'),reason='Tesseract missing')
def test_real_ocr_boxes_confidence(annotated):
    lines=recognize(annotated)
    assert any('12 VDC' in line['text'] for line in lines)
    assert all(len(line['box'])==4 and 0<=line['confidence']<=1 for line in lines)

@pytest.mark.skipif(not shutil.which('pdftoppm') or not shutil.which('tesseract'),reason='OCR prerequisites missing')
def test_real_scanned_pdf(annotated,tmp_path):
    from reportlab.pdfgen import canvas
    from app.documents import extract,exports
    path=tmp_path/'scanned.pdf';c=canvas.Canvas(str(path));c.drawImage(str(annotated),20,500,width=550,height=196);c.save()
    lines=scan_pdf(path)
    assert any('12 VDC' in line['text'] for line in lines)
    assert all(line['page']==1 for line in lines)
    texts=extract(path,'.pdf');assert texts
    exports(path,'.pdf',['Tension alimentation : 12 VDC.']*len(texts),tmp_path/'out')
    assert (tmp_path/'out/translation.docx').is_file()

@pytest.mark.skipif(not shutil.which('pdftoppm') or not shutil.which('tesseract'),reason='OCR prerequisites missing')
def test_reference_heading_does_not_include_graphic_ornament(tmp_path):
    import subprocess
    from pathlib import Path
    source = Path(__file__).parent/'fixtures/tsm-waveform-reference.pdf'
    prefix = tmp_path/'reference-heading'
    subprocess.run(['pdftoppm', '-f', '1', '-l', '1', '-singlefile',
                    '-scale-to', '2500', '-png', str(source), str(prefix)], check=True)
    lines = recognize(prefix.with_suffix('.png'))
    heading = next(line for line in lines if 'Product Specification Sheet' in line['text'])
    assert heading['text'] == 'Product Specification Sheet'
    # The text begins after the ornament, preserving its bitmap.
    assert heading['box'][0] > 80

