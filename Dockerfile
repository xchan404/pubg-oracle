# PUBG Oracle — multi-service image (api / bot / scheduler)
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps (procps for pgrep in container healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends procps libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code + artifacts needed by all three services
COPY config.py main.py ./
COPY config/ ./config/
COPY parser/ ./parser/
COPY schemas/ ./schemas/
COPY ml/ ./ml/
COPY intelligence/ ./intelligence/
COPY api/ ./api/
COPY database/ ./database/
COPY bot/ ./bot/
COPY ops/ ./ops/
COPY services/ ./services/
COPY scraper/ ./scraper/
COPY scripts/ ./scripts/
COPY models/ ./models/

# Non-root user
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data /app/sessions \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
