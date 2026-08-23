"""
DEPRECATED: This module is kept only for backwards compatibility.
All ad storage now lives in the unified SQLAlchemy layer (database/ads.py)
backed by data/raw/sqlite/pubg_accounts.db.

The legacy db/sniper.db is migrated automatically on first use.
"""

import warnings

warnings.warn(
    "db.database is deprecated; import from database.ads instead.",
    DeprecationWarning,
    stacklevel=2,
)

from database.ads import initialize as init_db
from database.ads import save_ad  # noqa: E402,F401

__all__ = ["save_ad", "init_db"]
