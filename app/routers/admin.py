import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import service
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])

_ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")


def _require_admin(x_admin_secret: str = Header(default="")):
    if not _ADMIN_SECRET or x_admin_secret != _ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/purge", dependencies=[Depends(_require_admin)])
def purge_expired(db: Session = Depends(get_db)):
    count = service.purge_expired(db)
    return {"purged": count}
