FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app
COPY prompts /app/prompts
COPY evaluation /app/evaluation

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -m seed.seed_data && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
