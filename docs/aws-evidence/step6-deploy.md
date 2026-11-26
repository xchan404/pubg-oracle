# Step 6 — EC2 Bootstrap & Deploy

**Date:** 2026-11-26  
**Instance:** i-0a52583fd325b9e87 (18.233.163.202)

## Commands

```bash
# Install Docker + Git
sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user

# Install Docker Compose plugin (v5.8.0)
sudo mkdir -p /usr/lib/docker/cli-plugins
sudo curl -SL 'https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64' \
  -o /usr/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/lib/docker/cli-plugins/docker-compose

# Install buildx (required by compose build)
sudo curl -SL 'https://github.com/docker/buildx/releases/download/v0.39.1/buildx-v0.39.1.linux-amd64' \
  -o /usr/lib/docker/cli-plugins/docker-buildx
sudo chmod +x /usr/lib/docker/cli-plugins/docker-buildx

# Clone repo and set up .env (placeholders; user fills real values)
git clone https://github.com/xchan404/pubg-oracle.git
cd pubg-oracle
cp .env.example .env
chmod 600 .env   # secrets stay on the instance, never committed

# Seed models into EBS
bash scripts/aws/seed_models.sh

# Deploy
docker compose -f docker-compose.yml -f compose.aws.yaml up -d --build
```

## Verification

### docker compose ps
```
NAME                      IMAGE                   STATUS                            PORTS
pubg-oracle-api-1         pubg-oracle-api         Up (healthy)                      0.0.0.0:8000->8000/tcp
pubg-oracle-bot-1         pubg-oracle-bot         Up (health: starting)             8000/tcp
pubg-oracle-scheduler-1   pubg-oracle-scheduler   Up (healthy)                      8000/tcp
```

### curl http://localhost:8000/healthz (on instance)
```
{"status":"ok"}
```

### curl http://18.233.163.202:8000/healthz (public)
```
200 {"status":"ok"}
```

### S3 upload test (using instance profile, no credentials in code)
```
aws s3 cp /tmp/test_upload.txt s3://pubg-oracle-cse363-992382742407/test/test_upload.txt
# => upload: ../../tmp/test_upload.txt to s3://pubg-oracle-cse363-992382742407/test/test_upload.txt
aws s3 ls s3://pubg-oracle-cse363-992382742407/test/
# => 2026-11-26 14:39:21          5 test_upload.txt
```

## Notes
- `.env` contains placeholder credentials; user fills real values on the server (never committed).
- `restart: unless-stopped` on all services.
- Only `api` publishes port 8000; bot and scheduler use the internal network.
- The scheduler runs but reports missing dataset CSV (expected — data not uploaded per project scope).
- The bot restarts due to placeholder Telegram credentials (user to fill real values).