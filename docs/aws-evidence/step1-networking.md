# Step 1 — VPC, Subnets, IGW, Route Tables

**Date:** 2026-11-26  
**Region:** us-east-1  
**Account:** 992382742407

## Commands

```bash
# Create VPC
aws ec2 create-vpc --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=project,Value=cse363}]'
# => VPC_ID=vpc-07bd230cf1328deca

# Public subnet
aws ec2 create-subnet --vpc-id vpc-07bd230cf1328deca --cidr-block 10.0.1.0/24 \
  --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=project,Value=cse363},{Key=Name,Value=pubg-public}]'
# => subnet-0e742c01aab0a7935

# Private subnet
aws ec2 create-subnet --vpc-id vpc-07bd230cf1328deca --cidr-block 10.0.2.0/24 \
  --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=project,Value=cse363},{Key=Name,Value=pubg-private}]'
# => subnet-02a53e2aed39f2343

# Internet Gateway
aws ec2 create-internet-gateway \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=project,Value=cse363}]'
# => igw-0c8ddefda9b81cb30
aws ec2 attach-internet-gateway --internet-gateway-id igw-0c8ddefda9b81cb30 \
  --vpc-id vpc-07bd230cf1328deca

# Public route table + 0.0.0.0/0 -> IGW
aws ec2 create-route-table --vpc-id vpc-07bd230cf1328deca \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=project,Value=cse363},{Key=Name,Value=pubg-public-rt}]'
# => rtb-0f428472538852fb3
aws ec2 create-route --route-table-id rtb-0f428472538852fb3 \
  --destination-cidr-block 0.0.0.0/0 --gateway-id igw-0c8ddefda9b81cb30
aws ec2 associate-route-table --route-table-id rtb-0f428472538852fb3 \
  --subnet-id subnet-0e742c01aab0a7935

# Private route table (no IGW route)
aws ec2 create-route-table --vpc-id vpc-07bd230cf1328deca \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=project,Value=cse363},{Key=Name,Value=pubg-private-rt}]'
# => rtb-076b81ff555d73afa
aws ec2 associate-route-table --route-table-id rtb-076b81ff555d73afa \
  --subnet-id subnet-02a53e2aed39f2343
```

## Outputs

| Resource | ID |
|---|---|
| VPC | vpc-07bd230cf1328deca |
| Public subnet | subnet-0e742c01aab0a7935 (10.0.1.0/24, us-east-1a) |
| Private subnet | subnet-02a53e2aed39f2343 (10.0.2.0/24, us-east-1a) |
| Internet Gateway | igw-0c8ddefda9b81cb30 |
| Public route table | rtb-0f428472538852fb3 (0.0.0.0/0 → IGW) |
| Private route table | rtb-076b81ff555d73afa (no IGW route) |

## Notes
- All resources tagged `project=cse363`.
- No NAT Gateway created (cost constraint).
- Private subnet has no route to the IGW (as required).