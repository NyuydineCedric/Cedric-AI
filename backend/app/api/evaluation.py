"""
Cedric AI - RAG Evaluation Route (Phase 26)
===============================================

POST /api/evaluation/retrieval - run Recall@K/Precision@K/MRR against
a dataset YOU provide (see the module docstring in services/
evaluation.py for why ground truth can't be auto-generated).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.evaluation import EvalRunRequest, EvalRunResponse
from app.services.evaluation import evaluate_retrieval

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.post("/retrieval", response_model=EvalRunResponse)
def run_retrieval_evaluation(
    payload: EvalRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dataset = [item.model_dump() for item in payload.dataset]
    return evaluate_retrieval(db, current_user.id, dataset, top_k=payload.top_k)