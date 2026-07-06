import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import BASE_URL
from app.database import create_tables
from app.routers import admin, auth, links

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title="Snapl",
    description=(
        "Production-grade URL shortener with JWT auth, custom aliases, "
        "QR codes, password-protected links, geo analytics, and bulk shortening."
    ),
    version="2.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "links", "description": "URL shortening, redirects, stats, QR codes"},
        {"name": "auth", "description": "Register, login, API keys"},
        {"name": "admin", "description": "Maintenance operations"},
    ],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[BASE_URL],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
# Link router last — its /{short_code} catch-all must not shadow the routes above
app.include_router(links.router)


_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@app.get("/", include_in_schema=False)
def root():
    with open(os.path.join(_STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
        return Response(content=f.read(), media_type="text/html")
