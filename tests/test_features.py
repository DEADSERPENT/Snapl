"""
Tests for: auth, custom alias, one-time links, QR codes,
password-protected links, geo analytics schema, bulk shortening,
link scheduling, and user-owned links.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=True)


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_register_and_login():
    r = client.post("/auth/register", json={"email": "u@test.com", "password": "secret123"})
    assert r.status_code == 201
    assert r.json()["email"] == "u@test.com"

    r2 = client.post("/auth/login", json={"email": "u@test.com", "password": "secret123"})
    assert r2.status_code == 200
    assert "access_token" in r2.json()
    assert "refresh_token" in r2.json()


def test_duplicate_email_is_rejected():
    client.post("/auth/register", json={"email": "dup@test.com", "password": "secret123"})
    r = client.post("/auth/register", json={"email": "dup@test.com", "password": "other1234"})
    assert r.status_code == 409


def test_wrong_password_rejected():
    client.post("/auth/register", json={"email": "x@test.com", "password": "correct99"})
    r = client.post("/auth/login", json={"email": "x@test.com", "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_auth():
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_returns_user():
    client.post("/auth/register", json={"email": "me@test.com", "password": "pass1234"})
    token = client.post("/auth/login", json={"email": "me@test.com", "password": "pass1234"}).json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "me@test.com"


def test_api_key_rotation():
    client.post("/auth/register", json={"email": "k@test.com", "password": "keykey12"})
    token = client.post("/auth/login", json={"email": "k@test.com", "password": "keykey12"}).json()["access_token"]
    r = client.post("/auth/api-key", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "api_key" in r.json()


def test_api_key_auth():
    client.post("/auth/register", json={"email": "ak@test.com", "password": "apikey12"})
    token = client.post("/auth/login", json={"email": "ak@test.com", "password": "apikey12"}).json()["access_token"]
    api_key = client.post("/auth/api-key", headers={"Authorization": f"Bearer {token}"}).json()["api_key"]
    r = client.get("/auth/me", headers={"X-API-Key": api_key})
    assert r.status_code == 200


def test_refresh_token():
    client.post("/auth/register", json={"email": "rf@test.com", "password": "refresh1"})
    tokens = client.post("/auth/login", json={"email": "rf@test.com", "password": "refresh1"}).json()
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert "access_token" in r.json()


# ── Custom alias ──────────────────────────────────────────────────────────────

def test_custom_alias_is_used():
    r = client.post("/shorten", json={"url": "https://example.com/custom", "custom_alias": "mylink"})
    assert r.status_code == 201
    assert r.json()["short_code"] == "mylink"


def test_custom_alias_conflict_returns_409():
    client.post("/shorten", json={"url": "https://example.com/a", "custom_alias": "taken"})
    r = client.post("/shorten", json={"url": "https://example.com/b", "custom_alias": "taken"})
    assert r.status_code == 409


def test_alias_invalid_chars_rejected():
    r = client.post("/shorten", json={"url": "https://example.com/", "custom_alias": "bad alias!"})
    assert r.status_code == 422


def test_alias_too_short_rejected():
    r = client.post("/shorten", json={"url": "https://example.com/", "custom_alias": "x"})
    assert r.status_code == 422


# ── One-time links ────────────────────────────────────────────────────────────

def test_one_time_link_works_once():
    code = client.post("/shorten", json={"url": "https://example.com/ot", "one_time": True}).json()["short_code"]
    r1 = client.get(f"/{code}", follow_redirects=False)
    assert r1.status_code == 302
    r2 = client.get(f"/{code}", follow_redirects=False)
    assert r2.status_code == 404


# ── QR code ───────────────────────────────────────────────────────────────────

def test_qr_returns_png():
    code = client.post("/shorten", json={"url": "https://example.com/qr"}).json()["short_code"]
    r = client.get(f"/qr/{code}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:4] == b"\x89PNG"


def test_qr_url_in_shorten_response():
    data = client.post("/shorten", json={"url": "https://example.com/qr2"}).json()
    assert "qr_url" in data
    assert "/qr/" in data["qr_url"]


def test_qr_unknown_code_404():
    r = client.get("/qr/doesnotexist")
    assert r.status_code == 404


# ── Password-protected links ───────────────────────────────────────────────────

def test_password_link_shows_form():
    code = client.post("/shorten", json={"url": "https://example.com/secret", "password": "hunter2"}).json()["short_code"]
    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 200
    assert "password" in r.text.lower()


def test_password_unlock_wrong_rejected():
    code = client.post("/shorten", json={"url": "https://example.com/secret2", "password": "correct"}).json()["short_code"]
    r = client.post(f"/{code}/unlock", json={"password": "wrong"})
    assert r.status_code == 401


def test_password_unlock_correct_redirects():
    code = client.post("/shorten", json={"url": "https://example.com/secret3", "password": "openme"}).json()["short_code"]
    r = client.post(f"/{code}/unlock", json={"password": "openme"}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://example.com/secret3"


# ── Link scheduling ───────────────────────────────────────────────────────────

def test_future_starts_at_returns_404():
    from datetime import datetime, timedelta, timezone
    future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    code = client.post("/shorten", json={"url": "https://example.com/future", "starts_at": future}).json()["short_code"]
    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 404


def test_past_starts_at_redirects():
    from datetime import datetime, timedelta, timezone
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    code = client.post("/shorten", json={"url": "https://example.com/past", "starts_at": past}).json()["short_code"]
    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 302


# ── Bulk shortening ───────────────────────────────────────────────────────────

def _auth_headers():
    client.post("/auth/register", json={"email": "bulk@test.com", "password": "bulk1234"})
    token = client.post("/auth/login", json={"email": "bulk@test.com", "password": "bulk1234"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_bulk_shorten():
    headers = _auth_headers()
    payload = {"urls": [
        {"url": "https://example.com/1"},
        {"url": "https://example.com/2"},
        {"url": "https://example.com/3"},
    ]}
    r = client.post("/bulk", json=payload, headers=headers)
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 3
    assert all("short_url" in item for item in results)


def test_bulk_requires_auth():
    r = client.post("/bulk", json={"urls": [{"url": "https://example.com"}]})
    assert r.status_code == 401


# ── My links ──────────────────────────────────────────────────────────────────

def test_my_links_returns_owned_links():
    client.post("/auth/register", json={"email": "ml@test.com", "password": "mylink12"})
    token = client.post("/auth/login", json={"email": "ml@test.com", "password": "mylink12"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/shorten", json={"url": "https://example.com/owned"}, headers=headers)
    r = client.get("/my-links", headers=headers)
    assert r.status_code == 200
    links = r.json()
    assert len(links) == 1
    assert links[0]["long_url"] == "https://example.com/owned"


def test_delete_owned_link():
    client.post("/auth/register", json={"email": "del@test.com", "password": "delete12"})
    token = client.post("/auth/login", json={"email": "del@test.com", "password": "delete12"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    code = client.post("/shorten", json={"url": "https://example.com/todel"}, headers=headers).json()["short_code"]
    r = client.delete(f"/my-links/{code}", headers=headers)
    assert r.status_code == 204
    assert client.get(f"/{code}", follow_redirects=False).status_code == 404


def test_cannot_delete_others_link():
    client.post("/auth/register", json={"email": "a@test.com", "password": "aaaaaa12"})
    token_a = client.post("/auth/login", json={"email": "a@test.com", "password": "aaaaaa12"}).json()["access_token"]
    code = client.post(
        "/shorten",
        json={"url": "https://example.com/a-link"},
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()["short_code"]

    client.post("/auth/register", json={"email": "b@test.com", "password": "bbbbbb12"})
    token_b = client.post("/auth/login", json={"email": "b@test.com", "password": "bbbbbb12"}).json()["access_token"]
    r = client.delete(f"/my-links/{code}", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 404


# ── Stats extended fields ─────────────────────────────────────────────────────

def test_stats_has_new_fields():
    code = client.post("/shorten", json={"url": "https://example.com/stat"}).json()["short_code"]
    data = client.get(f"/stats/{code}").json()
    assert "is_active" in data
    assert "has_password" in data
    assert "one_time" in data
    assert "starts_at" in data
