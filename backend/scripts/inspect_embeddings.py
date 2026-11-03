# scripts/inspect_embeddings.py
from app.db.database import SessionLocal
from app.models.document_chunk import DocumentChunk
import numpy as np

db = SessionLocal()

total = db.query(DocumentChunk).count()
chunks = db.query(DocumentChunk).limit(10).all()

print(f"Showing 10 of {total} total chunks\n")

for chunk in chunks:
    print(f"Chunk id={chunk.id}, document_id={chunk.document_id}")
    print(f"  content: {chunk.content[:80]}...")
    if chunk.embedding is not None:
        vec = np.frombuffer(chunk.embedding, dtype=np.float32)
        print(f"  embedding: {vec.shape[0]} dimensions")
        print(f"  first 5 values: {vec[:5]}")
    else:
        print("  embedding: NULL (not embedded)")
    print()

db.close()