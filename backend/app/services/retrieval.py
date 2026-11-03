"""
Cedric AI - Hybrid Retrieval & Reranking (Phase 9)
======================================================

Phase 6/7 retrieval was vector-only: embed the query, cosine-similarity
search. That works well for meaning-based matches but can miss an
exact acronym, code identifier, or proper noun that the embedding
model blurs together with related-but-different terms. Phase 9 adds a
second, independent retrieval path - keyword search - and fuses the
two, then reorders the fused list with a reranking step:

  QUERY
    |
    +--> VECTOR SEARCH (Phase 6: cosine similarity over embeddings)
    |
    +--> KEYWORD SEARCH (SQLite FTS5 / BM25 - exact term matching)
    |
  RESULT FUSION (Reciprocal Rank Fusion - see _reciprocal_rank_fusion)
    |
  RERANKING (Gemini reads the fused candidates and reorders them by
             actual relevance, not just lexical/vector proximity)
    |
  FINAL RANKED CHUNKS

WHY SQLITE FTS5 (no new dependency):
FTS5 ships inside Python's stdlib sqlite3 build - it's a real,
standard full-text index with BM25 ranking, not a hand-rolled
word-counting hack. It's SQLite-specific, though: migrating to
Postgres (per the Phase 6 storage note) would swap this for Postgres's
native tsvector/tsquery full-text search, which plays the same role.

WHY AN LLM RERANKER (no new dependency):
A proper cross-encoder reranker model would need a heavy ML
dependency (e.g. sentence-transformers + torch) this environment can't
install quickly. Asking Gemini itself to read the fused candidates and
reorder them by relevance is a legitimate, commonly used alternative -
it costs one extra API call per question, which is the real tradeoff
being made here (latency/cost vs. quality), not a shortcut around
having "real" reranking.
"""

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk
from app.services.embeddings import (
    chunk_similarity_to,
    cosine_similarity,
    embed_query,
    search_similar_chunks,
)
from app.services.gemini_client import GeminiClient, get_gemini_client


# --------------------------------------------------------------------
# Keyword search (SQLite FTS5)
# --------------------------------------------------------------------

def ensure_fts_table(db: Session) -> None:
    """Called once at startup - creates the full-text index if it doesn't exist yet."""
    db.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(content)"))
    db.commit()


def index_chunk_for_keyword_search(db: Session, chunk_id: int, content: str) -> None:
    """Called right after a DocumentChunk is created (see document_processing.py)."""
    db.execute(
        text("INSERT INTO document_chunks_fts (rowid, content) VALUES (:id, :content)"),
        {"id": chunk_id, "content": content},
    )


def remove_chunks_from_keyword_index(db: Session, chunk_ids: list[int]) -> None:
    """Called when a document is deleted, to keep the FTS index from holding stale rows."""
    if not chunk_ids:
        return
    # FTS5 doesn't support parameterized `IN (:ids)` with a Python list
    # the way a normal table does, so the ids are inlined directly -
    # safe here because they're `int(...)`-coerced, never raw strings.
    id_list = ",".join(str(int(cid)) for cid in chunk_ids)
    db.execute(text(f"DELETE FROM document_chunks_fts WHERE rowid IN ({id_list})"))


def _sanitize_fts_query(query: str) -> str:
    """
    FTS5's query syntax treats characters like `"`, `-`, `*` specially.
    Rather than trying to escape a user's free-text question, extract
    plain word tokens and OR them together as quoted literals - this
    treats every token as plain text and can't produce an invalid
    FTS5 query, at the cost of not supporting FTS5's own operators
    (which a student typing a normal question was never going to use
    anyway).
    """
    terms = re.findall(r"\w+", query)
    if not terms:
        return '""'
    return " OR ".join(f'"{t}"' for t in terms)


def _keyword_search(db: Session, owner_id: int, query: str, top_k: int) -> list[int]:
    """Returns chunk ids ranked by BM25 relevance, best first."""
    fts_query = _sanitize_fts_query(query)
    rows = db.execute(
        text(
            "SELECT document_chunks_fts.rowid AS chunk_id "
            "FROM document_chunks_fts "
            "JOIN document_chunks ON document_chunks.id = document_chunks_fts.rowid "
            "JOIN documents ON documents.id = document_chunks.document_id "
            "WHERE document_chunks_fts MATCH :q "
            "AND (document_chunks.owner_id = :owner_id OR documents.visibility = 'university') "
            "ORDER BY bm25(document_chunks_fts) LIMIT :top_k"
        ),
        {"q": fts_query, "owner_id": owner_id, "top_k": top_k},
    ).all()
    return [row.chunk_id for row in rows]

# --------------------------------------------------------------------
# Result fusion
# --------------------------------------------------------------------

def _reciprocal_rank_fusion(rankings: list[list[int]], k: int = 60) -> dict[int, float]:
    """
    Combines multiple ranked id-lists into one fused score per id.
    RRF is deliberately rank-based rather than score-based: cosine
    similarity (0-1) and BM25 (an unbounded, corpus-dependent number)
    aren't on comparable scales, so summing raw scores would let
    whichever method happens to produce bigger numbers dominate. Using
    rank position instead - "1/(k + rank)" - treats "found near the
    top of either list" as the signal, regardless of each method's
    particular scoring quirks.
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


# --------------------------------------------------------------------
# LLM-based reranking
# --------------------------------------------------------------------

def _llm_rerank(client: GeminiClient, question: str, candidates: list[DocumentChunk]) -> list[int]:
    """
    Returns candidate indices (into `candidates`) ordered best-match
    first, according to Gemini actually reading each passage - a
    different, complementary signal from either retrieval method's
    lexical/vector proximity score.
    """
    listing = "\n".join(f"{i}: {c.content[:300]}" for i, c in enumerate(candidates))
    prompt = (
        f"Question: {question}\n\n"
        "Below are numbered passages. Reply with ONLY a comma-separated "
        "list of their numbers, ordered from most to least relevant to "
        "the question. No other text.\n\n" + listing
    )
    raw = client.generate_reply([{"role": "user", "content": prompt}])

    order: list[int] = []
    for token in raw.replace("\n", ",").split(","):
        token = token.strip()
        if token.isdigit():
            index = int(token)
            if 0 <= index < len(candidates) and index not in order:
                order.append(index)

    # Fail-safe: any candidate the model's reply didn't mention keeps
    # its original (fusion-determined) relative order, appended at the
    # end, rather than being silently dropped.
    for i in range(len(candidates)):
        if i not in order:
            order.append(i)
    return order


# --------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------

def hybrid_search(
    db: Session,
    owner_id: int,
    query: str,
    top_k: int = 5,
    rerank: bool = True,
) -> list[tuple[DocumentChunk, float]]:
    """
    Combined vector + keyword retrieval, fused with RRF and optionally
    reranked by Gemini. Returns (chunk, cosine_similarity) pairs -
    same shape as embeddings.search_similar_chunks - so callers like
    services/rag.py don't need to know which retrieval strategy
    produced the list.

    The reported score is always genuine cosine similarity (not the
    RRF fusion score, which is on an unrelated scale) - fusion and
    reranking decide *which* chunks and their *order*; similarity is
    still what's shown to the user and used for the "enough evidence?"
    threshold in services/rag.py.
    """
    query_vec = embed_query(query)

    vector_ranked = search_similar_chunks(db, owner_id, query, top_k=20, query_vec=query_vec)
    vector_ids = [chunk.id for chunk, _ in vector_ranked]
    chunk_by_id: dict[int, DocumentChunk] = {chunk.id: chunk for chunk, _ in vector_ranked}

    keyword_ids = _keyword_search(db, owner_id, query, top_k=20)
    missing_ids = [cid for cid in keyword_ids if cid not in chunk_by_id]
    if missing_ids:
        for chunk in db.query(DocumentChunk).filter(DocumentChunk.id.in_(missing_ids)).all():
            chunk_by_id[chunk.id] = chunk

    fused_scores = _reciprocal_rank_fusion([vector_ids, keyword_ids])
    fused_order = sorted(fused_scores, key=lambda cid: fused_scores[cid], reverse=True)
    candidates = [chunk_by_id[cid] for cid in fused_order if cid in chunk_by_id][: max(top_k * 2, 10)]

    if rerank and candidates:
        order = _llm_rerank(get_gemini_client(), query, candidates)
        candidates = [candidates[i] for i in order]

    top_candidates = candidates[:top_k]
    return [(chunk, chunk_similarity_to(query_vec, chunk)) for chunk in top_candidates]
