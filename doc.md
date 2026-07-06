# Snapl — Technical Documentation

## Architecture

```
Browser
  │
  ▼
Nginx  (port 5600 dev / 80 prod)
  │
  ▼
FastAPI  (uvicorn :8000, internal)
  ├── GET /          → serves SPA (index.html)
  ├── GET /{code}    → Redis cache → PostgreSQL → 302 redirect
  ├── POST /shorten  → PostgreSQL → cache write
  └── BackgroundTask → Celery worker (geo lookup, click event)
        └── Celery Beat (midnight purge of expired links)
```

**Short code generation** — Each row gets an auto-incremented `id` encoded in base62 (`0–9a–zA–Z`). 4 chars = 14 M URLs, 5 chars = 916 M. Collision is structurally impossible. Custom aliases bypass encoding entirely.

**Caching** — `GET /{code}` checks Redis (or an in-memory TTL dict when Redis is unavailable) before touching Postgres. One-time links and password-protected links are never cached.

**Analytics** — Geo lookup (ip-api.com) and user-agent parsing run in a `BackgroundTask` so the redirect response is never blocked.

---

## API Reference

Interactive docs available at `/docs` (Swagger UI) and `/redoc`.

### Auth

| Method | Path | Body | Auth |
|--------|------|------|------|
| POST | `/auth/register` | `{ email, password }` | — |
| POST | `/auth/login` | `{ email, password }` | — |
| POST | `/auth/refresh` | `{ refresh_token }` | — |
| GET | `/auth/me` | — | Required |
| POST | `/auth/api-key` | — | Required |

All authenticated endpoints accept either:
```
Authorization: Bearer <access_token>
X-API-Key: <api_key>
```

### Links

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/shorten` | Optional | Create a short link |
| POST | `/bulk` | Required | Create up to 500 links |
| GET | `/my-links` | Required | List your links |
| DELETE | `/my-links/{code}` | Required | Delete an owned link |
| GET | `/{code}` | — | Redirect or password form |
| POST | `/{code}/unlock` | — | Unlock password-protected link |
| GET | `/stats/{code}` | — | Link metadata and click count |
| GET | `/analytics/{code}` | Required (owner) | Geo + browser breakdown |
| GET | `/qr/{code}` | — | QR code PNG |

### Admin

| Method | Path | Auth |
|--------|------|------|
| POST | `/admin/purge` | `X-Admin-Secret` header |

```bash
curl -X POST http://localhost:5600/admin/purge \
     -H "X-Admin-Secret: <ADMIN_SECRET>"
```

Celery Beat runs this automatically at midnight UTC.

---

## Request & Response Schemas

### POST /shorten

```json
{
  "url": "https://example.com/path",
  "custom_alias": "my-link",
  "expiry_days": 7,
  "starts_at": "2025-08-01T00:00:00Z",
  "one_time": false,
  "password": "optional"
}
```

- `url` — required, must be `http` or `https`
- `custom_alias` — 2–32 chars, `[a-zA-Z0-9_-]` only
- `expiry_days` — defaults to `DEFAULT_EXPIRY_DAYS` (30)
- `starts_at` — link returns 404 until this timestamp
- `one_time` — record is deleted after the first visit
- `password` — link shows a password form before redirecting

**Response**

```json
{
  "short_url": "http://localhost:5600/my-link",
  "short_code": "my-link",
  "long_url": "https://example.com/path",
  "expires_at": "2025-07-13T00:00:00Z",
  "starts_at": null,
  "created": true,
  "one_time": false,
  "qr_url": "http://localhost:5600/qr/my-link"
}
```

`created: false` means the URL already existed and the existing record was returned (anonymous idempotency).

### GET /my-links

Returns an array of `StatsResponse`:

```json
[
  {
    "short_code": "abc123",
    "short_url": "http://localhost:5600/abc123",
    "long_url": "https://example.com",
    "created_at": "2025-07-06T10:00:00Z",
    "expires_at": "2025-08-05T10:00:00Z",
    "starts_at": null,
    "last_accessed_at": "2025-07-06T11:30:00Z",
    "click_count": 42,
    "is_expired": false,
    "is_active": true,
    "one_time": false,
    "has_password": false,
    "owner_id": 1
  }
]
```

### GET /analytics/{code}

Owner-only. Returns geo and device breakdown plus the 20 most recent click events.

```json
{
  "short_code": "abc123",
  "total_clicks": 42,
  "clicks_by_country": { "India": 18, "United States": 12 },
  "clicks_by_browser": { "Chrome": 30, "Safari": 8 },
  "clicks_by_os": { "Windows": 22, "macOS": 10 },
  "clicks_by_device": { "desktop": 35, "mobile": 7 },
  "recent_clicks": [
    {
      "clicked_at": "2025-07-06T11:30:00Z",
      "country": "India",
      "city": "Bengaluru",
      "browser": "Chrome",
      "os": "Windows",
      "device": "desktop",
      "referrer": "https://twitter.com"
    }
  ]
}
```

---

## Configuration

All settings are loaded from `.env` (copy `.env.example` to get started).

| Variable | Default | Description |
|---|---|---|
| `DB_USER` | `postgres` | PostgreSQL username |
| `DB_PASSWORD` | — | PostgreSQL password |
| `DB_NAME` | `snapl` | PostgreSQL database name |
| `DATABASE_URL` | — | Full SQLAlchemy connection string (overrides DB_* vars) |
| `REDIS_URL` | *(empty)* | Redis URL; leave blank to use in-memory cache |
| `BASE_URL` | `http://localhost:5600` | Prefix prepended to all generated short URLs |
| `DEFAULT_EXPIRY_DAYS` | `30` | Link lifetime when not specified by the caller |
| `CACHE_TTL_SECONDS` | `300` | How long redirect targets are cached |
| `RATE_LIMIT_PER_MINUTE` | `60` | Per-IP request cap (applied at the FastAPI layer) |
| `JWT_SECRET` | *(required)* | Signs JWTs — generate with `openssl rand -hex 32` |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_EXPIRY_MINUTES` | `30` | Access token lifetime |
| `ADMIN_SECRET` | *(required)* | Protects `POST /admin/purge` — `openssl rand -hex 16` |
| `GEO_API_URL` | `http://ip-api.com/json/` | Geolocation endpoint (swap for MaxMind in production) |

---

## Edge Cases

| Scenario | HTTP Response |
|---|---|
| Invalid or non-http(s) URL | 422 Unprocessable Entity |
| Custom alias already taken | 409 Conflict |
| Duplicate anonymous URL | 201 with existing record, `created: false` |
| Unknown short code | 404 Not Found |
| Expired link | 410 Gone |
| Link before `starts_at` | 404 Not Found |
| One-time link visited twice | 404 on second visit (record deleted after first) |
| Wrong unlock password | 401 Unauthorized |
| Analytics for another user's link | 403 Forbidden |
| Rate limit exceeded | 429 Too Many Requests |

---

## Running Tests

```bash
pytest tests/ -v
```

Uses SQLite in-process — no Postgres or Redis required. Covers:

- Registration, login, token refresh
- Anonymous and authenticated shortening
- Custom aliases, idempotency
- One-time links, password-protected links
- Link scheduling (`starts_at`), expiry
- Redirects, click counting
- QR code generation
- Bulk shortening
- User ownership (`/my-links`, delete)
- Admin purge

---

## Load Testing

```bash
# 1. Seed a URL, note the short_code, set it in scripts/load_test.py
# 2. Run:
locust -f scripts/load_test.py --host http://localhost:5600 \
       --headless -u 50 -r 10 --run-time 60s
```

Compare `CACHE_TTL_SECONDS=0` vs default `300` to measure the Redis cache benefit on redirect latency.

---

## Background Jobs

Both services start automatically inside Docker Compose. To run manually:

```bash
# Worker — handles async geo lookups and click event writes
celery -A app.tasks worker --loglevel=info --concurrency=2

# Beat — triggers the midnight expired-link purge
celery -A app.tasks beat --loglevel=info
```

`REDIS_URL` must be set for Celery to function.

---

## Database Schema

```
users
  id, email, hashed_password, api_key, created_at

urls
  id, short_code, long_url, created_at, expires_at, starts_at,
  click_count, last_accessed_at, one_time, password_hash, user_id → users.id

click_events
  id, url_record_id → urls.id, clicked_at,
  country, city, browser, os, device, referrer, ip_address
```

Tables are created automatically on first startup via `Base.metadata.create_all()`.
