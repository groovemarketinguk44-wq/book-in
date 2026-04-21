import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..config import settings
from ..dependencies import get_current_business
from ..models import Business

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE_MB = 5


@router.post("")
async def upload_image(
    file: UploadFile = File(...),
    business: Business = Depends(get_current_business),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, WebP or GIF allowed")

    data = await file.read()
    if len(data) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File must be under {MAX_SIZE_MB}MB")

    upload_dir = Path(settings.UPLOAD_DIR) / str(business.id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "img.jpg").suffix.lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = upload_dir / filename

    with open(dest, "wb") as f:
        f.write(data)

    return {"url": f"/uploads/{business.id}/{filename}"}
