from pydantic import BaseModel


class EvalDatasetItem(BaseModel):
    question: str
    relevant_chunk_ids: list[int]


class EvalRunRequest(BaseModel):
    dataset: list[EvalDatasetItem]
    top_k: int = 5


class PerQuestionResult(BaseModel):
    question: str
    retrieved_chunk_ids: list[int]
    recall_at_k: float
    precision_at_k: float
    reciprocal_rank: float


class EvalAggregate(BaseModel):
    mean_recall_at_k: float
    mean_precision_at_k: float
    mrr: float
    num_questions: int
    top_k: int


class EvalRunResponse(BaseModel):
    per_question: list[PerQuestionResult]
    aggregate: EvalAggregate