from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.pdf_layout import export_pdf


def source_pdf(tmp_path):
    background = tmp_path / 'background.png'
    Image.new('RGB', (612, 792), (230, 230, 230)).save(background)
    path = tmp_path / 'original.pdf'
    c = canvas.Canvas(str(path), pagesize=(612, 792))
    for _ in range(2):
        c.drawImage(str(background), 0, 0, width=612, height=792)
        c.setFillColorRGB(0, .3, .8)
        c.rect(400, 400, 100, 100, fill=1, stroke=0)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(60, 700, 'Power supply: 12 VDC.')
        c.showPage()
    c.save()
    return path


def test_layout_retains_pages_artwork_and_translated_text(tmp_path):
    from app.ocr import scan_pdf
    source = source_pdf(tmp_path)
    segments = scan_pdf(source)
    targets = ['Alimentation : 12 VDC.' for segment in segments]
    output = tmp_path / 'translation.pdf'
    report = export_pdf(source, targets, segments, output)
    reader = PdfReader(output)
    assert len(reader.pages) == 2
    assert report['warnings'] == []
    for page in reader.pages:
        assert list(page.mediabox) == [0, 0, 612, 792]
        assert 'Alimentation : 12 VDC.' in page.extract_text()
        assert len(page.images) >= 1
        # Full original page artwork is retained, including the blue figure.
        im = page.images[0].image.convert('RGB')
        assert im.getpixel((int(450/612*im.width), int((792-450)/792*im.height))) == (0, 76, 204)


def test_overflow_is_reported_and_not_clipped(tmp_path):
    from app.ocr import scan_pdf
    source = source_pdf(tmp_path)
    segments = scan_pdf(source)
    report = export_pdf(source, ['Très long '*200]*len(segments), segments, tmp_path/'translation.pdf')
    assert all('trop longue' in warning['reason'] for warning in report['warnings'])
    assert len(report['warnings']) == len(segments)


def test_invalid_coordinates_refused(tmp_path):
    source = source_pdf(tmp_path)
    with pytest.raises(ValueError, match='hors de la page'):
        export_pdf(source, ['Bonjour'], [{'page':1, 'box':[-1,0,20,20]}], tmp_path/'translation.pdf')
    assert not (tmp_path/'translation.pdf').exists()


def test_tsm_reference_document(tmp_path):
    import hashlib
    from app.ocr import scan_pdf
    source = Path(__file__).parent / 'fixtures' / 'tsm-waveform-reference.pdf'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == '9bc58a21ffa56f89dcec9e201f17d77b606135462a9c23b8e23fc274467b9e4b'
    reader = PdfReader(source)
    assert len(reader.pages) == 2
    assert all(not (page.extract_text() or '').strip() for page in reader.pages)
    segments = scan_pdf(source)
    assert len(segments) >= 90
    # Table headings are independent cells, not one phrase across the border.
    assert any(item['text'] == 'Features' for item in segments)
    assert any(item['text'] == 'Capability' for item in segments)
    assert not any(item['page'] == 2 and 480 < item['box'][1] < 1900
                   and item['box'][0] < 480 < item['box'][2] for item in segments)
    replacements = {'Features': 'Critères', 'Capability': 'Capacité',
                    'Frequencies': 'Fréquences', 'Data': 'Données',
                    'TECHNICAL FEATURES OF THE': 'CARACTÉRISTIQUES TECHNIQUES'}
    targets = [replacements.get(item['text'], item['text']) for item in segments]
    report = export_pdf(source, targets, segments, tmp_path/'translation.pdf')
    output = PdfReader(tmp_path/'translation.pdf')
    assert len(output.pages) == 2
    assert all(list(page.mediabox) == [0, 0, 612, 792] for page in output.pages)
    assert 'Fréquences' in output.pages[1].extract_text()
    assert 'Capacité' in output.pages[1].extract_text()
    assert report['mode'] == 'page_background_with_text_overlay'
    assert all(page.images for page in output.pages)
