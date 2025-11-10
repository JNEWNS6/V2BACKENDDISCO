from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class HealthResponse(BaseModel):
    ok: bool

class SuggestRequest(BaseModel):
    domain: str = Field(..., examples=["asos.com"])
    url: Optional[str] = None
    html: Optional[str] = None
    limit: int = 25

class SuggestResponse(BaseModel):
    codes: List[str]

class RankRequest(BaseModel):
    domain: str
    context: Dict[str, Any]

class RankedCode(BaseModel):
    code: str
    score: float
    reasons: Dict[str, Any] = {}

class RankResponse(BaseModel):
    codes: List[RankedCode]
    metadata: Dict[str, Any] = {}

class SeedRequest(BaseModel):
    domain: str
    codes: List[str]
    source: str = "seed"

class EventRequest(BaseModel):
    domain: str
    code: str
    success: bool
    saved: float = 0.0
    before_total: Optional[float] = None
    after_total: Optional[float] = None
    anon_id: Optional[str] = None
    opt_out: Optional[bool] = False

class ScrapeRequest(BaseModel):
    domain: str
    url: Optional[str] = None
    html: Optional[str] = None
    limit: int = 50

class ScrapeResponse(BaseModel):
    codes: List[str]

class AdaptersResponse(BaseModel):
    platforms: Dict[str, Any]
    retailers: List[Dict[str, Any]]


class CatalogRetailerSummary(BaseModel):
    domain: str
    retailer: str
    platform: str
    aliases: List[str] = []
    regions: List[str] = []
    inventory: int = 0
    last_synced: Optional[str] = None


class CatalogInventoryEntry(BaseModel):
    code: str
    source: Optional[str] = None
    tags: List[str] = []
    attributes: Dict[str, Any] = {}
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    expires_at: Optional[str] = None


class CatalogRetailerResponse(BaseModel):
    domain: str
    retailer: str
    platform: str
    checkout_hints: List[str] = []
    selectors: Dict[str, Any] = {}
    heuristics: Dict[str, Any] = {}
    scrape: Dict[str, Any] = {}
    regions: List[str] = []
    aliases: List[str] = []
    inventory: List[CatalogInventoryEntry] = []
    inventory_count: int = 0
    last_synced: Optional[str] = None


class CatalogCoverageResponse(BaseModel):
    total: int
    generated_at: str
    retailers: List[CatalogRetailerSummary]
