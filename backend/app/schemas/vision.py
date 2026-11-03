from pydantic import BaseModel


class VisionAnalyzeResponse(BaseModel):
    description: str
