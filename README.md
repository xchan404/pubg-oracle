# PUBG Oracle — AI Account Valuation & Market Intelligence

PUBG Oracle evaluates PUBG Mobile account listings scraped from Telegram channels and returns a fair price, an expected range, and a security/transferability report. It combines an Arabic NLP parser, an XGBoost/CatBoost/LightGBM ensemble, conformal intervals, and a market-intelligence layer (item index, repost analytics, channel trust). A FastAPI backend serves a web dashboard, a Telegram bot, and an admin panel.

**Proposal:** CSE363 — Cloud Computing project, Milestone B (working local multi-container system + AWS evidence).

## Architecture

```
┌────────────┐     ┌────────────┐     ┌────────────┐
│   api      │◄────│    bot     │     │ scheduler  │
│  FastAPI   │     │  Telethon  │     │  (loop)    │
│  :8000     │◄────│            │     │            │
└─────┬──────┘     └────────────┘     └─────┬──────┘
      │                                      │
      ▼                                      ▼
┌─────────────────────────────────────────────────┐
│  data/ (SQLite + CSV/JSON)   models/ (joblib)  │
│  S3 (exports, models) when configured          │
└─────────────────────────────────────────────────┘
```

Data flow: Telegram listings → scraper → SQLite + CSV/JSON → parser/NLP features → ensemble pricer → fair value + range + security report. Scheduler rebuilds the training dataset, checks drift, and runs lifecycle (expiry, reminders, digest). Bot pushes live deals and serves the paywall.

## Prerequisites

- Docker + Docker Compose
- AWS Academy Learner Lab (for EC2/EBS/S3 evidence)
- Telegram API credentials (`API_ID`, `API_HASH` from https://my.telegram.org)
- Python 3.12 (for local dev without Docker)

## Local quickstart

```bash
cp .env.example .env
# fill in API_ID, API_HASH, BOT_TOKEN, MY_CHAT_ID, etc.
docker compose up --build
```

Open the dashboard at http://localhost:8000 and the bot in Telegram. Admin panel: http://localhost:8000/admin (token from `ADMIN_DASHBOARD_TOKEN`).

Run tests:

```bash
pip install -r requirements.txt
python -m pytest -q
```

## AWS deployment (EC2 + EBS + S3)

1. Create a VPC with a public subnet (10.0.1.0/24, route to IGW) and a private subnet (10.0.2.0/24, no IGW route). Security group: port 8000 from anywhere (demo), port 22 from your IP only.
2. Launch an EC2 instance (Amazon Linux 2023 or Ubuntu) and attach the `LabInstanceProfile` IAM role.
3. Create a 20 GiB gp3 EBS volume in the same AZ, attach, format (`mkfs -t xfs`), mount at `/mnt/pubg-data`, add to `/etc/fstab`.
4. Create the S3 bucket with versioning ON and Block Public Access all ON.
5. Bootstrap the instance (Docker, Compose, clone repo). Before the first `up`, prepare the EBS mount and seed models:

```bash
sudo mkdir -p /mnt/pubg-data/{models,data,sessions}
sudo chown -R 1000:1000 /mnt/pubg-data
git clone https://github.com/xchan404/pubg-oracle.git && cd pubg-oracle
cp .env.example .env   # fill in real values locally, never commit
bash scripts/aws/seed_models.sh   # one-time: seed models into /mnt/pubg-data/models
docker compose -f docker-compose.yml -f compose.aws.yaml up -d --build
docker compose ps
curl http://localhost:8000/market/summary
```

## Configuration

| Variable | Purpose |
|---|---|
| `API_ID` / `API_HASH` | Telegram API credentials (read by config.py) |
| `TELEGRAM_SESSION_NAME` | Telethon session file name |
| `BOT_TOKEN` | Telegram bot token (bot + background jobs) |
| `MY_CHAT_ID` | Owner chat id for admin alerts and payment review |
| `VODAFONE_CASH_NUMBER` / `INSTAPAY_HANDLE` | Manual payment collection details |
| `MIN_PROFIT_THRESHOLD` | Minimum profit (EGP) for deal alerts |
| `TARGET_CHATS` | Comma-separated target chats for the bot |
| `INTERNAL_TOKEN` | Token for bot → API deal push |
| `SCHEDULER_INTERVAL_MINUTES` | Scheduler cadence (default 360) |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) |
| `S3_BUCKET` | S3 bucket name (empty disables S3) |
| `AWS_REGION` | AWS region (default us-east-1) |

## Testing

Run `python -m pytest -q` (210 tests). Test evidence T1–T8 lives in `docs/aws-evidence/` (AWS console/CLI outputs).

## Troubleshooting

- **FloodWait:** Telegram rate limits; the scraper sleeps and resumes automatically.
- **Model not loaded:** ensure `models/*.pkl` exist; retrain via `/mlops/retrain` or run `ml/train.py`.
- **Lab session reset / new public IP:** re-run the EC2 bootstrap; update `ALLOWED_ORIGINS`.
- **Disk full on EBS:** extend the volume or clean `data/` exports.

## Teardown / cleanup

1. `docker compose down`
2. Terminate the EC2 instance.
3. Delete the EBS volume and snapshots.
4. Empty and delete the S3 bucket.
5. Verify lab credit stopped moving.

## Contribution log & AI assistance

- Developed by Mohamed Habib (xchan404).
- AI assistance (Cursor/Codex) was used for scaffolding, refactoring, and documentation; all code was reviewed and tested by the author. No credentials are committed.