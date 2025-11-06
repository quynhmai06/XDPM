# Flow Thanh Toán 4 Bước - EV Trading Platform

## Tổng quan

Quy trình thanh toán mới với ký hợp đồng điện tử và thanh toán VietQR

## Flow chi tiết

### Bước 1: Đặt hàng ngay

**Endpoint**: `POST /checkout/place`
**Người dùng**: Chọn sản phẩm và nhấn "Đặt hàng ngay"

**Backend xử lý**:

1. Tạo Order ID duy nhất: `ORD-{user_id}-{timestamp}-{uuid}`
2. Gọi Payment Service để tạo payment:
   ```
   POST /payment/create
   {
     "order_id": "ORD-123-...",
     "buyer_id": 1,
     "seller_id": 2,
     "amount": 500000000,
     "method": "banking"
   }
   ```
3. Tạo Contract từ Payment:
   ```
   POST /payment/contract/create-from-payment
   {
     "payment_id": 1,
     "product_info": {...},
     "buyer_info": {...},
     "seller_info": {...}
   }
   ```
4. Trạng thái:
   - Order: `draft`
   - Payment: `pending`
   - Contract: `pending_signature`

**Response**:

```json
{
  "ok": true,
  "payment_id": 1,
  "contract_id": 1,
  "redirect": "/contract/sign/1"
}
```

---

### Bước 2: Ký hợp đồng điện tử

**URL**: `/contract/sign/{contract_id}`
**Template**: `contract_signing.html`

**Giao diện hiển thị**:

1. Tiêu đề hợp đồng với mã: `HD{contract_id}`
2. Nội dung hợp đồng (scrollable):
   - Thông tin bên mua
   - Thông tin bên bán
   - Chi tiết sản phẩm
   - Giá trị hợp đồng
   - Điều khoản thanh toán, giao hàng, bảo hành
3. Phần ký (2 tùy chọn):
   - **Tab 1**: Nhập tên đầy đủ (text input)
   - **Tab 2**: Upload ảnh chữ ký (file upload)
4. Checkbox đồng ý điều khoản
5. Nút "XÁC NHẬN KÝ HỢP ĐỒNG"

**API Call**:

```javascript
POST /api/payment/contract/sign/{contract_id}
{
  "signer_role": "buyer",
  "signature_type": "text" | "image",
  "signature_data": "Nguyễn Văn A" | "data:image/png;base64,..."
}
```

**Backend xử lý**:

- Lưu `buyer_signature_type`, `buyer_signature_data`, `buyer_signed_at`
- Nếu cả buyer và seller đã ký → `contract_status = "signed"`
- Response: Redirect to `/payment/checkout/{payment_id}`

---

### Bước 3: Hiển thị mã QR thanh toán

**URL**: `/payment/checkout/{payment_id}`
**Template**: `payment_checkout.html`

**Giao diện hiển thị**:

1. Header:
   - Mã đơn hàng: `ORD-...`
   - Mã hợp đồng: `HD{contract_id}`
2. Số tiền thanh toán (lớn, nổi bật)
3. Hướng dẫn thanh toán (5 bước)
4. **Mã VietQR**:
   ```
   URL: https://img.vietqr.io/image/MB-0359506148-compact.png
        ?amount={amount}
        &addInfo=HD{contract_id}
   ```
5. Thông tin ngân hàng:
   - Ngân hàng: **MB Bank (Ngân hàng Quân Đội)**
   - Số TK: **0359506148**
   - Chủ TK: **Lê Quý Nam**
   - Nội dung CK: **HD{contract_id}**
6. Warning box: "KHÔNG THAY ĐỔI nội dung chuyển khoản"
7. Nút "TÔI ĐÃ CHUYỂN TIỀN" (màu xanh lá)

**JavaScript**:

```javascript
async function loadPaymentInfo() {
  const res = await fetch(`/api/payment/status/${paymentId}`);
  // Display amount, order_id, contract_code
  // Generate QR URL
}

function confirmPayment() {
  // Redirect to thank you page
  window.location.href = `/payment/thankyou/${paymentId}`;
}
```

---

### Bước 4: Xác nhận đã chuyển tiền

**URL**: `/payment/thankyou/{payment_id}`
**Template**: `payment_thankyou.html`

**Giao diện hiển thị**:

1. Icon success (✓) với animation
2. Tiêu đề: "Cảm ơn quý khách!"
3. Thông điệp:
   ```
   Cảm ơn quý khách đã thanh toán trên Nền tảng giao dịch pin và xe điện qua sử dụng.
   Nhân viên bên chúng tôi sẽ kiểm tra số tiền và xác nhận cho quý khách, đồng thời
   vận chuyển sản phẩm đến địa chỉ quý khách trong thời gian sớm nhất.
   ```
4. Order Summary:
   - Mã đơn hàng
   - Mã hợp đồng
   - Số tiền
5. Payment Status Badge:
   - ⏳ "Đang chờ xác nhận thanh toán" (vàng)
   - ✓ "Thanh toán đã được xác nhận" (xanh) - sau khi verify
6. Thông tin quan trọng:
   - ✓ Đơn hàng đã được ghi nhận
   - ✓ Xác minh trong 5-10 phút
   - ✓ Nhận email/SMS khi xác minh
   - ✓ Giao hàng trong 3-5 ngày
7. 2 nút:
   - "Quay về trang chủ" (trắng)
   - "Kiểm tra trạng thái" (tím) → Gọi API check status

**JavaScript**:

```javascript
async function checkPaymentStatus() {
  const res = await fetch(`/api/payment/status/${paymentId}`);
  if (data.status === "paid") {
    // Update UI to show verified
    alert("✓ Thanh toán đã được xác nhận!");
  } else {
    alert("Thanh toán chưa được xác nhận. Vui lòng đợi thêm...");
  }
}

// Auto-check every 30 seconds
setInterval(loadPaymentInfo, 30000);
```

---

## API Endpoints

### Payment Service

| Endpoint                                | Method | Description                |
| --------------------------------------- | ------ | -------------------------- |
| `/payment/create`                       | POST   | Tạo payment record         |
| `/payment/status/{id}`                  | GET    | Lấy status của payment     |
| `/payment/contract/create-from-payment` | POST   | Tạo contract từ payment    |
| `/payment/contract/view/{id}`           | GET    | Xem chi tiết contract      |
| `/payment/contract/sign/{id}`           | POST   | Ký contract (buyer/seller) |

### Gateway Proxy

| Endpoint                          | Method | Description                       |
| --------------------------------- | ------ | --------------------------------- |
| `/checkout/place`                 | POST   | Đặt hàng → Tạo payment & contract |
| `/contract/sign/{id}`             | GET    | Trang ký hợp đồng                 |
| `/payment/checkout/{id}`          | GET    | Trang thanh toán VietQR           |
| `/payment/thankyou/{id}`          | GET    | Trang cảm ơn                      |
| `/api/payment/contract/view/{id}` | GET    | Proxy to payment service          |
| `/api/payment/contract/sign/{id}` | POST   | Proxy to payment service          |
| `/api/payment/status/{id}`        | GET    | Proxy to payment service          |

---

## Database Schema

### Contracts Table - New Fields

```sql
ALTER TABLE contracts ADD COLUMN:
- contract_status VARCHAR(50)  -- 'draft', 'pending_signature', 'signed', 'completed'
- buyer_signature_type VARCHAR(20)  -- 'text', 'image'
- buyer_signature_data TEXT  -- Full name or base64 image
- buyer_signed_at TIMESTAMP
- seller_signature_type VARCHAR(20)
- seller_signature_data TEXT
- seller_signed_at TIMESTAMP
```

---

## VietQR Configuration

**Bank**: MB Bank (Military Commercial Joint Stock Bank)  
**Account Number**: 0359506148  
**Account Name**: Lê Quý Nam  
**QR URL**: `https://img.vietqr.io/image/MB-{account}-compact.png?amount={amount}&addInfo={content}`

**Transfer Content Format**: `HD{contract_id}`  
Example: `HD1`, `HD123`

---

## Testing Checklist

- [ ] Bước 1: Đặt hàng tạo payment & contract thành công
- [ ] Bước 2: Trang ký hợp đồng load đúng nội dung
- [ ] Bước 2a: Ký bằng text (nhập tên) hoạt động
- [ ] Bước 2b: Ký bằng upload ảnh hoạt động
- [ ] Bước 3: Redirect đến trang thanh toán sau khi ký
- [ ] Bước 3: VietQR hiển thị đúng số tiền và nội dung
- [ ] Bước 3: Thông tin ngân hàng hiển thị đầy đủ
- [ ] Bước 4: Nút "Tôi đã chuyển tiền" redirect đến thank you
- [ ] Bước 4: Trang thank you hiển thị đúng thông tin
- [ ] Bước 4: Nút "Kiểm tra trạng thái" gọi API đúng
- [ ] Bước 4: Auto-check status mỗi 30s hoạt động
- [ ] Database: Contract status được cập nhật đúng
- [ ] Database: Signature data được lưu chính xác

---

## Migration

Run migration script:

```bash
docker-compose exec payment_service python migrate_contracts.py
```

Or manually run SQL:

```bash
docker-compose exec db psql -U postgres -d ev_platform -f /app/migrations/add_signature_fields.sql
```

---

## Notes

- Contract chỉ cần buyer ký (seller auto-approve)
- Payment status vẫn là `pending` cho đến khi admin verify manual
- VietQR sử dụng service miễn phí từ vietqr.io
- Nội dung CK phải chính xác để dễ verify
