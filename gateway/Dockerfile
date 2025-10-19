FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Đặt đúng cổng của service: gateway=8000, admin-service=5003
EXPOSE 8000
CMD ["python", "app.py"]
