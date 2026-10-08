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


def test_invalid_coordinates_reported_without_blocking_export(tmp_path):
    source = source_pdf(tmp_path)
    report = export_pdf(source, ['Bonjour'], [{'page':1, 'box':[-1,0,20,20]}], tmp_path/'translation.pdf')
    assert 'Coordonnées OCR invalides' in report['warnings'][0]['reason']
    assert len(PdfReader(tmp_path/'translation.pdf').pages) == 2


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
    for item in segments:
        x0,y0,x1,y1 = item['box']
        width,height = item['image_size']
        assert 0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height
    assert any(item['text'].startswith('Specifications subject to change') for item in segments)
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
    all_zones = export_pdf(source, ['FR : '+item['text'] for item in segments], segments, tmp_path/'all-zones.pdf')
    assert not any('Coordonnées OCR invalides' in warning['reason'] for warning in all_zones['warnings'])
    assert len(PdfReader(tmp_path/'all-zones.pdf').pages) == 2



def test_multiline_paragraph_wraps_and_preserves_artwork(tmp_path):
    from app.ocr import paragraphs, scan_pdf
    source = tmp_path / 'paragraph.pdf'
    c = canvas.Canvas(str(source), pagesize=(612, 792))
    c.setFillColorRGB(0, .3, .8)
    c.rect(400, 640, 100, 100, fill=1, stroke=0)
    c.setFillColorRGB(0, 0, 0)
    c.setFont('Helvetica', 12)
    c.drawString(60, 700, 'Reliable communications across multiple')
    c.drawString(60, 683, 'hops with steady throughput.')
    c.save()
    lines = scan_pdf(source)
    # Fix only grouping metadata: OCR text, positions and confidence stay real.
    for item in lines:
        item['ocr_group'] = [1, 1]
        item['confidence'] = 1.0  # This test checks layout, not OCR uncertainty.
    segments = paragraphs(lines)
    assert len(segments) == 1 and len(segments[0]['lines']) == 2
    target = 'Communications fiables sur plusieurs sauts avec un débit constant.'
    destination = tmp_path / 'paragraph-translated.pdf'
    report = export_pdf(source, [target], segments, destination)
    assert not report['warnings']
    page = PdfReader(destination).pages[0]
    assert ' '.join(page.extract_text().split()) == target
    image = page.images[0].image.convert('RGB')
    assert image.getpixel((int(450/612*image.width),int((792-690)/792*image.height))) == (0,76,204)


def test_logo_lettering_is_not_overwritten_even_with_confident_ocr(tmp_path):
    source = source_pdf(tmp_path)
    output = tmp_path/'logo-protected.pdf'
    export_pdf(source, ['Trill isWa re'], [{'text':'Trell isWa re', 'page':1,
               'box':[1465,116,1808,181], 'confidence':.95}], output)
    assert 'Trill isWa re' not in PdfReader(output).pages[0].extract_text()


def test_graphic_tagline_keeps_original_ornaments(tmp_path):
    source = source_pdf(tmp_path); output = tmp_path/'tagline.pdf'
    export_pdf(source, ["©— Quand rien ne fonctionne —©"], [{'text':'©— When Nothing Else Works —©',
               'page':1, 'box':[300,1800,1700,1900], 'confidence':.98}], output)
    assert 'Quand rien' not in PdfReader(output).pages[0].extract_text()


def test_real_table_continuations_are_grouped_in_their_cells():
    from app.documents import analyze
    source = Path(__file__).parent/'fixtures/tsm-waveform-reference.pdf'
    segments = analyze(source, '.pdf')
    texts = [s['text'] for s in segments]
    assert 'Supported Software Defined Radio (SDR) Platforms' in texts
    assert 'End User Device (EUD) Support' in texts
    assert any(t.startswith('Supports up to 8 spatial MANET hops') and t.endswith('per hop in Long Range Mode') for t in texts)
    assert any(t.startswith('TrellisWare radios can be left unattended') and t.endswith('with SOCOM Tactical Communications (STC) Security') for t in texts)
    assert not any('Supported Software Defined' in t and 'TrellisWare radio products' in t for t in texts)
