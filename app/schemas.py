from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, field_validator
from app.validators import is_valid_url


# ── Link schemas ────────────────────────────────────────────────────────────

class ShortenRequest(BaseModel):
    url: str
    expiry_days: Optional[int] = None
    custom_alias: Optional[str] = None
    one_time: bool = False
    password: Optional[str] = None
    starts_at: Optional[datetime] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not is_valid_url(v):
            raise ValueError("Must be a valid http/https URL")
        return v.strip()

    @field_validator("custom_alias")
    @classmethod
    def validate_alias(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not (2 <= len(v) <= 32):
            raise ValueError("Alias must be 2–32 characters")
        if not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError("Alias may only contain letters, digits, hyphens, underscores")
        _RESERVED = {
            "admin", "api", "auth", "docs", "redoc", "openapi.json",
            "shorten", "bulk", "stats", "analytics", "qr", "my-links",
        }
        if v.lower() in _RESERVED:
            raise ValueError(f"Alias '{v}' is reserved")
        return v


class ShortenResponse(BaseModel):
    short_url: str
    short_code: str
    long_url: str
    expires_at: datetime
    starts_at: Optional[datetime]
    created: bool
    one_time: bool
    qr_url: str


class StatsResponse(BaseModel):
    short_code: str
    short_url: str
    long_url: str
    created_at: datetime
    expires_at: datetime
    starts_at: Optional[datetime]
    last_accessed_at: Optional[datetime]
    click_count: int
    is_expired: bool
    is_active: bool
    one_time: bool
    has_password: bool
    owner_id: Optional[int]


class ClickEventOut(BaseModel):
    clicked_at: datetime
    country: Optional[str]
    city: Optional[str]
    browser: Optional[str]
    os: Optional[str]
    device: Optional[str]
    referrer: Optional[str]


class AnalyticsResponse(BaseModel):
    short_code: str
    total_clicks: int
    clicks_by_country: Dict[str, int]
    clicks_by_browser: Dict[str, int]
    clicks_by_os: Dict[str, int]
    clicks_by_device: Dict[str, int]
    recent_clicks: List[ClickEventOut]


# ── Bulk shortening ─────────────────────────────────────────────────────────

class BulkItem(BaseModel):
    url: str
    custom_alias: Optional[str] = None
    expiry_days: Optional[int] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not is_valid_url(v):
            raise ValueError("Must be a valid http/https URL")
        return v.strip()


class BulkShortenRequest(BaseModel):
    urls: List[BulkItem]


class BulkShortenResponse(BaseModel):
    results: List[ShortenResponse]


# ── Auth schemas ─────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime
    api_key: Optional[str]


class APIKeyResponse(BaseModel):
    api_key: str


# ── Password-unlock ──────────────────────────────────────────────────────────

class UnlockRequest(BaseModel):
    password: str
