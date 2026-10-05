"""Offline OCR, with coordinates and confidence. Tesseract is the tested
CPU fallback; Paddle is opt-in and requires explicitly installed model dirs.
"""
import csv
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
    edge_pixels = edges.load()
    line_rules = {}
    lines = {}
    for row in csv.DictReader(result.stdout.splitlines(),delimiter='\t'):
        if not row.get('text','').strip() or float(row['conf']) < 0: continue
        key = (row['block_num'],row['par_num'],row['line_num'])
        left,top,width,height = [int(row[n]) for n in ('left','top','width','height')]
        if key not in line_rules:
            middle = top+height//2
            start, end = max(0,middle-35), min(edges.height,middle+35)
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
        if key not in lines: lines[key] = {"text":row['text'],"box":box,"confidence":float(row['conf'])/100}
        else:
            line = lines[key];line['text'] += ' '+row['text'];line['confidence']=min(line['confidence'],float(row['conf'])/100)
            line['box']=[min(line['box'][0],box[0]),min(line['box'][1],box[1]),max(line['box'][2],box[2]),max(line['box'][3],box[3])]
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
