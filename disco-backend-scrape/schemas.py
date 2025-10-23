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
