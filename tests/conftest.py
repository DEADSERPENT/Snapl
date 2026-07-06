"""Shared test infrastructure — SQLite DB + dependency override for all tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite:///./test_snapl.db"

engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def fresh_db():
    from app.cache import cache
    Base.metadata.create_all(bind=engine)
    cache.clear()
    yield
    Base.metadata.drop_all(bind=engine)
    cache.clear()
