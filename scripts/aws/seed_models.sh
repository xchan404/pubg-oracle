#!/usr/bin/env bash
# scripts/aws/seed_models.sh
# One-time seeding of model artifacts from the image into the EBS bind mount.
# Run BEFORE the first `docker compose -f docker-compose.yml -f compose.aws.yaml up`.
# Idempotent: skips seeding if any *.pkl already exists (never overwrites retrained models).
set -euo pipefail

docker compose -f docker-compose.yml -f compose.aws.yaml run --rm --no-deps --user root api \
  sh -c 'mkdir -p /mnt/pubg-data/models && if ls /mnt/pubg-data/models/*.pkl >/dev/null 2>&1; then echo "models already present - skipping seed"; else cp -r /app/models/. /mnt/pubg-data/models/ && chown -R 1000:1000 /mnt/pubg-data/models; echo "seeded models into /mnt/pubg-data/models"; fi'
