# Step 7 — Final Verification

**Date:** 2026-11-26  
**Instance:** i-0a52583fd325b9e87 (18.233.163.202)

## Commands

```bash
# On-instance
curl -s http://localhost:8000/healthz
# => {"status":"ok"}

docker compose -f docker-compose.yml -f compose.aws.yaml ps
# => api: healthy, scheduler: healthy, bot: starting (placeholder creds)

# Public (from outside)
curl http://18.233.163.202:8000/healthz
# => 200 {"status":"ok"}
```

## Outputs

### On-instance healthz
```
{"status":"ok"}
```

### docker compose ps
```
NAME                      IMAGE                   STATUS                          PORTS
pubg-oracle-api-1         pubg-oracle-api         Up (healthy)                    0.0.0.0:8000->8000/tcp
pubg-oracle-bot-1         pubg-oracle-bot         Up (health: starting)           8000/tcp
pubg-oracle-scheduler-1   pubg-oracle-scheduler   Up (healthy)                    8000/tcp
```

### Public healthz
```
HTTP 200: {"status":"ok"}
```

## Summary
- API is healthy and reachable publicly on port 8000.
- Scheduler is healthy (dataset CSV not present — expected, data not uploaded per project scope).
- Bot is restarting due to placeholder Telegram credentials (user to fill real values in .env).
- No NAT Gateway or Elastic IP created.
- S3 upload tested successfully using the instance profile (no credentials in code).