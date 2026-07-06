"""
Integration tests using an in-process SQLite DB (no Postgres needed to run tests).
FastAPI's TestClient exercises the full request/response cycle.
"""

from fastapi.testclient import TestClient

from app.database import URLRecord
from app.codec import encode
from app.main import app
from tests.conftest import TestingSession

client = TestClient(app, raise_server_exceptions=True)


# --- /shorten ---

def test_shorten_returns_short_url():
    res = client.post("/shorten", json={"url": "https://example.com/long/path"})
    assert res.status_code == 201
    data = res.json()
    assert "short_url" in data
    assert data["created"] is True


def test_shorten_same_url_twice_returns_existing():
    url = "https://example.com/duplicate"
    r1 = client.post("/shorten", json={"url": url})
    r2 = client.post("/shorten", json={"url": url})
    assert r1.json()["short_code"] == r2.json()["short_code"]
    assert r2.json()["created"] is False


def test_shorten_rejects_invalid_url():
    res = client.post("/shorten", json={"url": "not-a-url"})
    assert res.status_code == 422


def test_shorten_rejects_non_http_scheme():
    res = client.post("/shorten", json={"url": "ftp://example.com"})
    assert res.status_code == 422


# --- redirect ---

def test_redirect_follows_to_long_url():
    long = "https://example.com/destination"
    code = client.post("/shorten", json={"url": long}).json()["short_code"]
    res = client.get(f"/{code}", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == long


def test_redirect_unknown_code_returns_404():
    res = client.get("/zzz999", follow_redirects=False)
    assert res.status_code == 404


# --- /stats ---

def test_stats_increments_click_count():
    code = client.post("/shorten", json={"url": "https://example.com/clicks"}).json()["short_code"]
    client.get(f"/{code}", follow_redirects=False)
    client.get(f"/{code}", follow_redirects=False)
    stats = client.get(f"/stats/{code}").json()
    assert stats["click_count"] == 2


def test_stats_unknown_code_returns_404():
    res = client.get("/stats/doesnotexist")
    assert res.status_code == 404


# --- expiry ---

def test_expired_link_returns_410():
    from datetime import datetime, timezone
    db = TestingSession()
    expired_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    record = URLRecord(long_url="https://example.com/old", expires_at=expired_at, short_code="__exp__")
    db.add(record)
    db.flush()
    record.short_code = encode(record.id)
    db.commit()
    code = record.short_code
    db.close()

    res = client.get(f"/{code}", follow_redirects=False)
    assert res.status_code == 410


# --- purge ---

def test_purge_removes_expired_records():
    from datetime import datetime, timezone
    db = TestingSession()
    expired_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    record = URLRecord(long_url="https://example.com/purge-me", expires_at=expired_at, short_code="__prg__")
    db.add(record)
    db.flush()
    record.short_code = encode(record.id)
    db.commit()
    db.close()

    import os
    secret = os.getenv("ADMIN_SECRET", "test-admin-secret")
    res = client.post("/admin/purge", headers={"x-admin-secret": secret})
    assert res.status_code == 200
    assert res.json()["purged"] >= 1
