"""
SQLite Backup with rotation.
Copies the unified database to backups/ with a timestamped name,
keeps the newest N (default 7). Safe to run while services are up:
uses SQLite's online backup API rather than raw file copy.
"""

import argparse
import os
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "backups"))
DEFAULT_KEEP = 7


def _resolve_backup_dir() -> Path:
    """Use BACKUP_DIR when writable; otherwise fall back to the temp dir."""
    global BACKUP_DIR
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        BACKUP_DIR = Path(tempfile.gettempdir()) / "pubg_backups"
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[backup] falling back to {BACKUP_DIR}")
    return BACKUP_DIR


def backup(db_path: Path, keep: int = DEFAULT_KEEP) -> Path:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    backup_dir = _resolve_backup_dir()
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    target = backup_dir / f"pubg_accounts_{stamp}.db"

    src = sqlite3.connect(str(db_path))
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)  # online backup: consistent even during writes
        finally:
            dst.close()
    finally:
        src.close()

    backups = sorted(backup_dir.glob("pubg_accounts_*.db"))
    for old in backups[:-keep]:
        old.unlink()

    print(f"[backup] {target} ({target.stat().st_size / 1e6:.1f} MB), "
          f"{len(backups[-keep:])} kept")
    return target


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Backup the unified SQLite DB")
    parser.add_argument("--db", default="data/raw/sqlite/pubg_accounts.db")
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP)
    args = parser.parse_args()
    backup(Path(args.db), keep=args.keep)
