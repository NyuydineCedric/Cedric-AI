# app/api/debug.py
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
import numpy as np

from app.db.database import get_db
from app.models.document_chunk import DocumentChunk

router = APIRouter()


@router.get("/debug/chunks", response_class=HTMLResponse)
def view_chunks(limit: int = 50, document_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(DocumentChunk)
    if document_id is not None:
        query = query.filter(DocumentChunk.document_id == document_id)
    chunks = query.order_by(DocumentChunk.id).limit(limit).all()

    rows = ""
    for chunk in chunks:
        if chunk.embedding is not None:
            vec = np.frombuffer(chunk.embedding, dtype=np.float32)
            embedding_preview = f"{vec.shape[0]} dims — [{', '.join(f'{v:.4f}' for v in vec[:5])}, ...]"
        else:
            embedding_preview = "NULL"

        rows += f"""
        <tr>
            <td>{chunk.id}</td>
            <td>{chunk.document_id}</td>
            <td>{chunk.chunk_index}</td>
            <td style="max-width:400px">{chunk.content[:200]}...</td>
            <td style="font-family:monospace; font-size:12px">{embedding_preview}</td>
        </tr>
        """

    return f"""
    <html>
    <head>
        <title>Chunk & Embedding Viewer</title>
        <style>
            body {{ font-family: sans-serif; margin: 20px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; vertical-align: top; }}
            th {{ background: #f4f4f4; }}
        </style>
    </head>
    <body>
        <h2>Showing {len(chunks)} chunks{f' for document {document_id}' if document_id else ''}</h2>
        <p>Try <code>?document_id=1</code> or <code>?limit=100</code> in the URL to filter.</p>
        <table>
            <tr><th>id</th><th>document_id</th><th>chunk_index</th><th>content</th><th>embedding</th></tr>
            {rows}
        </table>
    </body>
    </html>
    """