from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, UniqueConstraint, Index, Text, ForeignKey
from sqlalchemy.orm import relationship
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
    anon_id = Column(String, nullable=True)
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


class RetailerProfile(Base):
    __tablename__ = "retailer_profiles"
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, unique=True, index=True, nullable=False)
    retailer_name = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    selectors = Column(Text, default="{}")
    heuristics = Column(Text, default="{}")
    retailer_metadata = Column("metadata", Text, default="{}")
    last_synced = Column(DateTime, nullable=True)
    inventory = relationship("RetailerInventory", back_populates="retailer", cascade="all, delete-orphan")


class RetailerInventory(Base):
    __tablename__ = "retailer_inventory"
    id = Column(Integer, primary_key=True, index=True)
    retailer_id = Column(Integer, ForeignKey("retailer_profiles.id", ondelete="CASCADE"), index=True, nullable=False)
    code = Column(String, nullable=False)
    source = Column(String, nullable=True)
    tags = Column(Text, default="[]")
    attributes = Column(Text, default="{}")
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    retailer = relationship("RetailerProfile", back_populates="inventory")
    __table_args__ = (
        UniqueConstraint("retailer_id", "code", name="uq_inventory_retailer_code"),
        Index("ix_inventory_retailer_last_seen", "retailer_id", "last_seen"),
    )
