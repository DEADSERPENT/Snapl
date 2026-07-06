import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/snapl")
REDIS_URL = os.getenv("REDIS_URL", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
DEFAULT_EXPIRY_DAYS = int(os.getenv("DEFAULT_EXPIRY_DAYS", "30"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production-use-a-long-random-string")
if JWT_SECRET == "change-me-in-production-use-a-long-random-string":
    import warnings
    warnings.warn(
        "\n\n  *** SECURITY WARNING ***\n"
        "  JWT_SECRET is using the insecure default value.\n"
        "  Set JWT_SECRET to a secure random string before going to production.\n"
        "  Generate one with:  openssl rand -hex 32\n",
        stacklevel=2,
    )
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "30"))

# Free tier: ip-api.com — swap for MaxMind in production
GEO_API_URL = os.getenv("GEO_API_URL", "http://ip-api.com/json/")
