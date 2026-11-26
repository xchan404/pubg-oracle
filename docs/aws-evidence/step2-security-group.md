# Step 2 — Security Group

**Date:** 2026-11-26  
**Region:** us-east-1

## Commands

```bash
# Create security group
aws ec2 create-security-group --group-name pubg-oracle-sg \
  --description "PUBG Oracle: 8000 public, 22 from my IP only" \
  --vpc-id vpc-07bd230cf1328deca \
  --tag-specifications 'ResourceType=security-group,Tags=[{Key=project,Value=cse363}]'
# => sg-0a3c55542b8ad80a4

# Inbound TCP 8000 from anywhere
aws ec2 authorize-security-group-ingress --group-id sg-0a3c55542b8ad80a4 \
  --protocol tcp --port 8000 --cidr 0.0.0.0/0

# Inbound TCP 22 from my IP only
aws ec2 authorize-security-group-ingress --group-id sg-0a3c55542b8ad80a4 \
  --protocol tcp --port 22 --cidr 196.155.76.216/32
```

## Outputs

| Rule | Protocol | Port | Source |
|---|---|---|---|
| 8000 public | TCP | 8000 | 0.0.0.0/0 |
| SSH | TCP | 22 | 196.155.76.216/32 |

## Notes
- No database port (5432/3306/etc.) is exposed.
- Default egress (all outbound) retained.