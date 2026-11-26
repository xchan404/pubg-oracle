#!/usr/bin/env bash
# scripts/aws/ec2_status.sh
# Shows this project's EC2 instance state, public IP and status checks.
# Input: INSTANCE_ID as $1 or env var. Expected: table with state/IP/checks.
set -euo pipefail
INSTANCE_ID="${1:-${INSTANCE_ID:?pass the instance id}}"
aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[].Instances[].{State:State.Name,PublicIP:PublicIpAddress,Type:InstanceType,AZ:Placement.AvailabilityZone}' \
  --output table
aws ec2 describe-instance-status --instance-ids "$INSTANCE_ID" \
  --query 'InstanceStatuses[].{System:SystemStatus.Status,Instance:InstanceStatus.Status}' --output table
