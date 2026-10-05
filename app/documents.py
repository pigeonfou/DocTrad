"""Safe native DOCX/PPTX reconstruction and reflowed PDF exports.
Scanned input uses local OCR; originals are always retained.
"""
from pathlib import Path
import zipfile
from io import BytesIO
from html import escape

SUPPORTED = {".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}

def validate(path, suffix):
    if suffix not in SUPPORTED: raise ValueError("Format non supporté")
    with open(path, "rb") as f: head = f.read(16)
    if suffix == ".pdf":
        if not head.startswith(b"%PDF-"): raise ValueError("Signature PDF invalide")
    elif suffix in {".docx", ".pptx"}:
        with zipfile.ZipFile(path) as z:
            info = z.infolist()
            if len(info) > 10000 or sum(i.file_size for i in info) > 512 * 1024 * 1024: raise ValueError("Archive trop volumineuse")
            for i in info:
                if i.file_size > 64 * 1024 * 1024 or (i.file_size > 1024 * 1024 and i.file_size / max(i.compress_size, 1) > 200): raise ValueError("Archive compressée dangereuse")
                if ".." in Path(i.filename).parts or i.filename.startswith("/"): raise ValueError("Chemin d'archive dangereux")
                if "vbaproject" in i.filename.lower() or "activex" in i.filename.lower(): raise ValueError("Macros ou contenu actif refusé")
            required = "word/document.xml" if suffix == ".docx" else "ppt/presentation.xml"
            if required not in z.namelist(): raise ValueError("Structure Office invalide")
    else:
        from PIL import Image
        with Image.open(path) as im:
            if im.width * im.height > 40_000_000: raise ValueError("Image trop grande")
            im.verify()

def docx_paragraphs(doc):
    yield from doc.paragraphs
    def tables(items):
        for table in items:
            seen = set()
            for row in table.rows:
                for cell in row.cells:
                    if id(cell._tc) in seen: continue
                    seen.add(id(cell._tc))
                    yield from cell.paragraphs
                    yield from tables(cell.tables)
    yield from tables(doc.tables)
    for section in doc.sections:
        for part in (section.header, section.footer):
            yield from part.paragraphs
            yield from tables(part.tables)

def pptx_paragraphs(presentation):
    def shapes(items):
        for shape in items:
            if shape.shape_type == 6: yield from shapes(shape.shapes)
            if shape.has_text_frame: yield from shape.text_frame.paragraphs
            if shape.has_table:
                for row in shape.table.rows:
                    for cell in row.cells: yield from cell.text_frame.paragraphs
    for slide in presentation.slides: yield from shapes(slide.shapes)

def extract(path, suffix):
    if suffix == ".docx":
        from docx import Document
        return [p.text for p in docx_paragraphs(Document(path)) if p.text.strip()]
    if suffix == ".pptx":
        from pptx import Presentation
        return [p.text for p in pptx_paragraphs(Presentation(path)) if p.text.strip()]
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted: raise ValueError("PDF chiffré non supporté")
        if len(reader.pages) > 500: raise ValueError("PDF limité à 500 pages")
        from .ocr import scan_pdf
        return [line['text'] for line in scan_pdf(path)]
    from .ocr import recognize
    return [line["text"] for line in recognize(path)]

def replace_paragraph(p, text):
    # Keep drawings and unrelated XML. Collapse translated text into the first
    # text node; run-level mixed formatting cannot be preserved reliably.
    nodes = p._p.xpath('.//*[local-name()="t"]')
    if nodes:
        nodes[0].text = text
        for node in nodes[1:]: node.text = ""

def exports(original, suffix, targets, output, segments=None):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    from docx import Document
    if suffix == ".docx":
        doc = Document(original)
        paragraphs = [p for p in docx_paragraphs(doc) if p.text.strip()]
        if len(paragraphs) != len(targets): raise ValueError("Structure du document modifiée")
        for p, t in zip(paragraphs, targets): replace_paragraph(p, t)
        doc.save(output / "translation.docx")
    else:
        doc = Document()
        for t in targets: doc.add_paragraph(t)
        doc.save(output / "translation.docx")
        if suffix == ".pptx":
            from pptx import Presentation
            presentation = Presentation(original)
            paragraphs = [p for p in pptx_paragraphs(presentation) if p.text.strip()]
            if len(paragraphs) != len(targets): raise ValueError("Structure de la présentation modifiée")
            for p, t in zip(paragraphs, targets): replace_paragraph(p, t)
            presentation.save(output / "translation.pptx")
    if suffix == '.pdf':
        from .pdf_layout import export_pdf
        if segments is None:
            segments = analyze(original, suffix)
        return export_pdf(original, targets, segments, output / 'translation.pdf')
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    styles = getSampleStyleSheet()
    story = []
    for t in targets:
        story.extend([Paragraph(escape(t), styles["BodyText"]), Spacer(1, 8)])
    SimpleDocTemplate(str(output / "translation.pdf")).build(story)


def analyze(path, suffix):
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        from .ocr import recognize
        return [dict(line, page=1) for line in recognize(path)]
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted: raise ValueError("PDF chiffré non supporté")
        if len(reader.pages) > 500: raise ValueError("PDF limité à 500 pages")
        # Both native and scanned PDFs need page coordinates for visual export.
        from .ocr import scan_pdf
        return scan_pdf(path)
    return [{"text":text,"confidence":1.0,"box":None,"page":None} for text in extract(path,suffix)]
