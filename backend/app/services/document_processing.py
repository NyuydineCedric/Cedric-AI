"""
Cedric AI - Document Processing Pipeline
===========================================

AI ENGINEERING DATA FLOW FOR THIS FEATURE (this is prep work for RAG,
not RAG itself yet - see Phase 6/7 for embeddings + retrieval):

  INPUT          -> a file on disk (PDF/DOCX/PPTX/TXT)
  PREPROCESSING  -> format-specific text extraction, split into
                     structural units (pages/headings/slides),
                     then chunked to a manageable size
  [no AI/MODEL step here - that's Phase 6]
  OUTPUT         -> DocumentChunk rows, ready to be embedded later

WHY SYNCHRONOUS (not a background job queue):
Processing runs inline, immediately after upload, inside the same
request. For a portfolio-scale project with normal-sized course notes
(a few dozen pages) this is fast enough not to matter. A production
system handling large files or many concurrent uploads would move
this to a background worker (Celery/RQ + Redis) so the upload request
returns instantly - that's a real architectural upgrade, flagged here
rather than silently pretended away.

WHY IMAGES AREN'T EXTRACTED YET:
Getting text out of a photo or scanned page is OCR, not the same
problem as reading a PDF's embedded text layer. The project roadmap
gives vision/OCR its own dedicated phase (image understanding). Rather
than bolt on a partial OCR solution here, image documents are marked
"unsupported" for extraction now and revisited properly later.
"""

from pathlib import Path

import fitz  # PyMuPDF
from docx import Document as DocxFile
from pptx import Presentation
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.retrieval import index_chunk_for_keyword_search
from app.services.storage import resolve_path

# Target size for a chunk, and how much consecutive chunks overlap.
# Overlap exists so a sentence or idea that happens to fall right on a
# chunk boundary isn't split with no shared context on either side -
# a common cause of bad retrieval later.
MAX_CHUNK_CHARS = 1000
CHUNK_OVERLAP_CHARS = 150


class ProcessingResult:
    def __init__(self, units: list[dict], page_count: int | None):
        self.units = units  # [{text, page_number, section_title}]
        self.page_count = page_count


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """Split `text` into overlapping windows, only if it's too long to begin with."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def _extract_pdf(path: Path) -> ProcessingResult:
    units = []
    with fitz.open(path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text().strip()
            if text:
                units.append({"text": text, "page_number": page_number, "section_title": None})
        page_count = pdf.page_count
    return ProcessingResult(units, page_count)


def _extract_docx(path: Path) -> ProcessingResult:
    doc = DocxFile(path)
    units: list[dict] = []
    current_heading: str | None = None
    buffer: list[str] = []

    def flush():
        joined = "\n".join(buffer).strip()
        if joined:
            units.append({"text": joined, "page_number": None, "section_title": current_heading})
        buffer.clear()

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style_name = para.style.name if para.style else ""
        if style_name.startswith("Heading"):
            # A new heading starts a new structural section - flush
            # whatever we were accumulating under the previous one.
            flush()
            current_heading = text
        else:
            buffer.append(text)
    flush()

    return ProcessingResult(units, page_count=None)


def _extract_pptx(path: Path) -> ProcessingResult:
    presentation = Presentation(path)
    units = []
    for slide_number, slide in enumerate(presentation.slides, start=1):
        texts = [
            shape.text_frame.text.strip()
            for shape in slide.shapes
            if shape.has_text_frame and shape.text_frame.text.strip()
        ]
        combined = "\n".join(texts)
        if combined:
            units.append({"text": combined, "page_number": slide_number, "section_title": None})
    return ProcessingResult(units, page_count=len(presentation.slides))


def _extract_txt(path: Path) -> ProcessingResult:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    units = [{"text": text, "page_number": None, "section_title": None}] if text else []
    return ProcessingResult(units, page_count=None)


_EXTRACTORS = {
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
    ".pptx": _extract_pptx,
    ".txt": _extract_txt,
}


def is_supported(extension: str) -> bool:
    return extension.lower() in _EXTRACTORS


def extract_and_chunk(path: Path, extension: str) -> ProcessingResult:
    """
    Run the right extractor for `extension`, then chunk each
    structural unit's text if it's longer than MAX_CHUNK_CHARS.
    Raises if the extension isn't supported - callers should check
    `is_supported` first.
    """
    extractor = _EXTRACTORS[extension.lower()]
    result = extractor(path)

    chunked_units = []
    for unit in result.units:
        for piece in chunk_text(unit["text"]):
            chunked_units.append({**unit, "text": piece})

    return ProcessingResult(chunked_units, result.page_count)


_IMAGE_EXTENSIONS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

_IMAGE_DESCRIPTION_PROMPT = (
    "Describe this image factually and in enough detail to be useful "
    "as searchable study material: if it's a diagram, explain what it "
    "shows; if it contains text (handwritten notes, a screenshot, a "
    "slide), transcribe the key content. Don't guess at anything you "
    "can't actually see."
)


def _persist_chunks(db: Session, document: Document, units: list[dict], page_count: int | None) -> None:
    """Shared by both the text-extraction and image-description paths below."""
    new_chunks = []
    for index, unit in enumerate(units):
        chunk = DocumentChunk(
            document_id=document.id,
            owner_id=document.owner_id,
            chunk_index=index,
            content=unit["text"],
            char_count=len(unit["text"]),
            page_number=unit["page_number"],
            section_title=unit["section_title"],
        )
        db.add(chunk)
        new_chunks.append(chunk)

    # flush (not commit) assigns each chunk its id without ending the
    # transaction yet - needed before indexing into the Phase 9
    # keyword-search table, which stores rowid = chunk.id.
    db.flush()
    for chunk in new_chunks:
        index_chunk_for_keyword_search(db, chunk.id, chunk.content)

    document.processing_status = "completed"
    document.processing_error = None
    document.page_count = page_count
    db.commit()


def _process_image_document(db: Session, document: Document, extension: str) -> None:
    """
    Phase 18: rather than permanently marking images "unsupported,"
    describe them with Gemini vision and store that description as a
    single searchable chunk - clearly labeled as AI-generated (not
    literal document text), so citations built from it stay honest
    about provenance. See services/gemini_client.py's describe_image.
    """
    from app.services.gemini_client import get_gemini_client  # local import: avoids a hard
    # dependency on the Gemini client for the (much more common) plain-text extraction path.

    try:
        client = get_gemini_client()
    except RuntimeError:
        document.processing_status = "unavailable"
        document.processing_error = (
            "Image description requires GEMINI_API_KEY to be configured. "
            "Re-upload once it's set to make this image searchable."
        )
        db.commit()
        return

    path = resolve_path(document.owner_id, document.stored_filename)
    try:
        description = client.describe_image(
            path.read_bytes(), _IMAGE_EXTENSIONS[extension], _IMAGE_DESCRIPTION_PROMPT
        )
    except Exception as exc:  # noqa: BLE001 - any vision-call failure
        document.processing_status = "failed"
        document.processing_error = str(exc)[:500]
        db.commit()
        return

    unit = {"text": description, "page_number": None, "section_title": "AI-generated image description"}
    _persist_chunks(db, document, [unit], page_count=None)


def process_document(db: Session, document: Document) -> None:
    """
    Run extraction + chunking for `document` and persist the results.
    Always leaves `document.processing_status` in a terminal state
    (completed/unavailable/unsupported/failed) and commits - callers
    don't need to handle the DB write themselves.
    """
    extension = Path(document.filename).suffix.lower()

    if extension in _IMAGE_EXTENSIONS:
        _process_image_document(db, document, extension)
        return

    if not is_supported(extension):
        document.processing_status = "unsupported"
        document.processing_error = "Text extraction isn't available for this file type."
        db.commit()
        return

    path = resolve_path(document.owner_id, document.stored_filename)

    try:
        result = extract_and_chunk(path, extension)
    except Exception as exc:  # noqa: BLE001 - genuinely want to catch any parser failure
        # A corrupt or unusual file shouldn't take the whole upload
        # request down - record the failure and let the student see it.
        document.processing_status = "failed"
        document.processing_error = str(exc)[:500]
        db.commit()
        return

    if not result.units:
        document.processing_status = "completed"
        document.processing_error = "No extractable text was found in this file."
        document.page_count = result.page_count
        db.commit()
        return

    _persist_chunks(db, document, result.units, result.page_count)
