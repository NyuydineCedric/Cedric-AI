"""
Cedric AI - Vision Route (Phase 18-19)
===========================================

POST /api/vision/analyze - upload a single image (or a photo captured
from a device camera on the frontend) with an optional question, and
get Gemini's analysis of it back.

TECHNICAL LIMITATION, STATED PLAINLY - this matters, per the project
spec's explicit warning not to conflate the two:
This analyzes ONE STILL IMAGE per request. It is NOT continuous
real-time video understanding - there's no persistent video stream
reaching the model, no reasoning across frames over time, no low-
latency perception loop. The frontend's "camera mode" (VisionPanel.jsx)
works by capturing a single photo from the device camera and sending
it exactly like a file upload - a reliable, simple way to let a
student "show Cedric AI something," but genuinely different from a
model watching live video. True continuous video understanding would
need a fundamentally different architecture (streaming frames, video
tokens, WebRTC piping) - out of scope here, and not something to fake
by just calling repeated still-image analysis "video understanding."
"""

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from google.genai.errors import APIError

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.vision import VisionAnalyzeResponse
from app.services.gemini_client import get_gemini_client

router = APIRouter(prefix="/api/vision", tags=["vision"])

DEFAULT_PROMPT = (
    "Describe this image for a student. If it's a diagram, explain what "
    "it shows and how the parts relate. If it contains text (handwritten "
    "notes, a screenshot, a slide), transcribe the key content. Be "
    "factual - don't guess at details you can't actually see."
)

# 10MB is generous for a single photo/screenshot while still bounding
# request size - consistent with the document upload limit's intent
# (see services/storage.py) even though this path doesn't go through it.
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}


@router.post("/analyze", response_model=VisionAnalyzeResponse)
async def analyze_image(
    file: UploadFile,
    prompt: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
):
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty image")
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image too large (max 10MB)")

    mime_type = file.content_type or "image/jpeg"
    if mime_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type '{mime_type}'",
        )

    try:
        client = get_gemini_client()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    try:
        description = client.describe_image(contents, mime_type, prompt or DEFAULT_PROMPT)
    except APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API error: {exc.message}",
        ) from exc

    return VisionAnalyzeResponse(description=description)
