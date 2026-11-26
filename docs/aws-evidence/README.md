# AWS Evidence Index — PUBG Oracle (CSE363)

**Project:** pubg-oracle  
**Region:** us-east-1  
**Account:** 992382742407  
**Date:** 2026-11-26

## Resource IDs

| Resource | ID |
|---|---|
| VPC | vpc-07bd230cf1328deca |
| Public subnet | subnet-0e742c01aab0a7935 (10.0.1.0/24, us-east-1a) |
| Private subnet | subnet-02a53e2aed39f2343 (10.0.2.0/24, us-east-1a) |
| Internet Gateway | igw-0c8ddefda9b81cb30 |
| Public route table | rtb-0f428472538852fb3 (0.0.0.0/0 → IGW) |
| Private route table | rtb-076b81ff555d73afa (no IGW route) |
| Security group | sg-0a3c55542b8ad80a4 (8000 public, 22 from IP) |
| EC2 instance | i-0a52583fd325b9e87 (t3.micro, AL2023, 18.233.163.202) |
| Key pair | pubg-oracle-key (~/.ssh/, never committed) |
| EBS volume | vol-07379544f7a798551 (10 GiB gp3, /mnt/pubg-data) |
| S3 bucket | pubg-oracle-cse363-992382742407 (versioning ON, block public access ON) |

## Steps

| Step | Description | Evidence file | Status |
|---|---|---|---|
| 1 | VPC, subnets, IGW, route tables | step1-networking.md | PASS |
| 2 | Security group (8000 public, 22 IP-only) | step2-security-group.md | PASS |
| 3 | EC2 instance + key pair | step3-ec2.md | PASS |
| 4 | EBS volume + mount + chown | step4-ebs.md | PASS |
| 5 | S3 bucket (versioning + block public) | step5-s3.md | PASS |
| 6 | Bootstrap + deploy (Docker, Compose, S3) | step6-deploy.md | PASS |
| 7 | Final verification | step7-verify.md | PASS |

## Tests

| Test | Goal | Result | Evidence |
|---|---|---|---|
| T1 | Reachability — evaluate account returns estimate | PASS | tests/T1.md |
| T2 | Container cooperation — healthcheck + /evaluate in logs | PASS (bot BLOCKED on creds) | tests/T2.md |
| T3 | Persistence — data survives container recreate | PASS | tests/T3.md |
| T4 | Storage protection — S3 versioning + presigned URL + public denied | PASS | tests/T4.md |
| T5 | Recovery — snapshot restore, read record | PASS | tests/T5.md |
| T6 | Security — 8000 allowed, DB port blocked, SSH restricted, iam denied | PASS (c not tested) | tests/T6.md |
| T7 | Automation — three AWS scripts | PASS | tests/T7.md |
| T8 | Operational failure — stop/start api, system recovers | PASS | tests/T8.md |

## Cost note

- **No NAT Gateway** — private subnet has no internet route (cost avoidance).
- **No Elastic IP** — instance uses auto-assigned public IP (changes on stop/start).
- **t3.micro** — smallest general-purpose instance (free-tier eligible).
- **10 GiB gp3 EBS** — minimal volume size.
- **S3** — standard storage, versioning enabled (small footprint).
- Lab session resets every ~4 hours; instance may need re-bootstrap.

## Teardown / cleanup

Delete in this order:

1. `docker compose -f docker-compose.yml -f compose.aws.yaml down` on the instance.
2. Terminate EC2 instance: `aws ec2 terminate-instances --instance-ids i-0a52583fd325b9e87`
3. Delete EBS volume: `aws ec2 delete-volume --volume-id vol-07379544f7a798551`
4. Empty and delete S3 bucket:
   ```bash
   aws s3 rm s3://pubg-oracle-cse363-992382742407 --recursive
   aws s3 rb s3://pubg-oracle-cse363-992382742407
   ```
5. Delete security group: `aws ec2 delete-security-group --group-id sg-0a3c55542b8ad80a4`
6. Delete route tables, subnets, IGW, VPC:
   ```bash
   aws ec2 delete-route-table --route-table-id rtb-0f428472538852fb3
   aws ec2 delete-route-table --route-table-id rtb-076b81ff555d73afa
   aws ec2 detach-internet-gateway --internet-gateway-id igw-0c8ddefda9b81cb30 --vpc-id vpc-07bd230cf1328deca
   aws ec2 delete-internet-gateway --internet-gateway-id igw-0c8ddefda9b81cb30
   aws ec2 delete-subnet --subnet-id subnet-0e742c01aab0a7935
   aws ec2 delete-subnet --subnet-id subnet-02a53e2aed39f2343
   aws ec2 delete-vpc --vpc-id vpc-07bd230cf1328deca
   ```
7. Delete key pair: `aws ec2 delete-key-pair --key-name pubg-oracle-key`
8. Verify lab credit stopped moving.