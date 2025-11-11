"""Export sanitized promo outcome telemetry for offline ranking/training jobs."""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import SessionLocal
from telemetry import build_training_rows


def _write_csv(rows: List[dict]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)


def _write_json(rows: List[dict]) -> None:
    json.dump(rows, sys.stdout, indent=2, sort_keys=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export recent checkout telemetry for ML pipelines."
    )
    parser.add_argument("--domain", help="Restrict export to a single domain", default=None)
    parser.add_argument(
        "--days",
        type=int,
        default=180,
        help="How many days of telemetry to include (default: 180)",
    )
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="Output format (default: json)",
    )
    args = parser.parse_args()

    session = SessionLocal()
    try:
        rows = build_training_rows(session, domain=args.domain, days=args.days)
    finally:
        session.close()

    if args.format == "csv":
        _write_csv(rows)
    else:
        _write_json(rows)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
