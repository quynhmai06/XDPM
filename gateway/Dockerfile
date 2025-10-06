# ===== Runtime image =====
FROM python:3.12-slim

# system deps (tùy chọn, giúp pip nhanh/chắc hơn)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# cài deps trước để tận dụng layer cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy code
COPY . .

# biến môi trường (có thể override bằng docker-compose)
ENV AUTH_URL=http://auth_service:8001 \
    ADMIN_URL=http://admin_service:8002 \
    JWT_SECRET=devsecret \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1

# Gateway nghe trên cổng 8000
EXPOSE 8000

# chạy bằng gunicorn (ổn định hơn flask dev server)
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "app:app"]
