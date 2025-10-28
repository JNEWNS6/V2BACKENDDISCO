from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from models import CodeAttempt, CodeSeed

def _domain_key(domain: str) -> str:
    return (domain or "").lower().replace("www.", "")

def _success_stats(db: Session, domain: str) -> Dict[str, Dict[str, float]]:
    stats: Dict[str, Dict[str, float]] = {}
    cutoff_90 = datetime.utcnow() - timedelta(days=90)
    rows = db.query(CodeAttempt).filter(CodeAttempt.domain == _domain_key(domain),
                                        CodeAttempt.created_at >= cutoff_90).all()
    for r in rows:
        s = stats.setdefault(r.code, {"n":0,"ok":0,"avg_saved":0.0,"last":0.0})
        s["n"] += 1
        if r.success or (r.saved or 0) > 0:
            s["ok"] += 1
        s["avg_saved"] = ((s["avg_saved"] * (s["n"]-1)) + (r.saved or 0)) / s["n"]
        s["last"] = max(s["last"], r.created_at.timestamp())
    return stats

def rank_codes(db: Session, domain: str, candidates: List[str]) -> List[Tuple[str, float, Dict]]:
    dom = _domain_key(domain)
    stats = _success_stats(db, dom)
    seed_counts: Dict[str, int] = {}
    for s in db.query(CodeSeed).filter(CodeSeed.domain == dom).all():
        seed_counts[s.code] = seed_counts.get(s.code, 0) + 1

    ranked = []
    now_ts = datetime.utcnow().timestamp()
    for code in candidates:
        c = code.strip().upper()
        if not c: 
            continue
        st = stats.get(c, {"n":0,"ok":0,"avg_saved":0.0,"last":0.0})
        n, ok = st["n"], st["ok"]
        success_rate = (ok / n) if n else 0.0
        recency_boost = max(0.0, 1.0 - min(1.0, (now_ts - st["last"]) / (60*60*24*30))) if st["last"] else 0.0
        saved_boost = min(1.0, (st["avg_saved"] or 0.0) / 20.0)
        prior = min(1.0, seed_counts.get(c, 0) / 5.0)
        shape = 0.0
        if 5 <= len(c) <= 12: shape += 0.2
        if any(ch.isdigit() for ch in c): shape += 0.1
        if "-" in c: shape += 0.05

        score = 0.45*success_rate + 0.2*recency_boost + 0.2*saved_boost + 0.1*prior + 0.05*shape
        ranked.append((c, score, {
            "success_rate": round(success_rate,3),
            "recency_boost": round(recency_boost,3),
            "avg_saved": round(st["avg_saved"],2),
            "prior": prior,
            "shape": shape
        }))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked
