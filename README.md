# Snapl

A production-ready URL shortener built with FastAPI, PostgreSQL, and Redis. Ships with a full single-page frontend, JWT auth, geo analytics, QR codes, and a complete Docker Compose stack.

## Stack

- **Backend** — FastAPI, SQLAlchemy, PostgreSQL, Redis
- **Frontend** — Vanilla JS SPA (no build step)
- **Queue** — Celery + Celery Beat
- **Proxy** — Nginx
- **CI** — GitHub Actions

## Quickstart

**Docker (recommended)**

```bash
cp .env.example .env   # fill in JWT_SECRET and ADMIN_SECRET
docker compose up --build
```

Open `http://localhost:5600`.

**Local**

```bash
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://localhost:8000`.

## Docs

- [doc.md](doc.md) — API reference, configuration, architecture, edge cases, testing

## License

MIT
