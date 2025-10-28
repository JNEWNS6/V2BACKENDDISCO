from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, UniqueConstraint, Index, Text
from datetime import datetime
from db import Base

class CodeSeed(Base):
    __tablename__ = "code_seeds"
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, index=True)
    code = Column(String, index=True)
    source = Column(String, default="seed")
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("domain", "code", name="uq_seed_domain_code"),)

class CodeAttempt(Base):
    __tablename__ = "code_attempts"
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, index=True)
    code = Column(String, index=True)
    saved = Column(Float, default=0.0)
    success = Column(Boolean, default=False)
    before_total = Column(Float, nullable=True)
    after_total = Column(Float, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (Index("ix_attempt_domain_code_time", "domain", "code", "created_at"),)

class ScrapeCache(Base):
    __tablename__ = "scrape_cache"
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, index=True)
    url = Column(String, index=True)
    codes_json = Column(Text)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("domain", "url", name="uq_scrape_domain_url"),)
