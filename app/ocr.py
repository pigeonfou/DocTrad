"""Offline OCR, with coordinates and confidence. Tesseract is the tested
CPU fallback; Paddle is opt-in and requires explicitly installed model dirs.
"""
import csv
import bisect
import re
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def vertical_rules(image, with_edges=False):
    from PIL import Image, ImageChops
    with Image.open(image) as source:
        grey = source.convert('L')
    edges = ImageChops.difference(grey, ImageChops.offset(grey, 1, 0))
    edges = edges.point(lambda value: 255 if value >= 35 else 0)
    columns = [x for x in range(1, edges.width)
               if edges.crop((x, 0, x+1, edges.height)).histogram()[255] > edges.height*.25]
    # JPEG/antialiasing produces several adjacent edge columns for one rule.
    groups = []
    for x in columns:
        if groups and x-groups[-1][-1] <= 4:
            groups[-1].append(x)
        else:
            groups.append([x])
    rules = [round(sum(group)/len(group)) for group in groups]
    return (rules, edges) if with_edges else rules


def recognize(image):
    backend = os.environ.get("OCR_BACKEND", "tesseract")
    if backend == "paddle": return paddle(image)
    if backend != "tesseract": raise ValueError("Moteur OCR inconnu")
    if not shutil.which("tesseract"): raise ValueError("Tesseract local absent")
    result = subprocess.run(["tesseract",str(image),"stdout","-l","eng","--psm","3","tsv"],capture_output=True,text=True,timeout=120,check=True)
    rules, edges = vertical_rules(image, with_edges=True)
    # Long, nearly continuous strokes distinguish row borders from text ink.
    from PIL import Image, ImageChops
    with Image.open(image) as source:
        grey = source.convert('L')
    horizontal_edges = ImageChops.difference(grey, ImageChops.offset(grey, 0, 1)).point(lambda value: 255 if value >= 35 else 0)
    border_rows = []
    for y in range(1, horizontal_edges.height):
        pixels = horizontal_edges.crop((0, y, horizontal_edges.width, y+1)).tobytes()
        if (pixels.count(255) > horizontal_edges.width*.5
                and max((len(m[0]) for m in re.finditer(rb'\xff(?:\x00{0,3}\xff)*', pixels)), default=0) > horizontal_edges.width*.6):
            if border_rows and y-border_rows[-1][-1] <= 4:
                border_rows[-1].append(y)
            else:
                border_rows.append([y])
    horizontal_rules = [round(sum(group)/len(group)) for group in border_rows]
    edge_pixels = edges.load()
    line_rules = {}
    lines = {}
    rows = list(csv.DictReader(result.stdout.splitlines(), delimiter='\t'))
    # Known document headings sometimes begin with a drawing recognized as
    # punctuation. Keep its artwork outside the heading's text/ink rectangle.
    from app.terminology import DEFAULT_TERMS
    heading_groups = {}
    grouped_words = {}
    for row in rows:
        if row.get('text', '').strip() and float(row['conf']) >= 0:
            key = (row['block_num'], row['par_num'], row['line_num'])
            grouped_words.setdefault(key, []).append(row)
    for key, words in grouped_words.items():
        real_words = [word for word in words if any(c.isalnum() for c in word['text'])]
        prose = ' '.join(word['text'] for word in real_words)
        if real_words and any(prose == name or prose.startswith(name + ' ') for name in DEFAULT_TERMS):
            heading_groups[key] = int(real_words[0]['left'])
    for row in rows:
        if not row.get('text','').strip() or float(row['conf']) < 0: continue
        key = (row['block_num'],row['par_num'],row['line_num'])
        if (key in heading_groups and float(row['conf']) < 20
                and int(row['left']) < heading_groups[key]
                and not any(c.isalnum() for c in row['text'])
                and row['text'] not in ('•', '●', '▪', '*', '–', '—', '»', '«', '-')):
            continue
        left,top,width,height = [int(row[n]) for n in ('left','top','width','height')]
        if key not in line_rules:
            start, end = max(0,top-3), min(edges.height,top+height+3)
            # A column boundary must actually extend through this text line.
            # A global x coordinate must never cut footnotes below the table.
            line_rules[key] = [rule for rule in rules if
                sum(any(edge_pixels[x,y] == 255 for x in range(max(0,rule-2), min(edges.width,rule+3)))
                    for y in range(start,end)) >= (end-start)*.8]
        active_rules = line_rules[key]
        box = [left,top,left+width,top+height]
        if (row['text'] == '|' or width < height/3) and any(abs(rule-(left+width/2)) < max(5,width/2) for rule in active_rules):
            # A table border is sometimes recognized as the character '|'.
            continue
        # A large horizontal gap usually separates table cells. Do not translate
        # both columns as one sentence or paint across the intervening border.
        part = 0
        while (*key, part) in lines:
            previous = lines[(*key, part)]
            crosses_rule = any(previous['box'][2] <= rule <= left for rule in active_rules)
            if not crosses_rule and left - previous['box'][2] <= max(height, previous['box'][3]-previous['box'][1])*2.5:
                break
            part += 1
        key = (*key, part)
        # An uncertain bullet must not make all the words in its line unusable.
        confidence = float(row['conf'])/100 if any(c.isalnum() for c in row['text']) else 1.0
        if key not in lines: lines[key] = {"text":row['text'],"box":box,"confidence":confidence,"ocr_group":list(key[:2]),"cell_part":part,"confidence_weight":max(1,len(row["text"])),"minimum_confidence":confidence}
        else:
            line = lines[key]
            weight = max(1, len(row['text']))
            old_weight = line['confidence_weight']
            line['confidence'] = (line['confidence']*old_weight + confidence*weight)/(old_weight+weight)
            line['confidence_weight'] += weight
            line['minimum_confidence'] = min(line['minimum_confidence'], confidence)
            line['text'] += ' '+row['text']
            line['box']=[min(line['box'][0],box[0]),min(line['box'][1],box[1]),max(line['box'][2],box[2]),max(line['box'][3],box[3])]
        # Stable physical cells, unlike Tesseract's per-line "part" counter.
        line = lines[key]
        a,b,c,d = line['box']
        column = bisect.bisect_right(active_rules, (a+c)/2)
        above = [y for y in horizontal_rules if y < b]
        below = [y for y in horizontal_rules if y > d]
        if 0 < column < len(active_rules) and above and below:
            line['table_cell'] = [active_rules[column-1], above[-1], active_rules[column], below[0]]
    return list(lines.values())


def paddle(image):
    detection = Path(os.environ.get('PADDLE_DET_ROOT','/opt/docutranslate/models/paddleocr/detection'))
    recognition = Path(os.environ.get('PADDLE_REC_ROOT','/opt/docutranslate/models/paddleocr/recognition'))
    for path in (detection,recognition):
        if not (path/'inference.json').is_file(): raise ValueError('Poids PaddleOCR locaux absents')
    os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK']='True'
    from paddleocr import PaddleOCR
    engine=PaddleOCR(text_detection_model_dir=str(detection),text_recognition_model_dir=str(recognition),use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False,device='cpu')
    lines=[]
    for result in engine.predict(str(image)):
        for text,score,box in zip(result['rec_texts'],result['rec_scores'],result['rec_boxes']):
            lines.append(dict(text=text,confidence=float(score),box=[int(n) for n in box]))
    return lines


def scan_pdf(path):
    if not shutil.which('pdftoppm'):raise ValueError('Poppler local absent')
    # Per-page conversion bounds disk use; never render all pages concurrently.
    from pypdf import PdfReader
    page_count=len(PdfReader(path).pages)
    if page_count>500:raise ValueError('PDF limité à 500 pages')
    all_lines=[]
    with tempfile.TemporaryDirectory(prefix='doctrad-ocr-') as temp:
        for page in range(1,page_count+1):
            prefix=Path(temp)/'page'
            subprocess.run(['pdftoppm','-f',str(page),'-l',str(page),'-singlefile','-cropbox','-scale-to','2500','-png',str(path),str(prefix)],capture_output=True,timeout=120,check=True)
            from PIL import Image
            with Image.open(prefix.with_suffix('.png')) as image:
                image_size=list(image.size)
            for line in recognize(prefix.with_suffix('.png')):
                line['page']=page;line['image_size']=image_size;all_lines.append(line)
    return all_lines



def paragraphs(lines):
    """Join aligned consecutive lines in the same detected paragraph/cell.

    Keep individual ink boxes for masking; never paint a large rectangle over
    artwork between lines. Backends without paragraph IDs stay line-based.
    """
    import re
    result = []
    # Read one physical cell at a time, including interleaved left/right lines.
    def reading_order(item):
        index, line = item
        box = line.get('box') or [0, index]
        cell = line.get('table_cell')
        return (line.get('page') or 0, cell[1] if cell else box[1],
                cell[0] if cell else 0, box[1], index)
    ordered = sorted(enumerate(lines), key=reading_order)
    for _, line in ordered:
        previous = result[-1] if result else None
        box = line.get('box')
        merge = False
        if previous and box and line.get('ocr_group') is not None:
            last = previous.get('lines', [previous])[-1]
            old = last['box']
            h, old_h = box[3]-box[1], old[3]-old[1]
            same_cell = line.get('table_cell') is not None and line.get('table_cell') == previous.get('table_cell')
            same_paragraph = (line['ocr_group'] == previous.get('ocr_group')
                              and line.get('cell_part') == previous.get('cell_part'))
            merge = (line.get('page') == previous.get('page')
                     and (same_cell or (not line.get('table_cell') and not previous.get('table_cell') and same_paragraph))
                     and abs(box[0]-old[0]) <= max(h, old_h)
                     and 0 <= box[1]-old[3] <= max(h, old_h)*1.2
                     and min(h, old_h)/max(h, old_h) >= .7
                     and not re.match(r'^[•●▪*–—»«-]\s*|^\d+[.)]\s', line['text'])
                     and not last['text'].rstrip().endswith(':')
                     and not re.match(r'^[A-Z][^:]{0,65}:', line['text']))
        if merge:
            if 'lines' not in previous:
                previous['lines'] = [dict(previous)]
            previous['lines'].append(dict(line))
            old_weight = max(1, len(previous['text']))
            weight = max(1, len(line['text']))
            previous['confidence'] = (previous['confidence']*old_weight + line['confidence']*weight)/(old_weight+weight)
            previous['minimum_confidence'] = min(previous.get('minimum_confidence', 1), line.get('minimum_confidence', line['confidence']))
            previous['text'] += ' ' + line['text']
            previous['box'] = [min(previous['box'][0], box[0]), previous['box'][1],
                               max(previous['box'][2], box[2]), box[3]]
        else:
            result.append(dict(line))
    return result

