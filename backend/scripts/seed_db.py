"""Run database seed from CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.bootstrap import setup_paths

setup_paths()

from app.db.session import SessionLocal
from app.services.seed_service import seed_from_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed debating database from JSON files")
    parser.add_argument("--force", action="store_true", help="Overwrite existing rows")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        counts = seed_from_files(db, force=args.force)
        print(f"Seeded: {counts}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
