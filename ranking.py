from datetime import datetime
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from models import CodeSeed
from telemetry import aggregate_success_metrics

def _domain_key(domain: str) -> str:
    return (domain or "").lower().replace("www.", "")

def _success_stats(db: Session, domain: str) -> Dict[str, Dict[str, float]]:
    return aggregate_success_metrics(db, domain=_domain_key(domain))

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

        # project likely savings using the learned signals we have on hand
        base_saved = st["avg_saved"] or 0.0
        velocity = (recency_boost * 0.6) + (success_rate * 0.4)
        predicted_savings = base_saved * (0.55 + 0.45 * success_rate) + (saved_boost * 8.0)
        predicted_savings += velocity * 3.0
        predicted_savings = max(predicted_savings, 0.0)

        # convert to a soft probability to express confidence to the client
        confidence = min(0.98, 0.35 + 0.4 * success_rate + 0.15 * recency_boost + 0.1 * prior)

        if predicted_savings >= 25:
            best_total = 150
        elif predicted_savings >= 15:
            best_total = 90
        elif predicted_savings >= 10:
            best_total = 60
        elif predicted_savings >= 5:
            best_total = 40
        else:
            best_total = 25

        ranked.append((c, score, {
            "success_rate": round(success_rate,3),
            "recency_boost": round(recency_boost,3),
            "avg_saved": round(base_saved,2),
            "prior": prior,
            "shape": shape,
            "predicted_savings": round(predicted_savings,2),
            "confidence": round(confidence,3),
            "best_for_total": best_total,
            "signals": {
                "trials": n,
                "recent_successes": ok,
            }
        }))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked
