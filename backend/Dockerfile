# Build from repo root:
#   docker build -f backend/Dockerfile -t debating-backend .
# Run:
#   docker run --rm -p 8000:8000 \
#     -e DATABASE_URL=postgresql+psycopg://user:pass@host:5432/debating \
#     -e CORS_ORIGINS=http://localhost:5173 \
#     -e OPENAI_API_KEY=... \
#     -e GOOGLE_API_KEY=... \
#     debating-backend

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY sim_chat/ /app/sim_chat/
COPY src/ /app/src/
COPY data/seeded/ /app/data/seeded/

WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
