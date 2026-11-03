"""
Cedric AI - Memory Routes (Phase 12)
=======================================

  POST   /api/memory         - remember a new fact about the student
  GET    /api/memory          - list everything remembered (optionally
                                  filtered by category)
  DELETE /api/memory/{id}     - forget something

No AI calls here - this is intentionally plain CRUD. The interesting
AI behavior comes later: Phase 13 (context engine) decides which
memories are relevant to pull into a given prompt, and Phase 15 (tool
system) lets the model itself call save_memory()/get_memory() as
explicit, permission-scoped tools rather than freely writing to the
database - see that phase for why that boundary matters.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.memory import Memory
from app.models.user import User
from app.schemas.memory import MemoryCreate, MemoryOut

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.post("", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
def create_memory(
    payload: MemoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memory = Memory(owner_id=current_user.id, category=payload.category, content=payload.content)
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


@router.get("", response_model=list[MemoryOut])
def list_memories(
    category: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Memory).filter(Memory.owner_id == current_user.id)
    if category:
        query = query.filter(Memory.category == category)
    return query.order_by(Memory.created_at.desc()).all()


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memory = (
        db.query(Memory)
        .filter(Memory.id == memory_id, Memory.owner_id == current_user.id)
        .first()
    )
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    db.delete(memory)
    db.commit()
