import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from sqlalchemy.orm import Session

from app.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRY_MINUTES
from app.database import User, get_db

_bearer = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRY_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=30)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "refresh": True},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)


def _decode_token(token: str, db: Session) -> Optional[User]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("refresh"):
            return None
        return db.query(User).filter(User.id == int(payload["sub"])).first()
    except (JWTError, KeyError, ValueError):
        return None


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer),
    api_key: Optional[str] = Security(_api_key_header),
    db: Session = Depends(get_db),
) -> User:
    user = _resolve_user(credentials, api_key, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer),
    api_key: Optional[str] = Security(_api_key_header),
    db: Session = Depends(get_db),
) -> Optional[User]:
    return _resolve_user(credentials, api_key, db)


def _resolve_user(
    credentials: Optional[HTTPAuthorizationCredentials],
    api_key: Optional[str],
    db: Session,
) -> Optional[User]:
    if credentials:
        user = _decode_token(credentials.credentials, db)
        if user:
            return user
    if api_key:
        return db.query(User).filter(User.api_key == api_key).first()
    return None
