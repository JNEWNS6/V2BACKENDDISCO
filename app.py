import os, json, hashlib
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from db import Base, engine, get_db
from models import CodeSeed, CodeAttempt, ScrapeCache
from schemas import (HealthResponse, SuggestRequest, SuggestResponse, RankRequest, RankResponse, RankedCode,
                    SeedRequest, EventRequest, ScrapeRequest, ScrapeResponse, AdaptersResponse)
from ranking import rank_codes
from scraper import scrape_pipeline
from auth import require_api_key
from catalog import (
    build_adapter_snapshot,
    get_retailer_inventory,
    get_retailer_overrides,
    get_retailer_bundle,
    list_supported_domains,
)

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

RETENTION_DAYS = int(os.getenv("CODE_EVENT_RETENTION_DAYS", "180") or 0)
_last_prune = 0.0


def _normalize_domain(domain: str) -> str:
    return (domain or "").strip().lower().replace("http://", "").replace("https://", "").replace("www.", "")


def _round_currency(value):
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (ValueError, TypeError):
        return None


def _hash_anon(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def prune_old_attempts(db: Session):
    global _last_prune
    if RETENTION_DAYS <= 0:
        return
    now_ts = datetime.utcnow().timestamp()
    if now_ts - _last_prune < 3600:
        return
    cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    db.query(CodeAttempt).filter(CodeAttempt.created_at < cutoff).delete()
    db.commit()
    _last_prune = now_ts


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(ok=True)


@app.get("/adapters", response_model=AdaptersResponse)
def get_adapters(db: Session = Depends(get_db)):
    return build_adapter_snapshot(db, ADAPTERS)


@app.get("/catalog/coverage", response_model=CatalogCoverageResponse)
def catalog_coverage(db: Session = Depends(get_db)):
    entries = list_supported_domains(db)
    retailers = []
    for entry in entries:
        retailers.append({
            "domain": entry["domain"],
            "retailer": entry["name"],
            "platform": entry.get("platform", "generic"),
            "aliases": entry.get("aliases", []),
            "regions": entry.get("regions", []),
            "inventory": entry.get("inventory_count", 0),
            "last_synced": entry.get("last_synced").isoformat() if entry.get("last_synced") else None,
        })
    return CatalogCoverageResponse(
        total=len(retailers),
        generated_at=datetime.utcnow().isoformat(),
        retailers=retailers,
    )


@app.get("/catalog/{domain}", response_model=CatalogRetailerResponse)
def catalog_detail(domain: str, db: Session = Depends(get_db)):
    bundle = get_retailer_bundle(db, domain)
    if not bundle:
        raise HTTPException(status_code=404, detail="catalog entry not found")
    inventory = []
    for entry in bundle.get("inventory", []):
        inventory.append({
            "code": entry.get("code"),
            "source": entry.get("source"),
            "tags": entry.get("tags", []),
            "attributes": entry.get("attributes", {}),
            "first_seen": entry.get("first_seen").isoformat() if entry.get("first_seen") else None,
            "last_seen": entry.get("last_seen").isoformat() if entry.get("last_seen") else None,
            "expires_at": entry.get("expires_at").isoformat() if entry.get("expires_at") else None,
        })
    return CatalogRetailerResponse(
        domain=bundle.get("domain"),
        retailer=bundle.get("retailer"),
        platform=bundle.get("platform", "generic"),
        checkout_hints=bundle.get("checkout_hints", []),
        selectors=bundle.get("selectors", {}),
        heuristics=bundle.get("heuristics", {}),
        scrape=bundle.get("scrape", {}),
        regions=bundle.get("regions", []),
        aliases=bundle.get("aliases", []),
        inventory=inventory,
        inventory_count=bundle.get("inventory_count", 0),
        last_synced=bundle.get("last_synced").isoformat() if bundle.get("last_synced") else None,
    )



@app.post("/scrape", response_model=ScrapeResponse)
def scrape(req: ScrapeRequest, db: Session = Depends(get_db)):
    overrides = get_retailer_overrides(db, req.domain)
    codes = scrape_pipeline(db, ADAPTERS, domain=req.domain, url=req.url, html=req.html, limit=req.limit, overrides=overrides)
    return ScrapeResponse(codes=codes)


@app.post("/suggest", response_model=SuggestResponse)
def suggest(req: SuggestRequest, db: Session = Depends(get_db)):
    domain = _normalize_domain(req.domain)

    attempts = db.query(CodeAttempt)\
        .filter(CodeAttempt.domain == domain, CodeAttempt.success == True)\
        .order_by(CodeAttempt.created_at.desc())\
        .limit(req.limit).all()
    recent_success = [a.code for a in attempts]

    seed_rows = db.query(CodeSeed).filter(CodeSeed.domain == domain)\
        .order_by(CodeSeed.created_at.desc()).limit(req.limit).all()
    seeds = [r.code for r in seed_rows]

    overrides = get_retailer_overrides(db, domain)
    scraped = scrape_pipeline(db, ADAPTERS, domain=domain, url=req.url, html=req.html, limit=req.limit, overrides=overrides)
    catalog_inventory = [item.get("code") for item in get_retailer_inventory(db, domain, req.limit)]

    merged = []
    seen = set()
    for lst in (catalog_inventory, recent_success, scraped, seeds):
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
    if req.opt_out:
        return JSONResponse({"ok": False, "stored": False, "reason": "opt_out"}, status_code=202)

    domain = _normalize_domain(req.domain)
    if not domain:
        raise HTTPException(status_code=400, detail="domain required")

    code = (req.code or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="code required")

    before_total = _round_currency(req.before_total)
    after_total = _round_currency(req.after_total)
    saved = _round_currency(req.saved)
    if saved is None and before_total is not None and after_total is not None:
        saved = _round_currency(max(0.0, before_total - after_total))

    attempt = CodeAttempt(
        domain=domain,
        code=code,
        success=bool(req.success),
        saved=float(saved or 0.0),
        before_total=before_total,
        after_total=after_total,
        user_agent=(user_agent or "")[:255],
        anon_id=_hash_anon(req.anon_id),
    )
    db.add(attempt)
    db.commit()
    prune_old_attempts(db)
    return {"ok": True, "id": attempt.id}
