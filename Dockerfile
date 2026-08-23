# PUBG Market Intelligence — API service
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config/ ./config/
COPY parser/ ./parser/
COPY schemas/ ./schemas/
COPY ml/ ./ml/
COPY intelligence/ ./intelligence/
COPY api/ ./api/
COPY database/ ./database/

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
