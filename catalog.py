import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from models import RetailerProfile, RetailerInventory


def normalize_domain(domain: str) -> str:
    return (domain or "").strip().lower().replace("https://", "").replace("http://", "").replace("www.", "")


def _loads(text: Optional[str], fallback):
    if text is None:
        return fallback
    if isinstance(text, (dict, list)):
        return text
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return fallback


def _dumps(value, fallback=None) -> str:
    if fallback is None:
        if isinstance(value, list):
            fallback = []
        else:
            fallback = {}
    if value is None:
        value = fallback
    try:
        return json.dumps(value, sort_keys=True)
    except (TypeError, ValueError):
        return json.dumps(fallback, sort_keys=True)


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def upsert_retailer_profile(db: Session, payload: Dict[str, Any]) -> RetailerProfile:
    domains = payload.get("domains") or [payload.get("domain")]
    domains = [normalize_domain(d) for d in domains if d]
    if not domains:
        raise ValueError("retailer payload missing domain")
    canonical = domains[0]

    profile = (
        db.query(RetailerProfile)
        .filter(RetailerProfile.domain == canonical)
        .first()
    )
    if not profile:
        profile = RetailerProfile(domain=canonical, retailer_name=payload.get("name") or canonical)
        db.add(profile)

    profile.retailer_name = payload.get("name") or profile.retailer_name
    profile.active = bool(payload.get("active", True))

    selectors = payload.get("selectors") or {}
    heuristics = payload.get("heuristics") or {}
    metadata = payload.get("metadata") or {}
    metadata.setdefault("aliases", domains)
    metadata.setdefault("platform", payload.get("platform", "generic"))
    metadata.setdefault("checkout_hints", payload.get("checkoutHints") or [])
    metadata.setdefault("regions", payload.get("regions") or [])
    metadata.setdefault("scrape", payload.get("scrape") or {})

    profile.selectors = _dumps(selectors)
    profile.heuristics = _dumps(heuristics)
    profile.retailer_metadata = _dumps(metadata)
    profile.last_synced = datetime.utcnow()

    existing = {inv.code.upper(): inv for inv in profile.inventory}
    seen_codes = set()
    inventory_payload = payload.get("inventory") or []
    now = datetime.utcnow()

    for item in inventory_payload:
        code = str(item.get("code") or "").strip().upper()
        if not code:
            continue
        seen_codes.add(code)
        record = existing.get(code)
        tags = item.get("tags") or []
        attributes = item.get("metadata") or item.get("attributes") or {}
        source = item.get("source") or "catalog"
        expires = _coerce_datetime(item.get("expires_at") or item.get("expiresAt"))
        if record:
            record.source = source
            record.tags = _dumps(tags)
            record.attributes = _dumps(attributes)
            record.last_seen = now
            record.expires_at = expires
        else:
            db.add(
                RetailerInventory(
                    retailer=profile,
                    code=code,
                    source=source,
                    tags=_dumps(tags),
                    attributes=_dumps(attributes),
                    first_seen=now,
                    last_seen=now,
                    expires_at=expires,
                )
            )

    for code, record in list(existing.items()):
        if code not in seen_codes:
            db.delete(record)

    return profile


def ingest_catalog_entries(db: Session, entries: Iterable[Dict[str, Any]], drop_missing: bool = False) -> int:
    seen = set()
    count = 0
    for payload in entries:
        profile = upsert_retailer_profile(db, payload)
        seen.add(profile.domain)
        count += 1
        if count % 100 == 0:
            db.flush()
    db.commit()
    if drop_missing and seen:
        (
            db.query(RetailerProfile)
            .filter(~RetailerProfile.domain.in_(seen))
            .update({"active": False}, synchronize_session=False)
        )
        db.commit()
    return count


def list_supported_domains(db: Session) -> List[Dict[str, Any]]:
    rows = db.query(RetailerProfile).filter(RetailerProfile.active == True).all()
    result: List[Dict[str, Any]] = []
    for row in rows:
        metadata = _loads(row.retailer_metadata, {})
        entry = {
            "domain": row.domain,
            "name": row.retailer_name,
            "platform": metadata.get("platform", "generic"),
            "aliases": metadata.get("aliases", [row.domain]),
            "regions": metadata.get("regions", []),
            "checkout_hints": metadata.get("checkout_hints", []),
            "scrape": metadata.get("scrape", {}),
            "last_synced": row.last_synced,
        }
        entry["inventory_count"] = (
            db.query(RetailerInventory)
            .filter(RetailerInventory.retailer_id == row.id)
            .count()
        )
        result.append(entry)
    return result


def get_retailer_bundle(db: Session, domain: str) -> Optional[Dict[str, Any]]:
    dom = normalize_domain(domain)
    if not dom:
        return None
    profile = (
        db.query(RetailerProfile)
        .filter(RetailerProfile.domain == dom, RetailerProfile.active == True)
        .first()
    )
    if not profile:
        return None
    metadata = _loads(profile.retailer_metadata, {})
    selectors = _loads(profile.selectors, {})
    heuristics = _loads(profile.heuristics, {})
    inventory_rows = (
        db.query(RetailerInventory)
        .filter(RetailerInventory.retailer_id == profile.id)
        .order_by(RetailerInventory.last_seen.desc())
        .all()
    )
    inventory: List[Dict[str, Any]] = []
    for row in inventory_rows:
        inventory.append(
            {
                "code": row.code,
                "source": row.source or "catalog",
                "tags": _loads(row.tags, []),
                "attributes": _loads(row.attributes, {}),
                "first_seen": row.first_seen,
                "last_seen": row.last_seen,
                "expires_at": row.expires_at,
            }
        )
    return {
        "domain": profile.domain,
        "retailer": profile.retailer_name,
        "platform": metadata.get("platform", "generic"),
        "checkout_hints": metadata.get("checkout_hints", []),
        "selectors": selectors,
        "heuristics": heuristics,
        "scrape": metadata.get("scrape", {}),
        "regions": metadata.get("regions", []),
        "aliases": metadata.get("aliases", [profile.domain]),
        "inventory": inventory,
        "inventory_count": len(inventory),
        "last_synced": profile.last_synced,
    }


def get_retailer_overrides(db: Session, domain: str) -> Dict[str, Any]:
    bundle = get_retailer_bundle(db, domain)
    if not bundle:
        return {}
    return {
        "platform": bundle.get("platform", "generic"),
        "scrape": bundle.get("scrape", {}),
        "selectors": bundle.get("selectors", {}),
        "checkout_hints": bundle.get("checkout_hints", []),
    }


def get_retailer_inventory(db: Session, domain: str, limit: int = 50) -> List[Dict[str, Any]]:
    bundle = get_retailer_bundle(db, domain)
    if not bundle:
        return []
    inventory: List[Dict[str, Any]] = []
    for row in bundle.get("inventory", [])[:limit]:
        inventory.append(
            {
                "code": row.get("code"),
                "source": row.get("source", "catalog"),
                "metadata": {
                    "tags": row.get("tags", []),
                    "attributes": row.get("attributes", {}),
                    "first_seen": row.get("first_seen"),
                    "last_seen": row.get("last_seen"),
                    "expires_at": row.get("expires_at"),
                },
            }
        )
    return inventory


def build_adapter_snapshot(db: Session, base_adapters: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = {
        "platforms": base_adapters.get("platforms", {}),
        "retailers": [],
    }
    base_retailers = base_adapters.get("retailers") or []
    snapshot["retailers"].extend(base_retailers)
    for entry in list_supported_domains(db):
        snapshot["retailers"].append(
            {
                "name": entry["name"],
                "domains": entry.get("aliases") or [entry["domain"]],
                "platform": entry.get("platform", "generic"),
                "checkoutHints": entry.get("checkout_hints", []),
                "regions": entry.get("regions", []),
                "inventory": entry.get("inventory_count", 0),
                "lastSynced": entry.get("last_synced").isoformat() if entry.get("last_synced") else None,
                "scrape": entry.get("scrape", {}),
            }
        )
    return snapshot
