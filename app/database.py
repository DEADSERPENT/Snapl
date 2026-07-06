from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, func,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker, Session
from sqlalchemy import create_engine
from app.config import DATABASE_URL


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    api_key = Column(String(64), unique=True, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    urls = relationship("URLRecord", back_populates="owner")


class URLRecord(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    short_code = Column(String(32), unique=True, index=True, nullable=False)
    long_url = Column(String(2048), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    click_count = Column(Integer, default=0, nullable=False)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    one_time = Column(Boolean, default=False, nullable=False)
    password_hash = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    owner = relationship("User", back_populates="urls")
    clicks = relationship("ClickEvent", back_populates="url_record", cascade="all, delete-orphan")


class ClickEvent(Base):
    __tablename__ = "click_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url_record_id = Column(Integer, ForeignKey("urls.id"), nullable=False)
    clicked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    country = Column(String(64), nullable=True)
    city = Column(String(64), nullable=True)
    browser = Column(String(64), nullable=True)
    os = Column(String(64), nullable=True)
    device = Column(String(16), nullable=True)  # mobile / tablet / desktop
    referrer = Column(String(2048), nullable=True)
    ip_address = Column(String(45), nullable=True)

    url_record = relationship("URLRecord", back_populates="clicks")


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    Base.metadata.create_all(bind=engine)
