import os, json
from fastapi import FastAPI, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from db import Base, engine, get_db
from models import CodeSeed, CodeAttempt, ScrapeCache
from schemas import (HealthResponse, SuggestRequest, SuggestResponse, RankRequest, RankResponse, RankedCode,
                     SeedRequest, EventRequest, ScrapeRequest, ScrapeResponse, AdaptersResponse)
from ranking import rank_codes
from scraper import scrape_pipeline
from auth import require_api_key

load_dotenv()

app = FastAPI(title="Disco Backend (Scraping+Adapters)", version="3.0.0")

origins = os.getenv("ALLOWED_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if origins == "*" else [o.strip() for o in origins.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

with open(os.path.join(os.path.dirname(__file__), "adapters.json"), "r") as f:
    ADAPTERS = json.load(f)

@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(ok=True)

@app.get("/adapters", response_model=AdaptersResponse)
def get_adapters():
    return ADAPTERS

@app.post("/scrape", response_model=ScrapeResponse)
def scrape(req: ScrapeRequest, db: Session = Depends(get_db)):
    codes = scrape_pipeline(db, ADAPTERS, domain=req.domain, url=req.url, html=req.html, limit=req.limit)
    return ScrapeResponse(codes=codes)

@app.post("/suggest", response_model=SuggestResponse)
def suggest(req: SuggestRequest, db: Session = Depends(get_db)):
    domain = req.domain.lower().replace("www.", "")

    attempts = db.query(CodeAttempt)\
        .filter(CodeAttempt.domain == domain, CodeAttempt.success == True)\
        .order_by(CodeAttempt.created_at.desc())\
        .limit(req.limit).all()
    recent_success = [a.code for a in attempts]

    seed_rows = db.query(CodeSeed).filter(CodeSeed.domain == domain)\
        .order_by(CodeSeed.created_at.desc()).limit(req.limit).all()
    seeds = [r.code for r in seed_rows]

    scraped = scrape_pipeline(db, ADAPTERS, domain=domain, url=req.url, html=req.html, limit=req.limit)

    merged = []
    seen = set()
    for lst in (recent_success, scraped, seeds):
        for c in lst:
            cu = c.strip().upper()
            if cu and cu not in seen:
                merged.append(cu)
                seen.add(cu)
            if len(merged) >= req.limit:
                break
        if len(merged) >= req.limit:
            break
    return SuggestResponse(codes=merged[:req.limit])

@app.post("/rank", response_model=RankResponse)
def rank(req: RankRequest, db: Session = Depends(get_db)):
    domain = (req.domain or "").lower().replace("www.", "")
    codes = None
    if isinstance(req.context, dict):
        codes = req.context.get("codes")
    if not codes:
        return RankResponse(codes=[], metadata={"reason": "no codes provided"})
    ranked = rank_codes(db, domain, list(dict.fromkeys([str(c).strip().upper() for c in codes])))
    return RankResponse(
        codes=[RankedCode(code=c, score=float(round(s,4)), reasons=r) for (c,s,r) in ranked],
        metadata={"domain": domain, "count": len(ranked)}
    )

@app.post("/seed", dependencies=[Depends(require_api_key)])
def seed_codes(req: SeedRequest, db: Session = Depends(get_db)):
    domain = req.domain.lower().replace("www.", "")
    added, skipped = 0, 0
    for code in req.codes:
        cu = code.strip().upper()
        if not cu:
            continue
        exists = db.query(CodeSeed).filter(CodeSeed.domain == domain, CodeSeed.code == cu).first()
        if exists:
            skipped += 1
            continue
        db.add(CodeSeed(domain=domain, code=cu, source=req.source))
        added += 1
    db.commit()
    return {"ok": True, "added": added, "skipped": skipped}

@app.post("/event")
def log_event(req: EventRequest, db: Session = Depends(get_db), user_agent: str = Header(None)):
    domain = req.domain.lower().replace("www.", "")
    attempt = CodeAttempt(
        domain=domain, code=req.code.strip().upper(), success=bool(req.success),
        saved=float(req.saved or 0.0), before_total=req.before_total, after_total=req.after_total,
        user_agent=user_agent or ""
    )
    db.add(attempt)
    db.commit()
    return {"ok": True, "id": attempt.id}
