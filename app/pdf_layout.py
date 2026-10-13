"""Offline PDF page reconstruction; source artwork remains the page background.

OCR coordinates are in the 2500-pixel Poppler rendering used at analysis time.
This is a visual export, not restoration of the source's editable vector text.
"""
import json
import re
from statistics import median
from collections import Counter
from functools import lru_cache
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageFont, ImageFilter
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .terminology import preserved_name, reference_label, DEFAULT_TERMS, correct_network_terms


@lru_cache(maxsize=4)
def ink_font(font):
    return ImageFont.truetype(str(pdfmetrics.getFont(font).face.filename), 1000)


def ink_metrics(text, font, size):
    """Visible glyph bounds, unlike the font's full ascender/descender box."""
    _, top, _, bottom = ink_font(font).getbbox(text, anchor='ls')
    return -top*size/1000, bottom*size/1000


def estimated_source_size(segment, sx, sy, font):
    """Estimate point size from source advances, not a label's ink height alone.

    Image PDFs have no recoverable font metadata. A short word with tall
    capitals/descenders must not acquire a larger size than nearby body text.
    """
    if segment.get('source_font_size'): return segment['source_font_size']
    estimates = []
    for line in segment.get('lines') or [segment]:
        text = line.get('text', '')
        box = line['box']
        advance = pdfmetrics.stringWidth(text, font, 1)
        if advance > 0 and len(text.strip()) >= 4:
            estimates.append(min((box[2]-box[0])*sx/advance, (box[3]-box[1])*sy/.55))
    return median(estimates) if estimates else (segment['box'][3]-segment['box'][1])*sy/.76


def heading(segment):
    # A glossary entry describes meaning, not typography. Table list items
    # such as Chat and File transfer are ordinary body text.
    if segment.get('table_cell') and segment.get('list_marker'):
        return False
    if segment.get('native_text') and 'source_bold' in segment: return bool(segment['source_bold'])
    text = segment.get('text', '')
    letters = ''.join(c for c in text if c.isalpha())
    return ((len(letters) >= 4 and letters.isupper())
            or (text.strip() in DEFAULT_TERMS and len(text) <= 65))


def table_labels(segments, page):
    cells = [s['table_cell'] for s in segments
             if s.get('page') == page and s.get('table_cell')]
    if not cells: return set()
    label_cells=set()
    for cell in cells:
        neighbour=next((other for other in cells if abs(other[0]-cell[2]) <= 2
                       and abs(other[1]-cell[1]) <= 2 and abs(other[3]-cell[3]) <= 2),None)
        if neighbour and cell[2]-cell[0] < (neighbour[2]-cell[0])*.6:
            label_cells.add(tuple(cell))
    return {i for i,s in enumerate(segments) if s.get('page') == page
            and tuple(s.get('table_cell',[])) in label_cells}


def page_typography(segments, page, sx, sy, regular, bold):
    """Share source size estimates across nearby sizes in the same text role."""
    roles = {}
    labels = table_labels(segments, page)
    for index, segment in enumerate(segments):
        if segment.get('page') != page or segment.get('confidence',1) < .65: continue
        if preserved_name(segment.get('text','')): continue
        cell = segment.get('table_cell')
        role = ('label' if index in labels else 'table' if cell else 'body',
                index in labels or heading(segment))
        size = estimated_source_size(segment,sx,sy,bold if role[1] else regular)
        if 5 <= size <= 48: roles.setdefault(role,[]).append((size,index))
    sizes = {}
    for role, entries in roles.items():
        if role[0] == 'label':
            # Very short acronyms have too little ink to estimate independently.
            reliable = [size for size,index in entries
                        if len(segments[index]['text'].strip()) >= 4]
            common = median(reliable or [size for size,_ in entries])
            for _,index in entries: sizes[index] = common
            continue
        clusters = []
        for size,index in sorted(entries):
            if not clusters or size > clusters[-1][0][0]*1.12:
                clusters.append([])
            clusters[-1].append((size,index))
        for cluster in clusters:
            common = median(size for size,_ in cluster)
            for _,index in cluster: sizes[index] = common
    return sizes


def content_right(segments, page, image_width):
    """Infer a content margin from wide paragraphs and table borders."""
    rights = []
    for segment in segments:
        if segment.get('page') != page: continue
        box = segment.get('box')
        if not box: continue
        cell = segment.get('table_cell')
        if cell: rights.append(cell[2])
        elif (segment.get('lines') and box[0] < image_width*.25
              and box[2]-box[0] > image_width*.5 and box[2] < image_width*.97):
            rights.append(box[2])
    return min(image_width-2,max(rights)) if rights else image_width-2


def clean_text_patch(image, box, background, foreground=None, preserve_rules=False):
    """Erase ink and its compression fringe without flattening pale artwork.

    Interpolate the background above and below each source line. Only pixels
    around contrasting ink are replaced; the rest of the original motif stays
    exact. This is deliberately limited to the OCR ink rectangle.
    """
    left, top, right, bottom = box
    patch = image.crop(box)
    ink = Image.new('L', patch.size)
    ink.putdata([255 if max(abs(a-b) for a,b in zip(rgb,background)) > 45 and (foreground is None or max(abs(a-b) for a,b in zip(rgb,foreground)) < 70) else 0
                 for rgb in patch.getdata()])
    rules=[]
    if preserve_rules:
        for row in range(ink.height):
            data=ink.crop((0,row,ink.width,row+1)).tobytes()
            if max((len(m[0]) for m in re.finditer(b'\xff+',data)),default=0) > max(20,ink.width*.75):
                rules.append(row)
    ink = ink.filter(ImageFilter.MaxFilter(5))
    for row in rules:
        ink.paste(0,(0,max(0,row-2),ink.width,min(ink.height,row+3)))
    source, mask, output = image.load(), ink.load(), patch.load()
    above, below = max(0,top-1), min(image.height-1,bottom)
    for x in range(patch.width):
        a, b = source[left+x,above], source[left+x,below]
        if max(abs(v-c) for v,c in zip(a,background)) > 24: a = background
        if max(abs(v-c) for v,c in zip(b,background)) > 24: b = background
        for y in range(patch.height):
            if mask[x,y]:
                ratio = (y+1)/(patch.height+1)
                output[x,y] = tuple(round(v*(1-ratio)+w*ratio) for v,w in zip(a,b))
    return patch


def harmonize_text_draws(draws, segments, source_sizes, labels, report=None, excluded=()):
    """Use a shared fitted size for body text with the same source typography.

    Never enlarge a fitted paragraph past its verified bounds. Exceptional
    reductions greater than twenty percent stay local instead of shrinking a page.
    """
    groups = {}
    for draw in draws:
        x,y,font,size,text,scale,colour,invisible,index = draw
        source = source_sizes.get(index)
        if invisible or source is None or index in excluded or (index not in labels and heading(segments[index])): continue
        if size < source*.8: continue
        key = ('label' if index in labels else bool(segments[index].get('table_cell')),font,source)
        groups.setdefault(key,[]).append(draw)
    common = {key:min(d[3] for d in values) for key,values in groups.items()}
    if report is not None:
        report.setdefault('typography_groups', []).extend(
            dict(role='table_labels', font_size=round(size,2), source_font_size=key[2], draws=len(groups[key]))
            for key,size in common.items() if key[0]=='label')
    result = []
    for draw in draws:
        x,y,font,size,text,scale,colour,invisible,index = draw
        key = ('label' if index in labels else bool(segments[index].get('table_cell')),font,source_sizes.get(index))
        if not invisible and index not in excluded and (index in labels or not heading(segments[index])) and key in common and size >= key[2]*.8:
            fitted = common[key]
            # Keep the top edge aligned when a baseline's font becomes smaller.
            y += ink_metrics(text,font,size)[0]-ink_metrics(text,font,fitted)[0]
            size = fitted
        result.append((x,y,font,size,text,scale,colour,invisible,index))
    return result


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
                source_sizes = page_typography(segments,page_number,sx,sy,regular_font,bold_font)
                exceptional_labels = set()
                labels = table_labels(segments, page_number)
                text_draws = []
                marker_draws = {}
                marker_pixels=[rgb for s in segments if s.get('page') == page_number and s.get('list_marker')
                               for rgb in image.crop(tuple(s['list_marker'])).getdata()]
                saturation=max((max(rgb)-min(rgb) for rgb in marker_pixels),default=0)
                coloured_markers=[rgb for rgb in marker_pixels if max(rgb)-min(rgb) >= max(20,saturation*.75)]
                marker_colour=(tuple(median(rgb[k] for rgb in coloured_markers) for k in range(3))
                               if coloured_markers else None)
                right_margin = content_right(segments,page_number,image.width)
                for index, (target, segment) in enumerate(zip(targets, segments)):
                    if segment.get('page') != page_number:
                        continue
                    box = segment.get('box')
                    if not box or len(box) != 4:
                        raise ValueError('Coordonnées PDF absentes ; réanalyser le document')
                    if segment.get('image_size') and list(image.size) != segment['image_size']:
                        raise ValueError('Dimensions OCR différentes du rendu PDF')
                    source_text = segment.get('text', '')
                    # Also repair a cached or re-exported target at the final
                    # boundary, using the original source as the only context.
                    target = correct_network_terms(source_text,target)
                    if index in labels and re.fullmatch(r'[A-Z]{2,6}', source_text.strip()):
                        if target.strip().rstrip('.') == source_text.strip():
                            target = source_text.strip()
                    is_heading = index in labels or heading(segment)
                    font = bold_font if is_heading else regular_font
                    if target == source_text:
                        if (re.search(r'[A-Za-z]{3,}', source_text)
                                and not preserved_name(source_text)
                                and DEFAULT_TERMS.get(source_text.strip()) != target.strip()
                                and not reference_label(source_text, {})):
                            report['warnings'].append({'segment': index, 'page': page_number,
                                'reason': 'Texte identique à la source : vérifier la traduction'})
                    if segment.get('preserve_artwork') or preserved_name(segment.get('text', '')):
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
                        # The marker is retained or repainted separately. Never
                        # draw punctuation invented by the model a second time.
                        target = re.sub(r'^[\s•●▪◦○°*~–—»«=−-]+', '', target)
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
                    marker = segment.get('list_marker')
                    cell = segment.get('table_cell')
                    if marker:
                        # Export the marker as a selectable Unicode glyph. Mask
                        # only its isolated gutter, preserving the nearby text.
                        a,b,c,d = marker
                        left, right = max(0,a-4), min(x0-2,c+4)
                        top, bottom = max(0,b-4), min(image.height,d+4)
                        if cell:
                            left=max(left,cell[0]+3);right=min(right,cell[2]-3)
                            top=max(top,cell[1]+3);bottom=min(bottom,cell[3]-3)
                        if left < right and top < bottom:
                            bounds=tuple(int(v) for v in (left,top,right,bottom))
                            cleaned=(Image.new('RGB',(bounds[2]-bounds[0],bounds[3]-bounds[1]),background)
                                     if cell else clean_text_patch(image,bounds,background))
                            pdf.drawImage(ImageReader(cleaned),left*sx,height-bottom*sy,
                                          width=(right-left)*sx,height=(bottom-top)*sy)
                            cleaned.close()
                            patch_pixels=list(image.crop(tuple(int(v) for v in marker)).getdata())
                            ink=[rgb for rgb in patch_pixels
                                 if max(abs(v-w) for v,w in zip(rgb,background)) > 45]
                            coloured=[rgb for rgb in ink if max(rgb)-min(rgb)>20]
                            colour=(tuple(median(rgb[k] for rgb in coloured or ink) for k in range(3))
                                    if ink else foreground)
                            if marker_colour and any(max(rgb)-min(rgb)>10 for rgb in patch_pixels):
                                colour=marker_colour
                            # Solid squares and round dots retain distinct glyphs.
                            occupancy=len(ink)/max(1,len(patch_pixels))
                            glyph=segment.get('list_marker_text') or ('▪' if occupancy > .85 else '•')
                            marker_font=regular_font
                            ascent,descent=ink_metrics(glyph,marker_font,1)
                            marker_height=min(d-b,c-a)*sy
                            size=marker_height/max(.1,ascent+descent)
                            advance=pdfmetrics.stringWidth(glyph,marker_font,size)
                            baseline=height-(b+d)/2*sy+(descent-ascent)*size/2
                            marker_draws[index]=((a+c)/2*sx-advance/2,baseline,marker_font,size,
                                                 glyph,1,colour,False,index)
                    if target == source_text and index not in labels and (segment.get('native_text') or reference_label(source_text, {})):
                        # Keep unchanged reference artwork exact while making it
                        # searchable. Painting a contact line can destroy a nearby
                        # postal line when their OCR rectangles overlap.
                        for line in segment.get('lines') or [segment]:
                            a,b,c,d = line['box']
                            size = estimated_source_size(line,sx,sy,font)
                            text_draws.append((a*sx,height-d*sy,font,size,line['text'],1,foreground,True,index))
                        continue
                    # A short label may use blank space inside its cell. Stop at
                    # a neighbouring text box or any visible border/illustration.
                    limit = max(x1, right_margin)
                    # In a ruled table, adjacent rows already define spacing;
                    # probing their ink would wrongly block cell whitespace.
                    clearance = 2 if segment.get('table_cell') else max(6, round(6/sy))
                    band_top, band_bottom = max(0,y0-clearance), min(image.height,y1+clearance)
                    for neighbour in segments:
                        other = neighbour.get('box')
                        if neighbour.get('page') == page_number and other and other[0] > x1 and other[1] < band_bottom and other[3] > band_top:
                            limit = min(limit, int(other[0])-clearance)
                    pixels = image.load()
                    end = x1
                    for column in range(x1+3, limit):
                        contrasting = sum(max(abs(a-b) for a,b in zip(pixels[column, row], background)) > 30
                                          for row in range(band_top, band_bottom))
                        if contrasting > max(2,(band_bottom-band_top)*.1):
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
                        # New text keeps a physical margin even when source ink
                        # or OCR boxes nearly touch the cell's right border.
                        available_width = min(available_width,(cell[2]-x0)*sx-3)
                    source_lines = segment.get('lines', [])
                    if cell and not source_lines: source_lines=[segment]
                    source_size = source_sizes.get(index, estimated_source_size(segment,sx,sy,font))
                    minimum_size = min(5, max(3.5, source_size*.9))
                    if source_lines:
                        # Use only whitespace verified across the entire block
                        # and its clearance band, never space across artwork.
                        size = source_sizes.get(index, estimated_source_size(segment, sx, sy, font))
                        # French prose can need an extra line. Use blank space
                        # below the source block before reducing the whole font.
                        bottom = min(image.height-clearance, y1+round(size*1.18/sy))
                        if cell: bottom = min(bottom,cell[3]-5)
                        corridor_right = min(image.width,round(x0+available_width/sx))
                        for neighbour in segments:
                            other = neighbour.get('box')
                            if (neighbour is not segment and neighbour.get('page') == page_number
                                    and other and other[1] >= y1
                                    and other[0] < corridor_right and other[2] > x0):
                                bottom = min(bottom,other[1]-clearance)
                        extended = y1
                        for row in range(y1+3,max(y1+3,int(bottom))):
                            contrasting = sum(max(abs(a-b) for a,b in zip(pixels[column,row],background)) > 30
                                              for column in range(x0,corridor_right))
                            if contrasting > max(2,(corridor_right-x0)*.01): break
                            extended = row-2
                        available_height = max(available_height,(extended-y0)*sy)
                        if cell and segment.get('native_text'):
                            available_height=min(available_height,(cell[3]-y0)*sy-2)
                        def wrap(text, font_size, horizontal_scale=1):
                            output, current = [], ''
                            for word in text.split():
                                candidate = (current + ' ' + word).strip()
                                if current and pdfmetrics.stringWidth(candidate, font, font_size)*horizontal_scale > available_width:
                                    output.append(current); current = word
                                else:
                                    current = candidate
                            if current: output.append(current)
                            return output
                        while size >= minimum_size:
                            leading = size*1.18
                            fits = False
                            for horizontal_scale in (1, .95):
                                wrapped = wrap(target, size, horizontal_scale)
                                ascent = max(ink_metrics(line,font,size)[0] for line in wrapped)
                                descent = max(ink_metrics(line,font,size)[1] for line in wrapped)
                                if ((len(wrapped)-1)*leading + ascent+descent <= available_height
                                    and all(pdfmetrics.stringWidth(line, font, size)*horizontal_scale <= available_width for line in wrapped)):
                                    fits = True
                                    break
                            if fits:
                                break
                            size -= .25
                        if (size < minimum_size and cell and index in labels and segment.get('native_text')
                                and sum(other.get('page')==page_number and other.get('table_cell')==cell
                                        for other in segments)==1):
                            # A centered one-line source can need two French lines.
                            # Reflow only within a verified uniform cell; never over artwork.
                            uniform = all(
                                mask[0] <= col < mask[2] and mask[1] <= row < mask[3]
                                or max(abs(a-b) for a,b in zip(pixels[col,row],background)) <= 30
                                for row in range(int(cell[1])+4,int(cell[3])-4)
                                for col in range(int(cell[0])+4,int(cell[2])-4))
                            if uniform:
                                available_height=(cell[3]-cell[1])*sy-2
                                size=source_size
                                while size >= minimum_size:
                                    leading=size*1.18
                                    fits=False
                                    for horizontal_scale in (1,.95):
                                        wrapped=wrap(target,size,horizontal_scale)
                                        ascent=max(ink_metrics(line,font,size)[0] for line in wrapped)
                                        descent=max(ink_metrics(line,font,size)[1] for line in wrapped)
                                        occupied=(len(wrapped)-1)*leading+ascent+descent
                                        if occupied <= available_height and all(
                                                pdfmetrics.stringWidth(line,font,size)*horizontal_scale <= available_width
                                                for line in wrapped):
                                            fits=True
                                            break
                                    if fits:
                                        y0=cell[1]+((cell[3]-cell[1])*sy-occupied)/2/sy
                                        exceptional_labels.add(index)
                                        report.setdefault('reflowed_cells',[]).append(
                                            dict(segment=index,page=page_number,font_size=round(size,2)))
                                        break
                                    size-=.25
                        if size < minimum_size:
                            report['warnings'].append({'segment': index, 'page': page_number,
                                'reason': 'Paragraphe trop long : zone originale conservée'})
                            continue
                        if size < 7:
                            report['warnings'].append({'segment': index, 'page': page_number,
                                'reason': 'Police réduite : lisibilité à vérifier', 'font_size': round(size, 2)})
                        if horizontal_scale < 1:
                            report['warnings'].append({'segment': index, 'page': page_number,
                                'reason': 'Texte légèrement condensé pour conserver la taille de police',
                                'horizontal_scale': horizontal_scale})
                        pdf.setFillColorRGB(*(value/255 for value in background))
                        for line in source_lines:
                            a,b,c,d = line['box']
                            bounds = (max(0,int(a)-3),max(0,int(b)-3),
                                      min(image.width,int(c)+3),min(image.height,int(d)+3))
                            # Native cell bounds are verified from PDF vectors.
                            # Fill only inside the border: selective ink detection
                            # can leave pale letters or mistake a short word for a rule.
                            if cell and segment.get('native_text'):
                                bounds=(max(bounds[0],int(cell[0])+3),max(bounds[1],int(cell[1])+3),
                                        min(bounds[2],int(cell[2])-3),min(bounds[3],int(cell[3])-3))
                                cleaned=Image.new('RGB',(bounds[2]-bounds[0],bounds[3]-bounds[1]),background)
                            else:
                                cleaned = clean_text_patch(image,bounds,background,preserve_rules=bool(segment.get('native_text')))
                            pdf.drawImage(ImageReader(cleaned),bounds[0]*sx,height-bounds[3]*sy,
                                          width=(bounds[2]-bounds[0])*sx,height=(bounds[3]-bounds[1])*sy)
                            cleaned.close()
                        baseline = height-y0*sy-ascent
                        for line in wrapped:
                            text_draws.append((x,baseline,font,size,line,horizontal_scale,foreground,False,index))
                            baseline -= leading
                        continue
                    size = source_sizes.get(index, estimated_source_size(segment, sx, sy, font))
                    ink_ascent, ink_descent = ink_metrics(target,font,size)
                    # The masking box includes two pixels of antialiasing on
                    # either side. Accented translations can use that same area.
                    if ink_ascent+ink_descent > available_height+4*sy:
                        size *= (available_height+4*sy)/(ink_ascent+ink_descent)
                    measured = pdfmetrics.stringWidth(target, font, size)
                    if measured > available_width:
                        size *= available_width / measured
                    if size < minimum_size:
                        report['warnings'].append({'segment': index, 'page': page_number,
                            'reason': 'Traduction trop longue : zone originale conservée'})
                        continue
                    if size < 7 or size < available_height*.65:
                        report['warnings'].append({'segment': index, 'page': page_number,
                            'reason': 'Police réduite : lisibilité à vérifier', 'font_size': round(size, 2)})
                    pdf.setFillColorRGB(*(value/255 for value in background))
                    cleaned = clean_text_patch(image,mask,background,preserve_rules=bool(segment.get('native_text')))
                    pdf.drawImage(ImageReader(cleaned),mask[0]*sx,height-mask[3]*sy,
                                  width=(mask[2]-mask[0])*sx,height=(mask[3]-mask[1])*sy)
                    cleaned.close()
                    ascent, descent = ink_metrics(target,font,size)
                    baseline = y + (available_height-(ascent+descent))/2+descent
                    if cell and ascent+descent+6 <= (cell[3]-cell[1])*sy:
                        baseline = max(height-cell[3]*sy+3+descent,
                                       min(baseline,height-cell[1]*sy-3-ascent))
                    text_draws.append((x,baseline,font,size,target,1,foreground,False,index))
                # Every source mask must precede every translated glyph. OCR
                # boxes can overlap; later masks must not clip earlier text.
                text_draws = harmonize_text_draws(text_draws, segments, source_sizes, labels, report, exceptional_labels)
                ordered_draws=[]
                for draw in text_draws:
                    marker_draw=marker_draws.pop(draw[-1],None)
                    if marker_draw: ordered_draws.append(marker_draw)
                    ordered_draws.append(draw)
                ordered_draws.extend(marker_draws.values())
                for x,y,font,size,text,scale,colour,invisible,index in ordered_draws:
                    pdf.saveState()
                    pdf.setFillColorRGB(*(value/255 for value in colour))
                    obj = pdf.beginText(x,y)
                    obj.setFont(font,size)
                    obj.setHorizScale(scale*100)
                    obj.setTextRenderMode(3 if invisible else 0)
                    obj.textOut(text)
                    pdf.drawText(obj)
                    pdf.restoreState()
                pdf.showPage()
                image.close()
        pdf.save()
        pending.replace(destination)
        destination.with_name('layout-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        pending.unlink(missing_ok=True)
    return report


