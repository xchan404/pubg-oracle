# Step 3 — EC2 Instance + Key Pair

**Date:** 2026-11-26  
**Region:** us-east-1

## Commands

```bash
# Create key pair (private key saved outside repo, never committed)
aws ec2 create-key-pair --key-name pubg-oracle-key --query 'KeyMaterial' --output text
# Save to ~/.ssh/pubg-oracle-key.pem with proper newlines (UTF-8, 64-char lines)

# Get Amazon Linux 2023 AMI ID
aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query 'Parameter.Value' --output text
# => ami-0aacbf72109c53c0c

# Launch instance
aws ec2 run-instances \
  --image-id ami-0aacbf72109c53c0c \
  --instance-type t3.micro \
  --key-name pubg-oracle-key \
  --subnet-id subnet-0e742c01aab0a7935 \
  --security-group-ids sg-0a3c55542b8ad80a4 \
  --iam-instance-profile Name=LabInstanceProfile \
  --associate-public-ip-address \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=project,Value=cse363},{Key=Name,Value=pubg-oracle}]'
# => i-0a52583fd325b9e87

aws ec2 wait instance-running --instance-ids i-0a52583fd325b9e87
```

## Outputs

| Field | Value |
|---|---|
| Instance ID | `i-0a52583fd325b9e87` |
| State | running |
| Type | t3.micro |
| AZ | us-east-1a |
| AMI | Amazon Linux 2023 (`ami-0aacbf72109c53c0c`) |
| Public IP | `18.233.163.202` |
| Key pair | `pubg-oracle-key` (saved to `~/.ssh/`, never committed) |
| IAM profile | LabInstanceProfile |
| Subnet | subnet-0e742c01aab0a7935 (public) |
| Security group | sg-0a3c55542b8ad80a4 |

## Notes
- Private key saved to `~/.ssh/pubg-oracle-key.pem` (outside repo, permissions restricted).
- `*.pem` added to `.gitignore`.
- Original instance i-0caafdb1720bcddd4 was terminated due to a malformed key file; new instance launched with corrected key.
- EBS volume attachment is Step 4.