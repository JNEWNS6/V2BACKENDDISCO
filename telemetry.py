"""Outcome telemetry helpers for recording, pruning, and exporting promo attempts."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from models import CodeAttempt

RETENTION_DAYS = int(os.getenv("CODE_EVENT_RETENTION_DAYS", "180") or 0)


def normalize_code(code: Optional[str]) -> str:
    """Normalize a promo code for storage/analytics."""
    return (code or "").strip().upper()


def normalize_domain(domain: Optional[str]) -> str:
    return (
        (domain or "")
        .strip()
        .lower()
        .replace("http://", "")
        .replace("https://", "")
        .replace("www.", "")
    )


def round_currency(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def hash_anon_id(anon_id: Optional[str]) -> Optional[str]:
    if not anon_id:
        return None
    return hashlib.sha256(anon_id.strip().encode("utf-8")).hexdigest()


def compute_saved(before_total: Optional[float], after_total: Optional[float], saved: Optional[float]) -> float:
    before = round_currency(before_total)
    after = round_currency(after_total)
    explicit = round_currency(saved)
    if explicit is not None:
        return float(explicit)
    if before is None or after is None:
        return 0.0
    computed = max(0.0, before - after)
    return float(round_currency(computed) or 0.0)


def record_attempt(
    db: Session,
    *,
    domain: str,
    code: str,
    success: bool,
    before_total: Optional[float] = None,
    after_total: Optional[float] = None,
    saved: Optional[float] = None,
    anon_id: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> CodeAttempt:
    normalized_domain = normalize_domain(domain)
    attempt = CodeAttempt(
        domain=normalized_domain,
        code=normalize_code(code),
        success=bool(success),
        saved=compute_saved(before_total, after_total, saved),
        before_total=round_currency(before_total),
        after_total=round_currency(after_total),
        anon_id=hash_anon_id(anon_id),
        user_agent=(user_agent or "")[:255] if user_agent else None,
    )
    db.add(attempt)
    db.flush()
    prune_attempts(db)
    db.commit()
    return attempt


def prune_attempts(db: Session) -> int:
    if RETENTION_DAYS <= 0:
        return 0
    cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    return db.query(CodeAttempt).filter(CodeAttempt.created_at < cutoff).delete()


def recent_attempts(
    db: Session,
    *,
    domain: Optional[str] = None,
    days: int = 180,
    limit: Optional[int] = None,
) -> List[CodeAttempt]:
    query = db.query(CodeAttempt)
    if domain:
        normalized = normalize_domain(domain)
        query = query.filter(CodeAttempt.domain == normalized)
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(CodeAttempt.created_at >= cutoff)
    query = query.order_by(CodeAttempt.created_at.desc())
    if limit:
        query = query.limit(limit)
    return list(query.all())


def build_training_rows(
    db: Session,
    *,
    domain: Optional[str] = None,
    days: int = 180,
) -> List[Dict[str, Optional[float]]]:
    rows: List[Dict[str, Optional[float]]] = []
    for attempt in recent_attempts(db, domain=domain, days=days, limit=None):
        rows.append(
            {
                "id": attempt.id,
                "domain": attempt.domain,
                "code": attempt.code,
                "success": bool(attempt.success),
                "saved": float(attempt.saved or 0.0),
                "before_total": float(attempt.before_total) if attempt.before_total is not None else None,
                "after_total": float(attempt.after_total) if attempt.after_total is not None else None,
                "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
            }
        )
    return rows


def aggregate_success_metrics(
    db: Session,
    *,
    domain: str,
    days: int = 90,
) -> Dict[str, Dict[str, float]]:
    if not domain:
        return {}
    normalized = normalize_domain(domain)
    stats: Dict[str, Dict[str, float]] = {}
    cutoff = datetime.utcnow() - timedelta(days=days)
    attempts = (
        db.query(CodeAttempt)
        .filter(CodeAttempt.domain == normalized)
        .filter(CodeAttempt.created_at >= cutoff)
        .all()
    )
    for attempt in attempts:
        record = stats.setdefault(
            attempt.code,
            {"n": 0, "ok": 0, "avg_saved": 0.0, "last": 0.0},
        )
        record["n"] += 1
        if attempt.success or (attempt.saved or 0.0) > 0:
            record["ok"] += 1
        record["avg_saved"] = (
            (record["avg_saved"] * (record["n"] - 1) + (attempt.saved or 0.0)) / record["n"]
        )
        if attempt.created_at:
            record["last"] = max(record["last"], attempt.created_at.timestamp())
    return stats


def iter_training_batches(
    db: Session,
    *,
    batch_size: int = 1000,
    domain: Optional[str] = None,
    days: int = 365,
) -> Iterable[List[Dict[str, Optional[float]]]]:
    batch: List[Dict[str, Optional[float]]] = []
    for row in build_training_rows(db, domain=domain, days=days):
        batch.append(row)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch

