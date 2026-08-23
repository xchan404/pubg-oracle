"""
Lightweight Experiment Tracking
JSONL ledger for training runs: params, metrics, dataset hashes, git state.
Zero-dependency alternative to MLflow; same core workflow:
    run_id = start_run("lgb_cheap", params={...})
    log_metrics(run_id, {"mae_egp": 1234.5})
    finish_run(run_id)
Ledger: mlruns/experiments.jsonl (gitignored).
"""

import hashlib
import json
import os
import platform
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEDGER_DIR = PROJECT_ROOT / "mlruns"
LEDGER_PATH = LEDGER_DIR / "experiments.jsonl"


def dataset_sha256(path: os.PathLike | str, sample_mb: int = 5) -> str:
    """Fast content hash: first/last N MB + size (stable, cheap on big files)."""
    p = Path(path)
    if not p.exists():
        return "missing"
    h = hashlib.sha256()
    size = p.stat().st_size
    chunk = sample_mb * 1024 * 1024
    with open(p, "rb") as fh:
        h.update(fh.read(chunk))
        if size > chunk:
            fh.seek(max(0, size - chunk))
            h.update(fh.read(chunk))
    h.update(str(size).encode())
    return h.hexdigest()[:16]


def _git_rev() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "no-git"


def _append(record: dict[str, Any]) -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def start_run(name: str, params: dict[str, Any] | None = None,
              dataset_path: str | None = None) -> str:
    run_id = uuid.uuid4().hex[:12]
    _append({
        "event": "start",
        "run_id": run_id,
        "name": name,
        "params": params or {},
        "dataset_sha": dataset_sha256(dataset_path) if dataset_path else None,
        "git_rev": _git_rev(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "timestamp": datetime.now(UTC).isoformat(),
    })
    return run_id


def log_metrics(run_id: str, metrics: dict[str, Any]) -> None:
    _append({"event": "metrics", "run_id": run_id,
             "metrics": metrics,
             "timestamp": datetime.now(UTC).isoformat()})


def finish_run(run_id: str, status: str = "success", note: str = "") -> None:
    _append({"event": "finish", "run_id": run_id, "status": status, "note": note,
             "timestamp": datetime.now(UTC).isoformat()})


def recent_runs(limit: int = 10) -> list:
    """Returns the last N runs summarized (start + final metrics merged)."""
    if not LEDGER_PATH.exists():
        return []
    runs: dict[str, dict[str, Any]] = {}
    order: list = []
    with open(LEDGER_PATH, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            rid = rec["run_id"]
            if rec["event"] == "start":
                runs[rid] = {**rec}
                order.append(rid)
            elif rec["event"] == "metrics" and rid in runs:
                runs[rid].setdefault("metrics", {}).update(rec.get("metrics", {}))
            elif rec["event"] == "finish" and rid in runs:
                runs[rid]["status"] = rec.get("status")
    return [runs[rid] for rid in order[-limit:]]


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for run in reversed(recent_runs()):
        m = run.get("metrics", {})
        print(f"{run['run_id']}  {run['name']:<24} status={run.get('status', '?'):<8} "
              f"mae={m.get('overall_mae_egp', '-')}  git={run.get('git_rev', '-')}")
