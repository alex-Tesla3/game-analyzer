FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# SQLite + in-memory caches: single worker avoids split-brain quota/alert state
CMD ["uvicorn", "src.web_app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
