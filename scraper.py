import os, re, json
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin
import requests
from lxml import html as lh
from sqlalchemy.orm import Session
from models import ScrapeCache
from datetime import datetime, timedelta

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 DiscoBot/1.0"
TIMEOUT = float(os.getenv("SCRAPE_TIMEOUT_SECONDS", "7"))
TTL = int(os.getenv("SCRAPE_TTL_SECONDS", "600"))

def normalize_domain(domain: str) -> str:
    return (domain or "").lower().replace("www.", "")

def _extract_tokens(text: str, token_re: str) -> List[str]:
    import re
    tokens = re.findall(token_re, text.upper())
    uniq = []
    for t in tokens:
        tt = t.strip().upper()
        if tt and tt not in uniq:
            uniq.append(tt)
    return uniq

def _filter_tokens(tokens: List[str], stop: List[str]) -> List[str]:
    stopset = set(stop or [])
    return [t for t in tokens if t not in stopset]

def scrape_from_html(html: str, token_re: str, keywords: List[str], stop: List[str]) -> List[str]:
    try:
        root = lh.fromstring(html)
        texts = root.xpath("//text()")
        joined = "\n".join([t.strip() for t in texts if t and t.strip()])
        toks = _extract_tokens(joined, token_re)
        upper = joined.upper()
        near = []
        for kw in keywords:
            i = upper.find(kw.upper())
            while i >= 0:
                excerpt = upper[max(0, i-160): i+160]
                near.extend(_extract_tokens(excerpt, token_re))
                i = upper.find(kw.upper(), i+1)
        merged = list(dict.fromkeys(near + toks))
        return _filter_tokens(merged, stop)
    except Exception:
        return []

def fetch_and_scrape(domain: str, url: str, token_re: str, keywords: List[str], stop: List[str]) -> List[str]:
    try:
        headers = {"User-Agent": UA, "Accept": "text/html"}
        resp = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        if not (200 <= resp.status_code < 300):
            return []
        html = resp.text
        return scrape_from_html(html, token_re, keywords, stop)
    except Exception:
        return []

def cached_fetch(db: Session, domain: str, url: str, token_re: str, keywords: List[str], stop: List[str]) -> List[str]:
    now = datetime.utcnow()
    row = db.query(ScrapeCache).filter(ScrapeCache.domain==domain, ScrapeCache.url==url).first()
    if row and row.fetched_at and (now - row.fetched_at) < timedelta(seconds=TTL):
        try:
            return json.loads(row.codes_json) or []
        except Exception:
            pass
    codes = fetch_and_scrape(domain, url, token_re, keywords, stop)
    payload = json.dumps(codes[:50])
    if row:
        row.codes_json = payload
        row.fetched_at = now
    else:
        row = ScrapeCache(domain=domain, url=url, codes_json=payload, fetched_at=now)
        db.add(row)
    db.commit()
    return codes

def scrape_pipeline(
    db: Session,
    adapters: Optional[Dict],
    domain: str,
    url: Optional[str]=None,
    html: Optional[str]=None,
    limit: int=50,
    overrides: Optional[Dict[str, Any]] = None,
) -> List[str]:
    dom = normalize_domain(domain)
    overrides = overrides or {}
    platforms = (adapters or {}).get("platforms", {})
    platform_key = overrides.get("platform") or "generic"
    plat = platforms.get(platform_key) or platforms.get("generic", {})
    sconf = plat.get("scrape", {}) if isinstance(plat, dict) else {}
    domain_scrape = overrides.get("scrape") if isinstance(overrides.get("scrape"), dict) else {}
    token_re = domain_scrape.get("token_re") or sconf.get("token_re", r"[A-Z0-9][A-Z0-9\-]{4,14}")
    keywords = domain_scrape.get("keywords") or sconf.get("keywords", [])
    stop = domain_scrape.get("stop") or sconf.get("stop", [])

    if html:
        return scrape_from_html(html, token_re, keywords, stop)[:limit]

    roots = [f"https://{dom}"]
    urls = []
    if url:
        urls.append(url)
    paths = domain_scrape.get("paths") or sconf.get("paths", ["/", "/sale", "/offers", "/promo", "/promotions", "/discount", "/voucher", "/vouchers"])
    for base in roots:
        for p in paths:
            urls.append(urljoin(base, p))

    found: List[str] = []
    for u in urls[:6]:
        codes = cached_fetch(db, dom, u, token_re, keywords, stop)
        for c in codes:
            if c not in found:
                found.append(c)
        if len(found) >= limit:
            break
    return found[:limit]
