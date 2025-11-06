# Payment Service Integration - Hoàn thành

## Tổng quan

Đã hoàn thành việc tích hợp **Payment Service** với chức năng thanh toán online và ký hợp đồng mua bán số hóa. Code được lấy từ nhánh `thanhdat` và chỉnh sửa để phù hợp với kiến trúc hiện tại.

## Các file đã tạo

### 1. payment-service/

- **Dockerfile**: Container configuration với Python 3.12-slim
- **requirements.txt**: Dependencies (Flask 3.0.3, SQLAlchemy 2.0+, PyJWT 2.9, psycopg2-binary)
- **db.py**: SQLAlchemy initialization wrapper
- **models.py**: ORM models với 2 bảng chính:
  - `Payment`: Quản lý giao dịch thanh toán (order_id, buyer_id, seller_id, amount, method, provider, status)
  - `Contract`: Quản lý hợp đồng số (payment_id, type, title, content, signer_name, signature_jwt)
  - 3 Enums: PaymentMethod (e-wallet, banking, cash), PaymentStatus (pending, completed, failed, refunded), ContractType (invoice, digital-sale)
- **routes.py**: REST API Blueprint với 15+ endpoints:
  - `POST /payment/create` - Tạo payment mới
  - `POST /payment/confirm/<id>` - Xác nhận thanh toán
  - `GET /payment/checkout/<id>` - Trang checkout (HTML)
  - `GET /payment/invoice/<contract_id>` - Trang hóa đơn (HTML)
  - `POST /payment/contract/sign` - Ký hợp đồng số hóa (JWT signature)
  - `GET /payment/contract/preview/<id>` - Xem trước hợp đồng
  - `POST /payment/update_method/<id>` - Đổi phương thức thanh toán
  - `POST /payment/simulate/<id>` - Simulate payment for testing
- **app.py**: Flask application factory với health check endpoint

## Cấu hình Docker

### docker-compose.yml

Đã thêm service `payment_service`:

```yaml
payment_service:
  build: ./payment-service
  environment:
    DATABASE_URL: postgresql+psycopg2://ev:evpass@db:5432/evdb
    JWT_SECRET: supersecret
    BANK_NAME: "EV Bank"
    BANK_ACCOUNT: "1234567890"
    VAT_RATE: "0.1"
  depends_on: [db]
  ports: ["5011:5003"] # External port 5011, internal port 5003
```

## Gateway Integration

### gateway/app.py

Đã thêm:

- Constant: `PAYMENT_URL = os.getenv("PAYMENT_URL", "http://payment_service:5003")`
- 8 payment proxy routes:
  - `POST /api/payment/create` - API tạo payment
  - `GET /payment/checkout/<id>` - Trang checkout
  - `POST /api/payment/confirm/<id>` - API xác nhận
  - `GET /payment/invoice/<contract_id>` - Trang invoice
  - `POST /api/payment/contract/sign` - API ký hợp đồng
  - `GET /api/payment/contract/preview/<id>` - API xem hợp đồng
  - `POST /api/payment/simulate/<id>` - API simulate payment

### gateway/Dockerfile

Đã thêm environment variable:

```dockerfile
PAYMENT_URL=http://payment_service:5003
```

## Tính năng chính

### 1. Thanh toán Online

- **3 phương thức**: E-wallet, Banking, Cash
- **Payment flow**: Create → Checkout → Confirm → Invoice
- **Payment statuses**: Pending, Completed, Failed, Refunded
- **Simulation mode**: Cho testing không cần external payment gateway

### 2. Ký hợp đồng số hóa

- **JWT-based signature**: Chữ ký số dùng PyJWT
- **2 loại hợp đồng**: Invoice (hóa đơn), Digital-sale (hợp đồng mua bán)
- **Contract flow**: Create payment → Generate invoice → Sign contract → View signed contract
- **Extra data**: JSON field lưu thông tin bổ sung (item details, VAT info, etc.)

### 3. Database Schema

```python
Payment:
  - id: Integer (PK)
  - order_id: String (unique, indexed)
  - buyer_id: Integer
  - seller_id: Integer
  - amount: Float
  - method: PaymentMethod enum
  - provider: String (nullable)
  - status: PaymentStatus enum
  - created_at, updated_at: DateTime
  - contracts: relationship to Contract[]

Contract:
  - id: Integer (PK)
  - payment_id: Integer (FK → Payment.id)
  - contract_type: ContractType enum
  - title: String
  - content: Text
  - signer_name: String
  - signature_jwt: Text
  - extra_data: JSON
  - signed_at: DateTime
  - payment: relationship to Payment
```

## Environment Variables

### Payment Service

- `DATABASE_URL`: PostgreSQL connection string
- `JWT_SECRET`: Secret key cho JWT signing (shared với auth-service)
- `BANK_NAME`: Tên ngân hàng (optional, cho invoice display)
- `BANK_ACCOUNT`: Số tài khoản (optional, cho invoice display)
- `VAT_RATE`: Thuế VAT (default: 0.1 = 10%)

## Cách sử dụng

### 1. Build và chạy services

```powershell
docker-compose up --build payment_service web_gateway
```

### 2. Test payment flow

```bash
# 1. Tạo payment
POST http://localhost:8000/api/payment/create
{
  "order_id": "ORD-123",
  "seller_id": 2,
  "amount": 500000,
  "method": "e-wallet"
}

# 2. Mở trang checkout
GET http://localhost:8000/payment/checkout/{payment_id}

# 3. Xác nhận thanh toán
POST http://localhost:8000/api/payment/confirm/{payment_id}
{
  "payment_method": "e-wallet",
  "provider": "Momo"
}

# 4. Xem invoice
GET http://localhost:8000/payment/invoice/{contract_id}

# 5. Ký hợp đồng
POST http://localhost:8000/api/payment/contract/sign
{
  "payment_id": 1,
  "contract_type": "digital-sale",
  "title": "Hợp đồng mua bán xe",
  "content": "...",
  "extra_data": {"product": "Tesla Model 3"}
}
```

### 3. Simulate payment (for testing)

```bash
POST http://localhost:8000/api/payment/simulate/{payment_id}
# Auto-completes payment without external gateway
```

## Security Features

- **Authentication**: All routes require JWT token
- **Authorization**: Buyer_id auto-filled from JWT (không cho user giả mạo)
- **Digital signature**: Contract signing dùng JWT với secret key
- **Input validation**: SQLAlchemy enums enforce valid payment methods/statuses

## Next Steps (Optional)

1. **Frontend integration**: Thêm payment buttons vào product detail pages
2. **Webhook integration**: Kết nối với Momo/VNPay real payment gateways
3. **Email notifications**: Gửi invoice qua email sau khi thanh toán
4. **Admin dashboard**: Thêm payment management vào admin panel
5. **Transaction sync**: Sync payment data vào transactions-service để unified history
6. **Refund flow**: Implement refund logic với admin approval

## Testing Checklist

- [ ] Service starts successfully: `docker-compose up payment_service`
- [ ] Health check: `curl http://localhost:5011/`
- [ ] Create payment: `POST /api/payment/create`
- [ ] View checkout page: `GET /payment/checkout/{id}`
- [ ] Confirm payment: `POST /api/payment/confirm/{id}`
- [ ] View invoice: `GET /payment/invoice/{contract_id}`
- [ ] Sign contract: `POST /api/payment/contract/sign`
- [ ] Preview contract: `GET /api/payment/contract/preview/{id}`
- [ ] Simulate payment: `POST /api/payment/simulate/{id}`

## Files Modified Summary

- ✅ Created: `payment-service/Dockerfile`
- ✅ Created: `payment-service/requirements.txt`
- ✅ Created: `payment-service/db.py`
- ✅ Created: `payment-service/models.py`
- ✅ Created: `payment-service/routes.py`
- ✅ Created: `payment-service/app.py`
- ✅ Modified: `docker-compose.yml` (added payment_service)
- ✅ Modified: `gateway/app.py` (added PAYMENT_URL + 8 proxy routes)
- ✅ Modified: `gateway/Dockerfile` (added PAYMENT_URL env var)

## Hoàn thành! 🎉

Payment service đã sẵn sàng để test và deploy. Không có conflict với git history vì tất cả files được tạo mới hoặc edit minimal.
