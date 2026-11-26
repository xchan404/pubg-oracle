#!/usr/bin/env bash
# scripts/aws/ebs_snapshot.sh
# Creates a snapshot of the data volume and lists recent snapshots.
# Input: VOLUME_ID as $1. Expected: snapshot id, then a table of snapshots.
set -euo pipefail
VOLUME_ID="${1:-${VOLUME_ID:?pass the volume id}}"
SNAP=$(aws ec2 create-snapshot --volume-id "$VOLUME_ID" \
  --description "pubg-oracle data backup $(date -u +%F)" \
  --query 'SnapshotId' --output text)
echo "snapshot: $SNAP"
aws ec2 wait snapshot-completed --snapshot-ids "$SNAP"
aws ec2 describe-snapshots --owner-ids self \
  --query 'Snapshots[].[SnapshotId,StartTime,State,VolumeSize]' --output table
