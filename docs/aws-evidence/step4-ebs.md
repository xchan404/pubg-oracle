# Step 4 — EBS Volume + Mount

**Date:** 2026-11-26  
**Region:** us-east-1

## Commands

```bash
# Create 10 GiB gp3 volume in us-east-1a
aws ec2 create-volume --size 10 --volume-type gp3 \
  --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=volume,Tags=[{Key=project,Value=cse363},{Key=Name,Value=pubg-oracle-data}]'
# => vol-07379544f7a798551

aws ec2 wait volume-available --volume-ids vol-07379544f7a798551

# Attach to instance
aws ec2 attach-volume --volume-id vol-07379544f7a798551 \
  --instance-id i-0a52583fd325b9e87 --device /dev/sdf
aws ec2 wait volume-in-use --volume-ids vol-07379544f7a798551

# SSH in and format + mount
ssh -i ~/.ssh/pubg-oracle-key.pem ec2-user@18.233.163.202
sudo mkfs -t ext4 /dev/nvme1n1
sudo mkdir -p /mnt/pubg-data
sudo mount /dev/nvme1n1 /mnt/pubg-data
echo '/dev/nvme1n1 /mnt/pubg-data ext4 defaults,nofail 0 2' | sudo tee -a /etc/fstab
sudo mkdir -p /mnt/pubg-data/{models,data,sessions}
sudo chown -R 1000:1000 /mnt/pubg-data
```

## Outputs

| Field | Value |
|---|---|
| Volume ID | vol-07379544f7a798551 |
| Size | 10 GiB |
| Type | gp3 |
| AZ | us-east-1a |
| Device (on instance) | /dev/nvme1n1 (Nitro) |
| Filesystem | ext4 |
| Mount point | /mnt/pubg-data |
| fstab entry | `/dev/nvme1n1 /mnt/pubg-data ext4 defaults,nofail 0 2` |
| Directories | models/, data/, sessions/ (owned by uid 1000) |
| Used | 36K / 9.8G (1%) |

## Notes
- Volume attached to instance i-0a52583fd325b9e87 (public IP 18.233.163.202).
- No NAT Gateway or Elastic IP created.