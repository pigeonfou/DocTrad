"""Local OpenDataLoader PDF analysis, normalized to DocTrad's layout contract."""
import json
import math
import os
import ipaddress
from urllib.parse import urlsplit
import subprocess
import sys
import tempfile
from pathlib import Path
from pypdf import PdfReader

VERSION = '2.5.13'


def pixel_box(box, page, image_size):
    if not isinstance(box, list) or len(box) != 4 or not all(isinstance(v, (int,float)) and math.isfinite(v) for v in box):
        raise ValueError('Coordonnées OpenDataLoader invalides')
    left, bottom, right, top = map(float, box)
    if left >= right or bottom >= top: raise ValueError('Rectangle OpenDataLoader vide')
    crop = page.cropbox; width, height = float(crop.width), float(crop.height)
    rotation = int(page.get('/Rotate', 0)) % 360
    corners=[]
    for x,y in [(left,bottom),(left,top),(right,bottom),(right,top)]:
        x-=float(crop.left);y=float(crop.top)-y
        if rotation == 90: x,y=height-y,x
        elif rotation == 180: x,y=width-x,height-y
        elif rotation == 270: x,y=y,width-x
        corners.append((x,y))
    if rotation in (90,270):width,height=height,width
    xs=[v[0]*image_size[0]/width for v in corners];ys=[v[1]*image_size[1]/height for v in corners]
    result=[max(0,math.floor(min(xs))),max(0,math.floor(min(ys))),min(image_size[0],math.ceil(max(xs))),min(image_size[1],math.ceil(max(ys)))]
    if result[0]>=result[2] or result[1]>=result[3]:raise ValueError('Rectangle OpenDataLoader hors page')
    return result


def normalize(document, pages, image_sizes):
    output=[];section={};table_fallback=set()
    def visit(node, cell=None, row_label=None):
        kind=node.get('type');number=node.get('page number')
        if kind=='heading' and '\n' in node.get('content',''):
            lines=node['content'].splitlines();left,bottom,right,top=node['bounding box']
            step=(top-bottom)/len(lines)
            for index,line in enumerate(lines):
                visit(dict(node,content=line,**{'bounding box':[left,top-(index+1)*step,right,top-index*step]}),cell,row_label)
            return
        if kind=='table':
            # ODL local 2.5.13 can merge all physical rows into two giant cells.
            # Do not translate their concatenation as one table value.
            rows=node.get('rows',[])
            if len(rows)<=2 and any(len(k.get('content','').splitlines())>5 for row in rows for c in row.get('cells',[]) for k in c.get('kids',[])):
                table_fallback.add(number)
            for row in rows:
                cells=row.get('cells',[])
                label=' '.join(k.get('content','') for k in cells[0].get('kids',[])) if cells else ''
                for c in cells:visit(c,c,label)
            return
        if kind=='heading':section[number]=node.get('content','').replace('\n',' ')[:250]
        if kind=='image':return
        children=node.get('kids',[]) or node.get('list items',[])
        if children:
            for child in children:visit(child,cell,row_label)
            return
        text=node.get('content','').strip()
        if not text:return
        if not isinstance(number,int) or not 1<=number<=len(pages):raise ValueError('Page OpenDataLoader invalide')
        page=pages[number-1];size=image_sizes[number-1];box=pixel_box(node['bounding box'],page,size)
        # Retain paragraph boundaries supplied by ODL, remove visual wrapping.
        text=text.replace('-\n','').replace('\n',' ')
        item={'text':text,'box':box,'page':number,'image_size':size,'confidence':1.0,
              'minimum_confidence':1.0,'native_text':True,'native_block_order':len(output),
              'source_bold':kind=='heading' or any(v in node.get('font','') for v in ('Bold','SemiBold','Demi')),
              'analysis_backend':'opendataloader','semantic_type':kind,'structure_id':node.get('id'),
              'document_context':{'role':'table_cell' if cell else 'text','section':section.get(number,'')}}
        font=node.get('font size')
        if isinstance(font,(int,float)) and 0<font<=200:item['source_font_size']=font
        if cell:
            item['table_cell']=pixel_box(cell['bounding box'],page,size)
            item['document_context']['row']=(row_label or '')[:500]
        item['lines']=[{'text':text,'box':box,'source_font_size':font,'native_text':True}] if isinstance(font,(int,float)) else [{'text':text,'box':box,'native_text':True}]
        output.append(item)
    for node in document.get('kids',[]):visit(node)
    return output,table_fallback


def analyze_pdf(path):
    path=Path(path).resolve();reader=PdfReader(path)
    if reader.is_encrypted:raise ValueError('PDF chiffré non supporté')
    if len(reader.pages)>500:raise ValueError('PDF limité à 500 pages')
    with tempfile.TemporaryDirectory(prefix='doctrad-odl-') as directory:
        # Child process bounds Java execution and keeps PDF text out of errors.
        hybrid_url=os.environ.get('DOCTRAD_ODL_HYBRID_URL','')
        if hybrid_url:
            address=urlsplit(hybrid_url)
            local=address.hostname=='localhost'
            try:local=local or ipaddress.ip_address(address.hostname or '').is_loopback
            except ValueError:pass
            if not local or address.scheme not in ('http','https') or address.username or address.password:
                raise ValueError('Le backend hybride OpenDataLoader doit être local (loopback).')
        program=("import opendataloader_pdf,sys; opendataloader_pdf.convert(sys.argv[1],output_dir=sys.argv[2],"
                 "format='json',quiet=True,keep_line_breaks=True,include_header_footer=True,image_output='off',sanitize=False,**({'hybrid':'docling-fast','hybrid_mode':'full','hybrid_url':sys.argv[3]} if sys.argv[3] else {}))")
        try:subprocess.run([sys.executable,'-c',program,str(path),directory,hybrid_url],capture_output=True,check=True,timeout=180)
        except (subprocess.SubprocessError,OSError):raise ValueError('Analyse OpenDataLoader indisponible : vérifier le paquet local et Java 11+.') from None
        result=Path(directory)/(path.stem+'.json')
        if not result.is_file() or result.stat().st_size>64*1024*1024:raise ValueError('Sortie OpenDataLoader absente ou trop volumineuse')
        document=json.loads(result.read_text())
        from PIL import Image
        sizes=[]
        for index in range(len(reader.pages)):
            prefix=Path(directory)/'page'
            subprocess.run(['pdftoppm','-f',str(index+1),'-l',str(index+1),'-singlefile','-cropbox','-scale-to','2500','-png',str(path),str(prefix)],capture_output=True,check=True,timeout=120)
            with Image.open(prefix.with_suffix('.png')) as image:sizes.append(list(image.size))
        items,bad_tables=normalize(document,reader.pages,sizes)
        # Use the original coordinate-aware analyzer only for unsupported pages
        # and incorrectly merged tables; ODL errors never silently fall back.
        from .ocr import paragraphs,recognize
        from .pdf_native import extract_page
        for index,page in enumerate(reader.pages,1):
            current=[x for x in items if x['page']==index]
            sparse=sum(len(x['text'].split()) for x in current)<30 and bool(page.images)
            if index not in bad_tables and current and not sparse:continue
            if index in bad_tables:
                native=extract_page(path,index,page,sizes[index-1])
                replacement=paragraphs([dict(x,page=index,image_size=sizes[index-1]) for x in native])
                replacement=[dict(x,analysis_backend='native_table_fallback') for x in replacement if x.get('table_cell')]
                if replacement:
                    items=[x for x in items if x['page']!=index or not x.get('table_cell')]+replacement
                    continue
            if not current or sparse:
                prefix=Path(directory)/'ocr'
                subprocess.run(['pdftoppm','-f',str(index),'-l',str(index),'-singlefile','-cropbox','-scale-to','2500','-png',str(path),str(prefix)],capture_output=True,check=True,timeout=120)
                lines=[dict(x,page=index,image_size=sizes[index-1]) for x in recognize(prefix.with_suffix('.png'))]
                items=[x for x in items if x['page']!=index]+[dict(x,analysis_backend='tesseract_fallback') for x in paragraphs(lines)]
        return sorted(items,key=lambda x:x['page'])
