"""Offline PDF page reconstruction; source artwork remains the page background.

OCR coordinates are in the 2500-pixel Poppler rendering used at analysis time.
This is a visual export, not restoration of the source's editable vector text.
"""
import json
import re
from statistics import median
from collections import Counter
import subprocess
import tempfile
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .terminology import preserved_name, reference_label, DEFAULT_TERMS


def estimated_source_size(segment, sx, sy, font):
    """Estimate point size from source advances, not a label's ink height alone.

    Image PDFs have no recoverable font metadata. A short word with tall
    capitals/descenders must not acquire a larger size than nearby body text.
    """
    estimates = []
    for line in segment.get('lines') or [segment]:
        text = line.get('text', '')
        box = line['box']
        advance = pdfmetrics.stringWidth(text, font, 1)
        if advance > 0 and len(text.strip()) >= 4:
            estimates.append(min((box[2]-box[0])*sx/advance, (box[3]-box[1])*sy/.55))
    return median(estimates) if estimates else (segment['box'][3]-segment['box'][1])*sy/.95


def export_pdf(original, targets, segments, destination):
    if len(targets) != len(segments):
        raise ValueError('Nombre de segments PDF incohérent ; réanalyser le document')
    reader = PdfReader(original)
    if reader.is_encrypted:
        raise ValueError('PDF chiffré non supporté')
    if len(reader.pages) > 500:
        raise ValueError('PDF limité à 500 pages')
    for segment in segments:
        page = segment.get('page')
        if not isinstance(page, int) or not 1 <= page <= len(reader.pages) or not segment.get('box'):
            raise ValueError('Coordonnées PDF absentes ; réanalyser le document')
    font_path = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not font_path.is_file():
        raise ValueError('Police locale DejaVu Sans absente')
    font = 'DocTradDejaVu'
    if font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font, str(font_path)))
    bold_path = font_path.with_name('DejaVuSans-Bold.ttf')
    bold_font = 'DocTradDejaVuBold'
    if bold_path.is_file() and bold_font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(bold_font, str(bold_path)))
    if not bold_path.is_file(): bold_font = font
    regular_font = font
    report = {'mode': 'page_background_with_text_overlay', 'pages': len(reader.pages),
              'typography': 'estimated_from_raster_source',
              'human_review_required': True, 'warnings': []}
    destination = Path(destination)
    pending = destination.with_suffix('.pending.pdf')
    try:
        pdf = canvas.Canvas(str(pending), pageCompression=1)
        with tempfile.TemporaryDirectory(prefix='doctrad-layout-') as temp:
            for page_number, source_page in enumerate(reader.pages, 1):
                prefix = Path(temp) / 'page'
                subprocess.run(['pdftoppm', '-f', str(page_number), '-l', str(page_number),
                                '-singlefile', '-cropbox', '-scale-to', '2500', '-png', str(original), str(prefix)],
                               capture_output=True, check=True, timeout=120)
                with Image.open(prefix.with_suffix('.png')) as raster:
                    image = raster.convert('RGB')
                # Poppler honours CropBox and rotation: take the same displayed size.
                width, height = float(source_page.cropbox.width), float(source_page.cropbox.height)
                if int(source_page.get('/Rotate', 0)) % 180:
                    width, height = height, width
                pdf.setPageSize((width, height))
                pdf.drawImage(ImageReader(image), 0, 0, width=width, height=height)
                sx, sy = width / image.width, height / image.height
                for index, (target, segment) in enumerate(zip(targets, segments)):
                    if segment.get('page') != page_number:
                        continue
                    box = segment.get('box')
                    if not box or len(box) != 4:
                        raise ValueError('Coordonnées PDF absentes ; réanalyser le document')
                    if segment.get('image_size') and list(image.size) != segment['image_size']:
                        raise ValueError('Dimensions OCR différentes du rendu PDF')
                    source_text = segment.get('text', '')
                    letters = ''.join(c for c in source_text if c.isalpha())
                    is_heading = ((len(letters) >= 4 and letters.isupper())
                                  or (source_text.strip() in DEFAULT_TERMS and len(source_text) <= 65))
                    font = bold_font if is_heading else regular_font
                    if target == source_text:
                        if (re.search(r'[A-Za-z]{3,}', source_text)
                                and not preserved_name(source_text)
                                and not reference_label(source_text, {})):
                            report['warnings'].append({'segment': index, 'page': page_number,
                                'reason': 'Texte identique à la source : vérifier la traduction'})
                        continue
                    if preserved_name(segment.get('text', '')):
                        # A logo is artwork, including lettering misread by OCR.
                        continue
                    x0, y0, x1, y1 = [int(value) for value in box]
                    if not (0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height):
                        report['warnings'].append({'segment': index, 'page': page_number,
                            'reason': 'Coordonnées OCR invalides : zone originale conservée ; réanalyser le document'})
                        continue
                    if not target.strip():
                        raise ValueError('Traduction PDF vide')
                    if segment.get('list_marker'):
                        # The original bullet remains an image. Never draw the
                        # punctuation a model invents in its place a second time.
                        target = re.sub(r'^[\s•●▪*~–—»«=−-]+', '', target)
                        if not target.strip(): raise ValueError('Traduction PDF vide')
                    # Average line confidence avoids rejecting a whole paragraph for one word.
                    if segment.get('confidence', 1) < .65:
                        report['warnings'].append({'segment': index, 'page': page_number,
                            'reason': 'OCR très incertain : zone originale conservée'})
                        continue
                    # Include antialiasing just outside Tesseract's ink box.
                    mask = (max(0, x0-2), max(0, y0-2), min(image.width, x1+2), min(image.height, y1+2))
                    patch = image.crop(mask)
                    colours = patch.getcolors(patch.width * patch.height)
                    # JPEG backgrounds contain many nearly identical colours.
                    # Cluster them before measuring uniformity instead of requiring
                    # exact RGB equality (which misclassifies white table cells).
                    clusters = Counter()
                    for count, colour in colours:
                        clusters[tuple((value+8)//16 for value in colour)] += count
                    background_bin, background_count = clusters.most_common(1)[0]
                    background_colours = [(count, colour) for count, colour in colours
                                          if tuple((value+8)//16 for value in colour) == background_bin]
                    centre = tuple(round(sum(count*colour[channel] for count, colour in background_colours)
                                         / background_count) for channel in range(3))
                    background_colours = [(count, colour) for count, colour in colours
                                          if max(abs(a-b) for a,b in zip(colour, centre)) <= 24]
                    background_count = sum(count for count, _ in background_colours)
                    background = tuple(round(sum(count*colour[channel] for count, colour in background_colours)
                                             / background_count) for channel in range(3))
                    # A photograph cannot be reconstructed with a solid rectangle.
                    if background_count / (patch.width * patch.height) < .25:
                        report['warnings'].append({'segment': index, 'page': page_number,
                            'reason': 'Fond graphique complexe : zone originale conservée'})
                        continue
                    foreground = max((colour for _, colour in colours),
                                     key=lambda colour: sum((a-b)**2 for a,b in zip(colour, background)))
                    x, y = x0*sx, height-y1*sy
                    available_width, available_height = (x1-x0)*sx, (y1-y0)*sy
                    # A short label may use blank space inside its cell. Stop at
                    # a neighbouring text box or any visible border/illustration.
                    limit = image.width-2
                    for neighbour in segments:
                        other = neighbour.get('box')
                        if neighbour.get('page') == page_number and other and other[0] > x1 and other[1] < y1 and other[3] > y0:
                            limit = min(limit, int(other[0])-4)
                    pixels = image.load()
                    end = x1
                    for column in range(x1+3, limit):
                        contrasting = sum(max(abs(a-b) for a,b in zip(pixels[column, row], background)) > 30
                                          for row in range(y0, y1))
                        if contrasting > (y1-y0)*.2:
                            break
                        end = column-2
                    available_width = max(available_width, (end-x0)*sx)
                    cell = segment.get('table_cell')
                    cell_width = None
                    if cell and len(cell) == 4 and cell[0] <= x0 < x1 <= cell[2]:
                        # Use cell whitespace, stopping before the border and any
                        # adjacent segment at the same vertical position.
                        cell_width = max((x1-x0)*sx, (min(cell[2]-5, limit, end)-x0)*sx)
                        available_width = min(available_width, cell_width)
                    source_lines = segment.get('lines', [])
                    if source_lines:
                        # Use the original cell/paragraph width, without extending
                        # through neighbouring artwork merely to fit more prose.
                        available_width = cell_width or (x1-x0)*sx
                        line_height = max(line['box'][3]-line['box'][1] for line in source_lines)*sy
                        size = min(line_height/.95, estimated_source_size(segment, sx, sy, font))
                        def wrap(text, font_size):
                            output, current = [], ''
                            for word in text.split():
                                candidate = (current + ' ' + word).strip()
                                if current and pdfmetrics.stringWidth(candidate, font, font_size) > available_width:
                                    output.append(current); current = word
                                else:
                                    current = candidate
                            if current: output.append(current)
                            return output
                        while size >= 5:
                            wrapped = wrap(target, size)
                            ascent, descent = pdfmetrics.getAscentDescent(font, size)
                            leading = size*1.18
                            if ((len(wrapped)-1)*leading + ascent-descent <= available_height
                                and all(pdfmetrics.stringWidth(line, font, size) <= available_width for line in wrapped)):
                                break
                            size -= .25
                        if size < 5:
                            report['warnings'].append({'segment': index, 'page': page_number,
                                'reason': 'Paragraphe trop long : zone originale conservée'})
                            continue
                        if size < 7:
                            report['warnings'].append({'segment': index, 'page': page_number,
                                'reason': 'Police réduite : lisibilité à vérifier', 'font_size': round(size, 2)})
                        pdf.setFillColorRGB(*(value/255 for value in background))
                        for line in source_lines:
                            a,b,c,d = line['box']
                            pdf.rect(max(0,a-2)*sx, height-min(image.height,d+2)*sy,
                                     (min(image.width,c+2)-max(0,a-2))*sx,
                                     (min(image.height,d+2)-max(0,b-2))*sy, stroke=0, fill=1)
                        pdf.setFillColorRGB(*(value/255 for value in foreground))
                        pdf.setFont(font, size)
                        baseline = height-y0*sy-ascent
                        for line in wrapped:
                            pdf.drawString(x, baseline, line)
                            baseline -= leading
                        continue
                    size = min(available_height / .95, estimated_source_size(segment, sx, sy, font))
                    measured = pdfmetrics.stringWidth(target, font, size)
                    if measured > available_width:
                        size *= available_width / measured
                    if size < 5:
                        report['warnings'].append({'segment': index, 'page': page_number,
                            'reason': 'Traduction trop longue : zone originale conservée'})
                        continue
                    if size < 7 or size < available_height*.65:
                        report['warnings'].append({'segment': index, 'page': page_number,
                            'reason': 'Police réduite : lisibilité à vérifier', 'font_size': round(size, 2)})
                    pdf.setFillColorRGB(*(value/255 for value in background))
                    pdf.rect(mask[0]*sx, height-mask[3]*sy,
                             (mask[2]-mask[0])*sx, (mask[3]-mask[1])*sy, stroke=0, fill=1)
                    pdf.setFillColorRGB(*(value/255 for value in foreground))
                    pdf.setFont(font, size)
                    ascent, descent = pdfmetrics.getAscentDescent(font, size)
                    baseline = y + (available_height-(ascent-descent))/2-descent
                    pdf.drawString(x, baseline, target)
                pdf.showPage()
                image.close()
        pdf.save()
        pending.replace(destination)
        destination.with_name('layout-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        pending.unlink(missing_ok=True)
    return report


