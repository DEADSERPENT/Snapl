from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app import codec
from app.auth import hash_password, verify_password
from app.cache import cache
from app.config import BASE_URL, DEFAULT_EXPIRY_DAYS, GEO_API_URL
from app.database import ClickEvent, SessionLocal, URLRecord, User
from app.schemas import (
    AnalyticsResponse,
    BulkItem,
    ClickEventOut,
    ShortenResponse,
    StatsResponse,
    UserResponse,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(dt: datetime) -> bool:
    if dt.tzinfo is None:
        return dt < datetime.utcnow()  # noqa: DTZ003
    return dt < _utcnow()


def _is_active(record: URLRecord) -> bool:
    if _is_expired(record.expires_at):
        return False
    if record.starts_at and not _is_expired(record.starts_at):
        # starts_at is still in the future
        return False
    return True


def _to_shorten_response(record: URLRecord) -> ShortenResponse:
    short_url = f"{BASE_URL}/{record.short_code}"
    return ShortenResponse(
        short_url=short_url,
        short_code=record.short_code,
        long_url=record.long_url,
        expires_at=record.expires_at,
        starts_at=record.starts_at,
        created=True,
        one_time=record.one_time,
        qr_url=f"{BASE_URL}/qr/{record.short_code}",
    )


# ── Shorten ──────────────────────────────────────────────────────────────────

def shorten(
    db: Session,
    long_url: str,
    expiry_days: Optional[int],
    custom_alias: Optional[str],
    one_time: bool,
    password: Optional[str],
    starts_at: Optional[datetime],
    user_id: Optional[int],
) -> ShortenResponse:
    days = expiry_days if expiry_days is not None else DEFAULT_EXPIRY_DAYS

    if custom_alias:
        existing = db.query(URLRecord).filter(URLRecord.short_code == custom_alias).first()
        if existing:
            raise ValueError(f"Alias '{custom_alias}' is already taken")
        short_code = custom_alias
    else:
        # Idempotency: same URL → return existing record (anonymous only)
        if user_id is None:
            existing = db.query(URLRecord).filter(
                URLRecord.long_url == long_url,
                URLRecord.user_id.is_(None),
                URLRecord.one_time.is_(False),
                URLRecord.password_hash.is_(None),
            ).first()
            if existing:
                resp = _to_shorten_response(existing)
                resp.created = False
                return resp
        short_code = None  # assigned after flush

    expires_at = _utcnow() + timedelta(days=days)
    password_hash = hash_password(password) if password else None

    record = URLRecord(
        long_url=long_url,
        expires_at=expires_at,
        starts_at=starts_at,
        short_code=custom_alias or str(uuid4()),
        one_time=one_time,
        password_hash=password_hash,
        user_id=user_id,
    )
    db.add(record)
    db.flush()

    if not custom_alias:
        short_code = codec.encode(record.id)
        record.short_code = short_code

    db.commit()
    db.refresh(record)

    if not one_time and not password_hash:
        cache.set(record.short_code, long_url)

    return _to_shorten_response(record)


# ── Resolve ──────────────────────────────────────────────────────────────────

class ResolveStatus(str, Enum):
    OK = "ok"
    NOT_FOUND = "not_found"
    EXPIRED = "expired"
    NOT_ACTIVE = "not_active"
    PASSWORD_REQUIRED = "password_required"


@dataclass
class ResolveResult:
    status: ResolveStatus
    long_url: Optional[str] = None
    record_id: Optional[int] = None


def resolve(db: Session, short_code: str) -> ResolveResult:
    record = db.query(URLRecord).filter(URLRecord.short_code == short_code).first()
    if record is None:
        return ResolveResult(ResolveStatus.NOT_FOUND)

    if _is_expired(record.expires_at):
        return ResolveResult(ResolveStatus.EXPIRED)

    if record.starts_at and not _is_expired(record.starts_at):
        return ResolveResult(ResolveStatus.NOT_ACTIVE)

    if record.password_hash:
        return ResolveResult(ResolveStatus.PASSWORD_REQUIRED, record_id=record.id)

    long_url = record.long_url

    if record.one_time:
        # Delete immediately — no caching
        db.delete(record)
        db.commit()
        return ResolveResult(ResolveStatus.OK, long_url=long_url)

    _increment(db, record.id)
    cache.set(short_code, long_url)
    return ResolveResult(ResolveStatus.OK, long_url=long_url, record_id=record.id)


def unlock(db: Session, short_code: str, password: str) -> ResolveResult:
    record = db.query(URLRecord).filter(URLRecord.short_code == short_code).first()
    if record is None:
        return ResolveResult(ResolveStatus.NOT_FOUND)
    if _is_expired(record.expires_at):
        return ResolveResult(ResolveStatus.EXPIRED)
    if not record.password_hash or not verify_password(password, record.password_hash):
        return ResolveResult(ResolveStatus.PASSWORD_REQUIRED)

    long_url = record.long_url
    if record.one_time:
        db.delete(record)
        db.commit()
    else:
        _increment(db, record.id)
        db.commit()
    return ResolveResult(ResolveStatus.OK, long_url=long_url, record_id=record.id)


# ── Click tracking ────────────────────────────────────────────────────────────

def _increment(db: Session, record_id: int) -> None:
    db.query(URLRecord).filter(URLRecord.id == record_id).update(
        {"click_count": URLRecord.click_count + 1, "last_accessed_at": _utcnow()}
    )
    db.commit()


def log_click_event(record_id: int, ip: str, ua_string: str, referrer: str) -> None:
    """Run in a BackgroundTask. Opens its own DB session."""
    try:
        from user_agents import parse as ua_parse
        import httpx

        ua = ua_parse(ua_string or "")
        browser = ua.browser.family or "Unknown"
        os_name = ua.os.family or "Unknown"
        device = "mobile" if ua.is_mobile else "tablet" if ua.is_tablet else "desktop"

        country = city = None
        skip_geo = ip in ("127.0.0.1", "::1", "testclient", "")
        if not skip_geo:
            try:
                with httpx.Client(timeout=2.0) as client:
                    r = client.get(f"{GEO_API_URL}{ip}?fields=country,city,status")
                    data = r.json()
                    if data.get("status") == "success":
                        country = data.get("country")
                        city = data.get("city")
            except Exception:
                pass

        db = SessionLocal()
        try:
            event = ClickEvent(
                url_record_id=record_id,
                country=country,
                city=city,
                browser=browser,
                os=os_name,
                device=device,
                referrer=referrer or None,
                ip_address=ip,
            )
            db.add(event)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass  # never let analytics failures surface to users


# ── Stats / Analytics ─────────────────────────────────────────────────────────

def stats(db: Session, short_code: str) -> Optional[StatsResponse]:
    record = db.query(URLRecord).filter(URLRecord.short_code == short_code).first()
    if record is None:
        return None
    return StatsResponse(
        short_code=record.short_code,
        short_url=f"{BASE_URL}/{record.short_code}",
        long_url=record.long_url,
        created_at=record.created_at,
        expires_at=record.expires_at,
        starts_at=record.starts_at,
        last_accessed_at=record.last_accessed_at,
        click_count=record.click_count,
        is_expired=_is_expired(record.expires_at),
        is_active=_is_active(record),
        one_time=record.one_time,
        has_password=bool(record.password_hash),
        owner_id=record.user_id,
    )


def analytics(db: Session, short_code: str) -> Optional[AnalyticsResponse]:
    record = db.query(URLRecord).filter(URLRecord.short_code == short_code).first()
    if record is None:
        return None

    events = (
        db.query(ClickEvent)
        .filter(ClickEvent.url_record_id == record.id)
        .order_by(ClickEvent.clicked_at.desc())
        .all()
    )

    def _count(field: str) -> dict:
        c = Counter(getattr(e, field) or "Unknown" for e in events)
        return dict(c.most_common())

    recent = [
        ClickEventOut(
            clicked_at=e.clicked_at,
            country=e.country,
            city=e.city,
            browser=e.browser,
            os=e.os,
            device=e.device,
            referrer=e.referrer,
        )
        for e in events[:20]
    ]

    return AnalyticsResponse(
        short_code=short_code,
        total_clicks=record.click_count,
        clicks_by_country=_count("country"),
        clicks_by_browser=_count("browser"),
        clicks_by_os=_count("os"),
        clicks_by_device=_count("device"),
        recent_clicks=recent,
    )


# ── Admin ─────────────────────────────────────────────────────────────────────

def purge_expired(db: Session) -> int:
    deleted = db.query(URLRecord).filter(URLRecord.expires_at < _utcnow()).delete()
    db.commit()
    return deleted


# ── User ops ──────────────────────────────────────────────────────────────────

def my_links(db: Session, user_id: int) -> List[StatsResponse]:
    records = db.query(URLRecord).filter(URLRecord.user_id == user_id).all()
    return [
        StatsResponse(
            short_code=r.short_code,
            short_url=f"{BASE_URL}/{r.short_code}",
            long_url=r.long_url,
            created_at=r.created_at,
            expires_at=r.expires_at,
            starts_at=r.starts_at,
            last_accessed_at=r.last_accessed_at,
            click_count=r.click_count,
            is_expired=_is_expired(r.expires_at),
            is_active=_is_active(r),
            one_time=r.one_time,
            has_password=bool(r.password_hash),
            owner_id=r.user_id,
        )
        for r in records
    ]


def delete_link(db: Session, short_code: str, user_id: int) -> bool:
    record = db.query(URLRecord).filter(
        URLRecord.short_code == short_code,
        URLRecord.user_id == user_id,
    ).first()
    if record is None:
        return False
    cache.delete(short_code)
    db.delete(record)
    db.commit()
    return True
