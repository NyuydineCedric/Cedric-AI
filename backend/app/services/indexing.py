# app/services/indexing.py
from pinecone import Pinecone
import os

from app.services.embeddings import embed_text

_pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
_index = _pc.Index("cedric-ai-chunks")

def index_chunk(chunk) -> None:
    vector = embed_text(chunk.content, task_type="RETRIEVAL_DOCUMENT")
    _index.upsert(vectors=[{
        "id": str(chunk.id),
        "values": vector,
        "metadata": {
            "owner_id": chunk.owner_id,
            "document_id": chunk.document_id,
        },
    }])