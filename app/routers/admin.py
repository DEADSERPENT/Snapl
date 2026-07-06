import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import service
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])

def _require_admin(x_admin_secret: str = Header(default="")):
    secret = os.getenv("ADMIN_SECRET") or ""
    if not secret:
        raise HTTPException(status_code=503, detail="Admin endpoint not configured")
    if x_admin_secret != secret:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/purge", dependencies=[Depends(_require_admin)])
def purge_expired(db: Session = Depends(get_db)):
    count = service.purge_expired(db)
    return {"purged": count}
