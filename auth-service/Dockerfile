FROM python:3.11-slim
WORKDIR /app

# Cài deps hệ thống cho psycopg2 (Postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PORT=5001
EXPOSE 5001
CMD ["python", "app.py"]
