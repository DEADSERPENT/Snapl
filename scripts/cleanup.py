"""
Standalone cleanup script — run on a schedule (cron, Task Scheduler, etc.)
to purge expired URL records from the database.

Usage:
    python scripts/cleanup.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal, create_tables
from app.service import purge_expired


def main():
    create_tables()
    db = SessionLocal()
    try:
        count = purge_expired(db)
        print(f"Purged {count} expired records.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
