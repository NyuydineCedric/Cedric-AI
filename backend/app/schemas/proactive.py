from pydantic import BaseModel


class UpcomingDeadline(BaseModel):
    memory_id: int
    label: str
    date: str
    days_remaining: int