# Step 5 — S3 Bucket

**Date:** 2026-11-26  
**Region:** us-east-1

## Commands

```bash
BUCKET=pubg-oracle-cse363-992382742407

# Create bucket
aws s3api create-bucket --bucket $BUCKET --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning --bucket $BUCKET \
  --versioning-configuration Status=Enabled

# Block all public access
aws s3api put-public-access-block --bucket $BUCKET \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

## Outputs

| Field | Value |
|---|---|
| Bucket name | pubg-oracle-cse363-992382742407 |
| Bucket ARN | arn:aws:s3:::pubg-oracle-cse363-992382742407 |
| Region | us-east-1 |
| Versioning | Enabled |
| BlockPublicAcls | true |
| IgnorePublicAcls | true |
| BlockPublicPolicy | true |
| RestrictPublicBuckets | true |

## Notes
- Bucket name includes account ID for global uniqueness.
- No credentials written to any file.