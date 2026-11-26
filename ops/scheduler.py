"""
Ops Scheduler
Long-running loop for the compose `scheduler` service:
  - rebuilds the flywheel training dataset (asking + verified labels)
  - runs retrain drift/threshold checks via ml.retrain_service CLI logic
Interval configurable via SCHEDULER_INTERVAL_MINUTES (default 360 = 6h).
"""

import os
import sys
import time
import traceback
from datetime import UTC, datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def run_cycle() -> None:
    print(f"\n[{_stamp()}] === scheduler cycle start ===", flush=True)

    try:
        from intelligence.freshness import get_freshness
        fresh = get_freshness()
        print(f"[freshness] status={fresh['status']} "
              f"last={fresh['last_listing_at']} "
              f"24h={fresh['listings_24h']} channels_24h={fresh['channels_24h']}",
              flush=True)
        if fresh["is_stale"]:
            print("[freshness] WARNING: listings are stale — is the scraper running?",
                  flush=True)
    except Exception as e:
        print(f"[freshness] FAILED: {e}", flush=True)

    try:
        from ml.dataset_builder import build_training_dataset
        report = build_training_dataset()
        print(f"[dataset] asking={report['asking_rows']:,} "
              f"verified={report['verified_rows']} -> {report['output']}", flush=True)
    except Exception as e:
        traceback.print_exc()
        print(f"[dataset] FAILED: {e}", flush=True)

    try:
        from ml.retrain_service import run_retrain_service
        run_retrain_service(check_only=True)
    except Exception as e:
        traceback.print_exc()
        print(f"[retrain-check] FAILED: {e}", flush=True)

    # Subscriptions: expiry notices, renewal reminders, daily digest.
    # Gated to once per UTC day even though the scheduler ticks more often.
    try:
        from database.db import SessionLocal
        from services.lifecycle import run_daily_if_due

        with SessionLocal() as session:
            maintenance = run_daily_if_due(session)
        if maintenance is None:
            print("[lifecycle] already ran today — skipping", flush=True)
        else:
            print(f"[lifecycle] expired={maintenance.expired} "
                  f"reminded={maintenance.reminded} "
                  f"sent={maintenance.sent} failed={maintenance.failed} "
                  f"skipped={maintenance.skipped} "
                  f"digest={maintenance.digest_sent}", flush=True)
    except Exception as e:
        traceback.print_exc()
        print(f"[lifecycle] FAILED: {e}", flush=True)

    print(f"[{_stamp()}] === scheduler cycle done ===", flush=True)


def main() -> None:
    interval_min = float(os.getenv("SCHEDULER_INTERVAL_MINUTES", "360"))
    print(f"[ops-scheduler] starting; interval={interval_min} min", flush=True)

    if os.getenv("RUN_ONCE"):
        run_cycle()
        return

    while True:
        start = time.monotonic()
        try:
            run_cycle()
        except Exception as e:  # pragma: no cover - belt & suspenders
            print(f"[scheduler] unexpected error: {e}", flush=True)
        elapsed = time.monotonic() - start
        sleep_s = max(60.0, interval_min * 60 - elapsed)
        print(f"[ops-scheduler] sleeping {sleep_s / 60:.1f} min", flush=True)
        time.sleep(sleep_s)


if __name__ == "__main__":
    main()
