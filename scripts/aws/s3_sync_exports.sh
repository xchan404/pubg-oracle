#!/usr/bin/env bash
# scripts/aws/s3_sync_exports.sh
# Syncs dataset exports to the project bucket and shows version history.
# Input: S3_BUCKET as $1. Expected: sync summary, then object versions table.
set -euo pipefail
BUCKET="${1:-${S3_BUCKET:?pass the bucket name}}"
aws s3 sync /mnt/pubg-data/data "s3://$BUCKET/exports/" --exclude "*.session*"
aws s3api list-object-versions --bucket "$BUCKET" --prefix exports/ \
  --query 'Versions[].[Key,VersionId,LastModified]' --output table
