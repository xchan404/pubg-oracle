#!/usr/bin/env bash
# One-time seeding of model files from the host repo into the EBS bind mount.
# Run from the repo root BEFORE the first docker compose up.
# Idempotent: skips if any *.pkl already exists.
set -euo pipefail

DEST=/mnt/pubg-data/models

sudo mkdir -p "$DEST"
if ls "$DEST"/*.pkl >/dev/null 2>&1; then
  echo "models already present in $DEST - skipping seed"
else
  sudo cp -n models/* "$DEST"/
  sudo chown -R 1000:1000 "$DEST"
  echo "seeded models into $DEST"
fi
