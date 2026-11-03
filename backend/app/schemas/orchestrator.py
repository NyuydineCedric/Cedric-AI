from pydantic import BaseModel

from app.schemas.chat import ChatMessage


class OrchestratorRequest(BaseModel):
    messages: list[ChatMessage]


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict


class OrchestratorResponse(BaseModel):
    answer: str
    # Which tools Gemini decided to call, and with what arguments -
    # shown in the UI so the student (and you, demonstrating this
    # project) can see the orchestration actually happening, not just
    # trust that it did.
    tools_used: list[ToolCallRecord]

class OrchestratorResponse(BaseModel):
    answer: str
    tools_used: list[ToolCallRecord]
    sketch: str | None = None