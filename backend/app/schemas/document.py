from datetime import datetime

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: int
    owner_id: int
    filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime
    processing_status: str
    processing_error: str | None
    page_count: int | None
    embedding_status: str
    embedding_error: str | None
    visibility: str

    model_config = {"from_attributes": True}


class DocumentSearchRequest(BaseModel):
    query: str = Field(min_length=1)


class DocumentSearchResult(BaseModel):
    document_id: int
    filename: str
    similarity: float
    matched_snippet: str
    page_number: int | None
    section_title: str | None


class DocumentChunkOut(BaseModel):
    id: int
    chunk_index: int
    content: str
    char_count: int
    page_number: int | None
    section_title: str | None

    model_config = {"from_attributes": True}
