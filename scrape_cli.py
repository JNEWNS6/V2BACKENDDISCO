#!/usr/bin/env python3
import sys, json, os, pathlib
from typing import Any, List
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from db import get_db
from ranking import rank_codes
from scraper import scrape_pipeline
from schemas import ScrapeRequest
from catalog import build_adapter_snapshot, get_retailer_overrides
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin

load_dotenv()

def _allowed(domain: str, user_agent: str = 'DiscoBot') -> bool:
    try:
        rp = RobotFileParser()
        rp.set_url(urljoin(f'https://{domain}', '/robots.txt'))
        rp.read()
        return rp.can_fetch(user_agent, '/')
    except Exception:
        return False

def read_json():
    data = sys.stdin.read().strip()
    return json.loads(data) if data else {}

def main():
    if len(sys.argv) < 2:
        print("Usage: python scrape_cli.py <op> (codes|rank)", file=sys.stderr)
        sys.exit(2)
    op = sys.argv[1]
    payload = read_json()

    # Load adapters if present
    ADAPTERS = None
    try:
        base_path = pathlib.Path('adapters.json')
        if base_path.exists():
            ADAPTERS = json.loads(base_path.read_text())
    except Exception:
        ADAPTERS = None

    allowlist = [s.strip().lower() for s in (os.getenv('ALLOWLIST_DOMAINS','').split(',')) if s.strip()]
    if op in ('codes','rank'):
        dom = (payload.get('domain') or '').lower().replace('www.','')
        if allowlist and dom not in allowlist:
            print(json.dumps({'error': f'domain not allowlisted: {dom}'}))
            sys.exit(1)
        if not _allowed(dom):
            print(json.dumps({'error': f'robots.txt disallows scraping for {dom}'}))
            sys.exit(1)

    db_gen = get_db(); db: Session = next(db_gen)
    try:
        adapters_snapshot = build_adapter_snapshot(db, ADAPTERS or {"platforms": {}, "retailers": []})

        if op == 'codes':
            domain = (payload.get('domain') or '')
            url = payload.get('url')
            html = payload.get('html')
            limit = int(payload.get('limit') or 50)
            overrides = get_retailer_overrides(db, domain)
            codes: List[str] = scrape_pipeline(
                db,
                adapters_snapshot,
                domain=domain,
                url=url,
                html=html,
                limit=limit,
                overrides=overrides,
            )
            print(json.dumps({'codes': codes})); sys.exit(0)
        elif op == 'rank':
            domain = (payload.get('domain') or '')
            candidates = payload.get('candidates') or []
            ranked = rank_codes(db, domain, candidates)
            resp = [{'code': r[0], 'score': float(r[1]), 'meta': r[2]} for r in ranked]
            print(json.dumps({'ranked': resp})); sys.exit(0)
        else:
            print(json.dumps({'error': 'unknown op'})); sys.exit(2)
    finally:
        try: next(db_gen)
        except StopIteration: pass

if __name__ == '__main__':
    main()
