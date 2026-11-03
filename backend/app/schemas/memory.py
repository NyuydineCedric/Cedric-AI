from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.memory import MEMORY_CATEGORIES


class MemoryCreate(BaseModel):
    category: str = Field(default="other")
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("category")
    @classmethod
    def category_must_be_known(cls, value: str) -> str:
        if value not in MEMORY_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(MEMORY_CATEGORIES)}")
        return value


class MemoryOut(BaseModel):
    id: int
    category: str
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
