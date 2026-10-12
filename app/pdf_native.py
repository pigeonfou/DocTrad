"""Coordinate-preserving Poppler text extraction, without a new dependency."""
import math
import re
import subprocess
import xml.etree.ElementTree as ET


def vector_cells(page):
    """Find paired rectangular cells, including lightly ruled tables."""
    rectangles=[]
    height=float(page.cropbox.height)
    if int(page.get('/Rotate',0)) % 360: return []
    def visit(op,args,cm,tm):
        if op != b're' or abs(cm[1])+abs(cm[2]) > .001: return
        x,y,w,h=map(float,args)
        x0,x1=sorted((x*cm[0]+cm[4],(x+w)*cm[0]+cm[4]))
        y0,y1=sorted((y*cm[3]+cm[5],(y+h)*cm[3]+cm[5]))
        x0-=float(page.cropbox.left);x1-=float(page.cropbox.left)
        y0-=float(page.cropbox.bottom);y1-=float(page.cropbox.bottom)
        if 20 <= x1-x0 <= float(page.cropbox.width)*.7 and 5 <= y1-y0 <= height*.3:
            rectangles.append([x0,height-y1,x1,height-y0])
    page.extract_text(visitor_operand_before=visit)
    unique=list({tuple(round(v,2) for v in r):r for r in rectangles}.values())
    selected=[r for r in unique if any(other is not r and
            abs(other[1]-r[1]) < .5 and abs(other[3]-r[3]) < .5 and
            (abs(other[0]-r[2]) < .5 or abs(other[2]-r[0]) < .5) for other in unique)]
    headers=[r for r in unique if r not in selected and
             any(abs(c[1]-r[3]) < .5 and abs(c[0]-r[0]) < .5 for c in selected) and
             any(abs(c[1]-r[3]) < .5 and abs(c[2]-r[2]) < .5 for c in selected)]
    return selected+headers


def extract_page(path,page_number,page,image_size):
    if not (page.extract_text() or '').strip(): return []
    result=subprocess.run(['pdftotext','-f',str(page_number),'-l',str(page_number),
                           '-cropbox','-bbox-layout',str(path),'-'],capture_output=True,check=True,timeout=120)
    root=ET.fromstring(result.stdout)
    ns={'p':'http://www.w3.org/1999/xhtml'}
    node=root.find('.//p:page',ns)
    if node is None: return []
    width,height=float(node.get('width')),float(node.get('height'))
    sx,sy=image_size[0]/width,image_size[1]/height
    cells=vector_cells(page)
    spans=[]
    def text_span(text,cm,tm,font,size):
        if text.strip():
            spans.append((text.strip(),float(size)*math.hypot(cm[0]*tm[0]+cm[2]*tm[1],cm[1]*tm[0]+cm[3]*tm[1]),
                          bool(abs(cm[1])+abs(cm[2])+abs(tm[1])+abs(tm[2]) > .01),
                          bool(font and any(part in str(font.get('/BaseFont','')) for part in ('Bold','Demi')))))
    page.extract_text(visitor_text=text_span)
    def bounds(element): return [float(element.get(k)) for k in ('xMin','yMin','xMax','yMax')]
    def pixels(box):return [max(0,math.floor(box[0]*sx)),max(0,math.floor(box[1]*sy)),
                            min(image_size[0],math.ceil(box[2]*sx)),min(image_size[1],math.ceil(box[3]*sy))]
    lines=[]
    for block_index,block in enumerate(node.findall('.//p:block',ns)):
        for row in block.findall('p:line',ns):
            groups={}
            for word in row.findall('p:word',ns):
                text=''.join(word.itertext()).strip()
                if not text: continue
                box=bounds(word);x,y=(box[0]+box[2])/2,(box[1]+box[3])/2
                cell=next((i for i,c in enumerate(cells) if c[0] <= x <= c[2] and c[1] <= y <= c[3]),None)
                groups.setdefault(cell,[]).append(dict(text=text,box=pixels(box)))
            for cell,words in groups.items():
                boxes=[w['box'] for w in words]
                line=dict(text=' '.join(w['text'] for w in words),words=words,confidence=1,
                          minimum_confidence=1,native_text=True,native_block_order=block_index,
                          ocr_group=['native',block_index],cell_part=cell,
                          box=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)])
                normalized=lambda text: ''.join(text.split()).casefold()
                candidates=[span for span in spans if normalized(line['text']) in normalized(span[0])]
                if candidates:
                    chosen=min(candidates,key=lambda span:len(span[0]))
                    if 3 <= chosen[1] <= 48: line['source_font_size']=chosen[1]
                    line['source_bold']=chosen[3]
                    if chosen[2]: line['preserve_artwork']=True
                if cell is not None: line['table_cell']=pixels(cells[cell])
                line['text']=re.sub(r'\bin\s+([23])\b',lambda m:'in'+{'2':'²','3':'³'}[m[1]],line['text'])
                lines.append(line)
    return lines
