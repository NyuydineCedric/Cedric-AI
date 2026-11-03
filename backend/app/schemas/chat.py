"""
Cedric AI - Chat Schemas
==========================

Phase 3 keeps this deliberately simple: the frontend holds the
conversation in memory and sends the whole thing on each request; the
backend does not persist chat history to the database yet. That's
intentional - Phase 12+ (memory / context engine) is where we decide
what's worth remembering long-term, and conflating "basic Gemini
plumbing" with "conversation storage design" would make this phase
harder to reason about than it needs to be.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str
