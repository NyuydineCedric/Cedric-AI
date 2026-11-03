"""
Cedric AI - RAG Evaluation (Phase 26)
=========================================

Two genuinely different kinds of measurement here:

1. RETRIEVAL METRICS (Recall@K, Precision@K, MRR) - these require
   ground truth: for a given question, which chunk(s) SHOULD have
   been retrieved. That's a judgment call only a human can make - an
   AI-generated "ground truth" would just be the system grading
   itself. See eval_dataset.py for the format you fill in by hand.

2. GENERATION METRICS (groundedness rate) - these DON'T need ground
   truth, because Phase 25's verification step already independently
   judges each individual answer. This function just aggregates those
   judgments across many questions into a rate.

INPUT            -> a labeled dataset: [{question, relevant_chunk_ids}]
PREPROCESSING     -> run each question through the real retrieval
                      pipeline (hybrid_search) exactly as production does
[AI/MODEL step happens inside hybrid_search/verify_groundedness -
 this module doesn't call Gemini directly]
POSTPROCESSING    -> compare retrieved ids against labeled relevant
                      ids; compute standard IR metrics
OUTPUT            -> per-question and aggregate scores
"""

from sqlalchemy.orm import Session

from app.services.retrieval import hybrid_search


def _recall_at_k(retrieved_ids: list[int], relevant_ids: set[int]) -> float:
    if not relevant_ids:
        return 0.0
    found = len(set(retrieved_ids) & relevant_ids)
    return found / len(relevant_ids)


def _precision_at_k(retrieved_ids: list[int], relevant_ids: set[int]) -> float:
    if not retrieved_ids:
        return 0.0
    found = len(set(retrieved_ids) & relevant_ids)
    return found / len(retrieved_ids)


def _reciprocal_rank(retrieved_ids: list[int], relevant_ids: set[int]) -> float:
    for rank, chunk_id in enumerate(retrieved_ids, start=1):
        if chunk_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def evaluate_retrieval(
    db: Session, owner_id: int, dataset: list[dict], top_k: int = 5
) -> dict:
    """
    `dataset` entries look like:
      {"question": "...", "relevant_chunk_ids": [12, 15]}
    """
    per_question = []
    for item in dataset:
        ranked = hybrid_search(db, owner_id, item["question"], top_k=top_k)
        retrieved_ids = [chunk.id for chunk, _score in ranked]
        relevant_ids = set(item["relevant_chunk_ids"])

        per_question.append(
            {
                "question": item["question"],
                "retrieved_chunk_ids": retrieved_ids,
                "recall_at_k": round(_recall_at_k(retrieved_ids, relevant_ids), 3),
                "precision_at_k": round(_precision_at_k(retrieved_ids, relevant_ids), 3),
                "reciprocal_rank": round(_reciprocal_rank(retrieved_ids, relevant_ids), 3),
            }
        )

    n = len(per_question) or 1
    aggregate = {
        "mean_recall_at_k": round(sum(q["recall_at_k"] for q in per_question) / n, 3),
        "mean_precision_at_k": round(sum(q["precision_at_k"] for q in per_question) / n, 3),
        "mrr": round(sum(q["reciprocal_rank"] for q in per_question) / n, 3),
        "num_questions": len(per_question),
        "top_k": top_k,
    }
    return {"per_question": per_question, "aggregate": aggregate}