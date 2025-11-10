#!/usr/bin/env python3
import argparse
import json
import os
import sys
from typing import Iterable, Dict, Any, List

import requests
from sqlalchemy.orm import Session

from db import SessionLocal
from catalog import ingest_catalog_entries, normalize_domain
from models import RetailerProfile


def _read_manifest(path: str) -> List[Dict[str, Any]]:
    if path.startswith("http://") or path.startswith("https://"):
        timeout = float(os.getenv("RETAILER_CATALOG_HTTP_TIMEOUT", "60"))
        resp = requests.get(path, timeout=timeout)
        resp.raise_for_status()
        content = resp.text
    else:
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        entries: List[Dict[str, Any]] = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))
        return entries
    if isinstance(data, dict) and "retailers" in data:
        items = data.get("retailers") or []
        if isinstance(items, dict):
            return list(items.values())
        return list(items)
    if isinstance(data, list):
        return data
    raise ValueError("Unsupported manifest format")


def _batched(iterable: Iterable[Dict[str, Any]], size: int) -> Iterable[List[Dict[str, Any]]]:
    batch: List[Dict[str, Any]] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _deactivate_missing(session: Session, keep_domains: Iterable[str]) -> None:
    keep = {normalize_domain(domain) for domain in keep_domains if domain}
    if not keep:
        return
    (
        session.query(RetailerProfile)
        .filter(~RetailerProfile.domain.in_(keep))
        .update({"active": False}, synchronize_session=False)
    )


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync retailer catalog into the Disco backend database")
    parser.add_argument("manifest", help="Path or URL to the retailer manifest (JSON or NDJSON)")
    parser.add_argument("--drop-missing", action="store_true", help="Deactivate retailers not present in the manifest")
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("RETAILER_CATALOG_BATCH", "250")), help="Number of retailers to ingest per batch commit")
    args = parser.parse_args(argv)

    entries = _read_manifest(args.manifest)
    if not entries:
        print("No retailers discovered in manifest", file=sys.stderr)
        return 1

    session: Session = SessionLocal()
    total = 0
    try:
        for batch in _batched(entries, max(1, args.batch_size)):
            total += ingest_catalog_entries(session, batch, drop_missing=False)
        if args.drop_missing:
            _deactivate_missing(session, (payload.get("domain") for payload in entries))
        session.commit()
    finally:
        session.close()

    print(f"Ingested {total} retailers from manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
