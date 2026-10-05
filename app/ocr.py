"""Offline OCR, with coordinates and confidence. Tesseract is the tested
CPU fallback; Paddle is opt-in and requires explicitly installed model dirs.
"""
import csv
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def recognize(image):
    backend = os.environ.get("OCR_BACKEND", "tesseract")
    if backend == "paddle": return paddle(image)
    if backend != "tesseract": raise ValueError("Moteur OCR inconnu")
    if not shutil.which("tesseract"): raise ValueError("Tesseract local absent")
    result = subprocess.run(["tesseract",str(image),"stdout","-l","eng","--psm","3","tsv"],capture_output=True,text=True,timeout=120,check=True)
    lines = {}
    for row in csv.DictReader(result.stdout.splitlines(),delimiter='\t'):
        if not row.get('text','').strip() or float(row['conf']) < 0: continue
        key = (row['block_num'],row['par_num'],row['line_num'])
        left,top,width,height = [int(row[n]) for n in ('left','top','width','height')]
        box = [left,top,left+width,top+height]
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
            subprocess.run(['pdftoppm','-f',str(page),'-l',str(page),'-singlefile','-scale-to','2500','-png',str(path),str(prefix)],capture_output=True,timeout=120,check=True)
            for line in recognize(prefix.with_suffix('.png')):
                line['page']=page;all_lines.append(line)
    return all_lines
