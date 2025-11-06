FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables (override via docker-compose)
ENV AUTH_URL=http://auth_service:5001 \
    LISTING_URL=http://listing_service:5002 \
    PRICING_URL=http://pricing_service:5003 \
    ADMIN_URL=http://admin_service:5002 \
    SEARCH_URL=http://search_service:5003 \
    FAVORITES_URL=http://favorites_service:5004 \
    ORDERS_URL=http://orders_service:5005 \
    REVIEWS_URL=http://reviews_service:5007 \
    TRANSACTIONS_URL=http://transactions_service:5008 \
    PAYMENT_URL=http://payment_service:5003 \
    JWT_SECRET=devsecret \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1

# Gateway listens on port 8000
EXPOSE 8000

# Run with gunicorn (production-ready)
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "app:app"]
