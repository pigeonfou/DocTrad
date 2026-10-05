"""Optional structured PDF analysis. No fallback downloads.
Adapter must be acceptance-tested with the transferred Docling artifacts.
"""
from pathlib import Path

def convert(path, artifacts):
    root=Path(artifacts)
    if not root.is_dir() or not any(root.iterdir()):raise ValueError('Artefacts Docling locaux absents')
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    options=PdfPipelineOptions(artifacts_path=root,do_ocr=False,enable_remote_services=False)
    converter=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=options)})
    return converter.convert(Path(path)).document
