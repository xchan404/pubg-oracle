#!/usr/bin/env bash
# scripts/aws/seed_models.sh
# One-time seeding of model artifacts from the image into the EBS bind mount.
# Run BEFORE the first `docker compose -f docker-compose.yml -f compose.aws.yaml up`.
# Requires the project to be cloned on the EC2 host with models/ present.
set -euo pipefail
docker compose -f docker-compose.yml -f compose.aws.yaml run --rm --no-deps --user root api \
  cp -r /app/models/. /mnt/pubg-data/models/
echo "seeded models into /mnt/pubg-data/models"