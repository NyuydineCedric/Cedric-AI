"""
Cedric AI - Document Routes
=============================

  POST   /api/documents/upload         - upload a file
  GET    /api/documents                - list *my* documents
  GET    /api/documents/{id}/download  - download one of *my* documents
  DELETE /api/documents/{id}           - delete one of *my* documents

PERMISSION-AWARE RETRIEVAL, EXPLAINED:
Every query below filters by `Document.owner_id == current_user.id`.
That's not a style choice - it's the actual security boundary. If any
of these routes forgot that filter, one student could list, download,
or delete another student's files just by guessing an id. This is the
same principle the project spec calls out explicitly for RAG later:
permission-aware retrieval has to be enforced at the query level, not
left to "the frontend won't show you other people's stuff."
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import User
from app.schemas.document import (
    DocumentChunkOut,
    DocumentOut,
    DocumentSearchRequest,
    DocumentSearchResult,
)
from app.services.document_processing import process_document
from app.services.embeddings import embed_document_chunks
from app.services.retrieval import remove_chunks_from_keyword_index
from app.services.semantic_search import search_documents_by_meaning
from app.services.storage import UploadValidationError, delete_file, resolve_path, save_upload

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy import or_

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_VISIBILITIES = {"personal", "university"}

def _get_accessible_document(document_id: int, current_user: User, db: Session) -> Document:
    """
    Like _get_owned_document, but also allows read access to any
    'university' document regardless of who uploaded it - the whole
    point of shared institutional material. Ownership is still
    required for anything destructive (see delete_document, which
    deliberately keeps using _get_owned_document instead of this).
    """
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            or_(Document.owner_id == current_user.id, Document.visibility == "university"),
        )
        .first()
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    visibility: str = Form(default="personal"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if visibility not in ALLOWED_VISIBILITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"visibility must be one of {sorted(ALLOWED_VISIBILITIES)}",
        )

    contents = await file.read()
    try:
        stored_filename, content_type, size_bytes = save_upload(current_user.id, file, contents)
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    document = Document(
        owner_id=current_user.id,
        filename=file.filename or "unnamed",
        stored_filename=stored_filename,
        content_type=content_type,
        size_bytes=size_bytes,
        visibility=visibility,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    process_document(db, document)
    embed_document_chunks(db, document)
    db.refresh(document)

    return document


@router.get("", response_model=list[DocumentOut])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Everyone sees their own documents, plus every 'university'
    # document regardless of who uploaded it - that's the shared
    # knowledge base the project spec describes.
    return (
        db.query(Document)
        .filter(or_(Document.owner_id == current_user.id, Document.visibility == "university"))
        .order_by(Document.uploaded_at.desc())
        .all()
    )


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = _get_accessible_document(document_id, current_user, db)  # changed from _get_owned_document
    # ...rest of this function stays exactly the same...


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkOut])
def list_document_chunks(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = _get_accessible_document(document_id, current_user, db)  # changed from _get_owned_document
    # NOTE: chunk ownership filter below must also loosen to match -
    # see next block.
    return (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)  # owner_id filter removed here
        .order_by(DocumentChunk.chunk_index)
        .all()
    )




def _get_owned_document(document_id: int, current_user: User, db: Session) -> Document:
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner_id == current_user.id)
        .first()
    )
    if document is None:
        # Same 404 whether the id doesn't exist at all or belongs to
        # someone else - never confirm that another user's document
        # id is valid.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return document


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contents = await file.read()

    try:
        stored_filename, content_type, size_bytes = save_upload(
            current_user.id, file, contents
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    document = Document(
        owner_id=current_user.id,
        filename=file.filename or "unnamed",
        stored_filename=stored_filename,
        content_type=content_type,
        size_bytes=size_bytes,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Phase 5: extract + chunk immediately (see document_processing.py
    # for why this runs synchronously rather than in a background job).
    process_document(db, document)
    # Phase 6: embed whatever chunks extraction produced, so the
    # document is immediately searchable by meaning (Phase 7 RAG).
    embed_document_chunks(db, document)
    db.refresh(document)

    return document


@router.get("", response_model=list[DocumentOut])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Document)
        .filter(Document.owner_id == current_user.id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )


@router.post("/search", response_model=list[DocumentSearchResult])
def search_documents(
    payload: DocumentSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Phase 11: "find the file where I wrote about X" - returns actual
    documents (ranked, with the matching excerpt), not a generated
    answer. See services/semantic_search.py.
    """
    try:
        return search_documents_by_meaning(db, current_user.id, payload.query)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = _get_owned_document(document_id, current_user, db)
    path = resolve_path(current_user.id, document.stored_filename)

    if not path.exists():
        # DB row exists but the file on disk doesn't - a genuine
        # inconsistency (e.g. disk was cleared). Surface it honestly
        # rather than pretending the download succeeded.
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="The file is missing from storage.",
        )

    return FileResponse(
        path=path,
        media_type=document.content_type,
        filename=document.filename,
    )


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkOut])
def list_document_chunks(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lets you see exactly what Phase 5's extraction/chunking produced
    for a document - useful for demonstrating and debugging the
    pipeline before Phase 6/7 build embeddings and retrieval on top
    of these same rows.
    """
    _get_owned_document(document_id, current_user, db)  # ownership check
    return (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id, DocumentChunk.owner_id == current_user.id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = _get_owned_document(document_id, current_user, db)
    delete_file(current_user.id, document.stored_filename)

    # No FK cascade configured (SQLite doesn't enforce FKs by default),
    # so chunks - and their Phase 9 keyword-search index rows - are
    # cleaned up explicitly rather than left orphaned.
    chunk_ids = [
        row.id
        for row in db.query(DocumentChunk.id).filter(DocumentChunk.document_id == document.id).all()
    ]
    remove_chunks_from_keyword_index(db, chunk_ids)
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
    db.delete(document)
    db.commit()
