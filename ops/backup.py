#!/usr/bin/env python3
"""Database backup and maintenance for Lighthouse Analytics."""

import shutil
import sqlite3
import gzip
from datetime import datetime
from pathlib import Path

OPS_DIR = Path(__file__).parent
DATA_DIR = Path(__file__).parent.parent / "saas" / "data"
BACKUP_DIR = OPS_DIR / "data" / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "lighthouse.db"
MAX_BACKUPS = 30  # Keep last 30 backups


def backup_database() -> str:
    """Create a compressed backup of the database."""
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return ""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"lighthouse_{timestamp}.db.gz"

    # Read and compress
    with open(DB_PATH, "rb") as src:
        with gzip.open(backup_path, "wb") as dst:
            dst.write(src.read())

    print(f"✅ Backup created: {backup_path.name} ({backup_path.stat().st_size:,} bytes)")

    # Rotate old backups
    _rotate_backups()

    return str(backup_path)


def _rotate_backups():
    """Remove old backups beyond MAX_BACKUPS."""
    backups = sorted(BACKUP_DIR.glob("lighthouse_*.db.gz"))
    if len(backups) > MAX_BACKUPS:
        for old in backups[:-MAX_BACKUPS]:
            old.unlink()
            print(f"  🗑️  Removed old backup: {old.name}")


def restore_database(backup_path: str) -> bool:
    """Restore database from a backup."""
    backup_file = Path(backup_path)
    if not backup_file.exists():
        print(f"❌ Backup not found: {backup_path}")
        return False

    # Backup current DB first (safety)
    if DB_PATH.exists():
        safety = BACKUP_DIR / f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db.gz"
        with open(DB_PATH, "rb") as src:
            with gzip.open(safety, "wb") as dst:
                dst.write(src.read())
        print(f"📦 Pre-restore safety backup: {safety.name}")

    # Restore
    with gzip.open(backup_file, "rb") as src:
        with open(DB_PATH, "wb") as dst:
            dst.write(src.read())

    print(f"✅ Database restored from: {backup_file.name}")
    return True


def check_database_integrity() -> bool:
    """Run integrity check on the database."""
    if not DB_PATH.exists():
        print("❌ No database to check")
        return False

    conn = sqlite3.connect(str(DB_PATH))
    try:
        result = conn.execute("PRAGMA integrity_check;").fetchone()
        if result[0] == "ok":
            print("✅ Database integrity: OK")
            return True
        else:
            print(f"❌ Database integrity: {result[0]}")
            return False
    except Exception as e:
        print(f"❌ Integrity check failed: {e}")
        return False
    finally:
        conn.close()


def vacuum_database():
    """VACUUM the database to reclaim space."""
    if not DB_PATH.exists():
        return
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("VACUUM;")
    conn.close()
    size_mb = DB_PATH.stat().st_size / (1024 * 1024)
    print(f"✅ Database vacuumed. Size: {size_mb:.1f} MB")


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "backup"

    if cmd == "backup":
        backup_database()
    elif cmd == "restore":
        if len(sys.argv) < 3:
            print("Usage: backup.py restore <backup_path>")
            sys.exit(1)
        restore_database(sys.argv[2])
    elif cmd == "check":
        check_database_integrity()
    elif cmd == "vacuum":
        vacuum_database()
    elif cmd == "full":
        check_database_integrity()
        backup_database()
        vacuum_database()
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: backup, restore, check, vacuum, full")
