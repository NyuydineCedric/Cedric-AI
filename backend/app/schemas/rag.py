from pydantic import BaseModel, Field


class RagAskRequest(BaseModel):
    question: str = Field(min_length=1)


class RagSource(BaseModel):
    document_id: int
    filename: str
    page_number: int | None
    section_title: str | None
    snippet: str
    similarity: float


class RagAskResponse(BaseModel):
    answer: str
    sources: list[RagSource]
    grounded: bool
    fully_verified: bool | None
    unsupported_claims: list[str]