# 🎉 Momo Payment Gateway Integration

## ✅ Tích hợp hoàn tất: Thanh toán Momo qua QR Code

### 🔑 Thông tin API Momo (Test Environment)

```yaml
API URL: https://test-payment.momo.vn/v2/gateway/api/create
Partner Code: MOMO
Access Key: F8BBA842ECF85
Secret Key: K951B6PE1waDMi640xX08PD3vg6EkVlz
Request Type: captureWallet (QR Code payment)
```

---

## 📋 Flow thanh toán Momo

### 1️⃣ User chọn Momo

```
[Payment Checkout Page]
  → User chọn "Ví điện tử"
  → Dropdown chọn "Momo"
  → Click "Xác nhận thanh toán"
```

### 2️⃣ Tạo QR Code

```
Frontend → POST /api/payment/momo/create/{payment_id}
  ↓
Gateway → POST /payment/momo/create/{payment_id}
  ↓
Payment Service:
  - Gọi Momo API với HMAC-SHA256 signature
  - Momo trả về:
    * qrCodeUrl: Link ảnh QR code
    * payUrl: Link trang thanh toán
    * deeplink: Link mở app Momo
```

### 3️⃣ Hiển thị QR Code Modal

```
Frontend:
  - Hiển thị modal với QR code
  - User có thể:
    * Quét QR bằng app Momo
    * Click "Mở ứng dụng Momo" (deeplink)
  - Auto polling status mỗi 3 giây
```

### 4️⃣ User thanh toán

```
User mở Momo app:
  → Quét QR code
  → Xác nhận thanh toán trong app
  → Momo xử lý giao dịch
```

### 5️⃣ Momo gọi webhook

```
Momo → POST /payment/momo-notify (IPN)
  ↓
Gateway → POST /payment/momo/notify
  ↓
Payment Service:
  - Verify signature
  - Cập nhật payment.status = completed
  - Lưu TransID
```

### 6️⃣ Frontend polling detect

```
Frontend (3s interval):
  → GET /api/payment/momo/check/{payment_id}
  → Nếu status = completed:
    - Đóng modal
    - Reload page hoặc redirect invoice
```

### 7️⃣ Redirect về website

```
Momo → Redirect user to: /payment/momo-return
  ↓
Gateway → GET /payment/momo/return
  ↓
Payment Service:
  - Verify signature
  - Hiển thị success/failed page
  - Auto redirect to invoice (nếu success)
```

---

## 🗂️ Files Created/Modified

### Created:

1. ✅ **payment-service/momo_payment.py** - Momo API integration class
   - `create_payment()` - Tạo payment request với signature
   - `verify_signature()` - Verify callback signature
   - `query_transaction()` - Check transaction status
   - HMAC-SHA256 signature generation

### Modified:

2. ✅ **payment-service/routes.py** - Added 4 Momo routes:

   - `POST /payment/momo/create/{id}` - Create QR payment
   - `POST /payment/momo/notify` - IPN webhook
   - `GET /payment/momo/return` - Return URL
   - `GET /payment/momo/check/{id}` - Status polling

3. ✅ **payment-service/requirements.txt**

   - Added: `requests>=2.31.0`

4. ✅ **docker-compose.yml**

   - Added Momo environment variables to payment_service

5. ✅ **gateway/app.py** - Added 4 proxy routes:

   - `POST /api/payment/momo/create/{id}`
   - `POST /payment/momo-notify` (no auth - webhook)
   - `GET /payment/momo-return` (redirect handler)
   - `GET /api/payment/momo/check/{id}` (polling)

6. ✅ **gateway/templates/payment_checkout.html**
   - Added Momo QR modal HTML
   - Added `showMomoQR()` function
   - Added `checkMomoStatus()` polling
   - Added `openMomoApp()` deeplink
   - Modified `confirmPayment()` to detect Momo

---

## 🎨 UI Features

### Momo QR Code Modal:

- ✅ Beautiful centered modal with dark overlay
- ✅ Momo logo and branding
- ✅ QR code display (300x300)
- ✅ Amount display in VND
- ✅ "Mở ứng dụng Momo" button (deeplink)
- ✅ Auto-polling status indicator
- ✅ Close button (X)
- ✅ Cancel button

### Auto Status Checking:

- ✅ Poll every 3 seconds
- ✅ Auto-close modal when completed
- ✅ Show success message
- ✅ Reload page or redirect

---

## 🔐 Security Features

### 1. HMAC-SHA256 Signature

```python
# Request signature (alphabetically ordered keys)
raw_signature = (
    f"accessKey={access_key}"
    f"&amount={amount}"
    f"&extraData="
    f"&ipnUrl={notify_url}"
    f"&orderId={order_id}"
    f"&orderInfo={order_info}"
    f"&partnerCode={partner_code}"
    f"&redirectUrl={return_url}"
    f"&requestId={request_id}"
    f"&requestType={request_type}"
)
signature = hmac.new(secret_key, raw_signature, hashlib.sha256).hexdigest()
```

### 2. Signature Verification

```python
# Verify Momo callback
def verify_signature(data: Dict) -> bool:
    received = data.get("signature")
    expected = generate_signature(build_raw_string(data))
    return hmac.compare_digest(received, expected)
```

### 3. Webhook Protection

- ✅ Signature verification required
- ✅ No authentication needed (called by Momo)
- ✅ Safe database updates only after verification

---

## 🧪 Testing Guide

### 1. Start Services

```powershell
docker-compose up --build payment_service web_gateway
```

### 2. Access Payment Flow

```
1. Go to: http://localhost:8000
2. Add product to cart
3. Checkout
4. Select "Ví điện tử" → "Momo"
5. Click "Xác nhận thanh toán"
```

### 3. Expected Result

```
✓ Modal appears with QR code
✓ QR code image loads from Momo
✓ Amount displayed correctly
✓ Can click "Mở ứng dụng Momo"
✓ Status polling starts (every 3s)
```

### 4. Test Payment (Momo Test Environment)

```
Option 1: Scan QR with Momo app (if available)
Option 2: Use Momo test credentials (check Momo docs)
Option 3: Simulate IPN callback manually:

POST http://localhost:8000/payment/momo-notify
{
  "orderId": "ORD-123-...",
  "resultCode": 0,
  "transId": "12345678",
  "signature": "...",
  ...
}
```

### 5. Verify Success

```
✓ Frontend detects status = completed
✓ Modal closes automatically
✓ Page reloads or redirects
✓ Payment status updated in DB
✓ Can view invoice
```

---

## 🔄 API Endpoints Summary

### Payment Service (`payment_service:5003`):

```
POST   /payment/momo/create/{id}    - Create QR payment
POST   /payment/momo/notify         - Momo IPN webhook
GET    /payment/momo/return         - Return URL handler
GET    /payment/momo/check/{id}     - Status polling
```

### Gateway (`localhost:8000`):

```
POST   /api/payment/momo/create/{id}   - Proxy create
POST   /payment/momo-notify             - Proxy webhook (no auth)
GET    /payment/momo-return             - Proxy return
GET    /api/payment/momo/check/{id}     - Proxy status
```

---

## 📊 Database Changes

### Payment Model:

```python
payment.provider = "Momo (TransID: 12345678)"
payment.method = PaymentMethod.E_WALLET
payment.status = PaymentStatus.COMPLETED  # After IPN
```

### No schema changes needed - uses existing fields

---

## 🌐 Environment Variables

### docker-compose.yml:

```yaml
payment_service:
  environment:
    MOMO_API_URL: "https://test-payment.momo.vn/v2/gateway/api/create"
    MOMO_PARTNER_CODE: "MOMO"
    MOMO_ACCESS_KEY: "F8BBA842ECF85"
    MOMO_SECRET_KEY: "K951B6PE1waDMi640xX08PD3vg6EkVlz"
    MOMO_RETURN_URL: "http://localhost:8000/payment/momo-return"
    MOMO_NOTIFY_URL: "http://localhost:8000/payment/momo-notify"
```

### ⚠️ Production Notes:

- Change to production Momo endpoint
- Use real credentials (apply from Momo)
- Update return/notify URLs to production domain
- Enable HTTPS for webhooks

---

## 🎯 Flow Diagram

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ 1. Select Momo
       ↓
┌─────────────────────┐
│  payment_checkout   │
│      .html          │
└──────┬──────────────┘
       │ 2. POST /api/payment/momo/create/{id}
       ↓
┌─────────────┐
│   Gateway   │─────→ 3. POST /payment/momo/create/{id}
└──────┬──────┘
       │
       ↓
┌──────────────────┐
│ Payment Service  │─────→ 4. POST to Momo API
│  momo_payment.py │            (with HMAC signature)
└──────┬───────────┘
       │ 5. Return QR URL
       ↓
┌─────────────┐
│   Modal     │ ← 6. Display QR code
│  (QR Code)  │
└──────┬──────┘
       │ 7. User scans with Momo app
       │
       ↓
  [ User pays in Momo ]
       │
       ↓
┌─────────────┐
│  Momo API   │─────→ 8. POST /payment/momo-notify (IPN)
└─────────────┘
       │
       ↓
┌──────────────────┐
│ Payment Service  │─────→ 9. Verify signature
│   Update status  │       10. status = completed
└──────────────────┘
       ↑
       │ 11. Poll /api/payment/momo/check/{id} (every 3s)
       │
┌─────────────┐
│  Frontend   │─────→ 12. Detect completed
└──────┬──────┘       13. Close modal
       │              14. Redirect to invoice
       ↓
┌─────────────┐
│   Invoice   │
└─────────────┘
```

---

## ✅ Features Implemented

### ✓ QR Code Payment

- Momo QR code generation
- Beautiful modal display
- Responsive design

### ✓ Deep Link

- "Mở ứng dụng Momo" button
- Auto-open Momo app on mobile

### ✓ Auto Status Check

- Poll every 3 seconds
- Auto-close on success
- No manual refresh needed

### ✓ Webhook Integration

- IPN (Instant Payment Notification)
- Signature verification
- Secure status update

### ✓ Return URL

- User redirect after payment
- Success/failure page
- Auto redirect to invoice

### ✓ Security

- HMAC-SHA256 signature
- Request/response verification
- No plaintext secrets in frontend

---

## 🚀 Next Steps (Optional Enhancements)

1. **Production Momo Account**

   - Apply for production credentials
   - Update environment variables
   - Test with real transactions

2. **Other Payment Methods**

   - ZaloPay integration
   - VNPay integration
   - Banking QR code (VietQR)

3. **Payment Timeout**

   - Add 15-minute timeout for QR
   - Auto-cancel expired payments

4. **Email Notifications**

   - Send QR code via email
   - Payment confirmation email

5. **Transaction History**
   - Save Momo TransID
   - Link to transaction logs
   - Refund support

---

## 📝 Summary

**Khi user chọn Momo để thanh toán:**

1. ✅ Click "Xác nhận thanh toán" khi chọn Momo
2. ✅ Modal hiện ra với QR code từ Momo
3. ✅ User quét QR bằng app Momo
4. ✅ Thanh toán trong app Momo
5. ✅ Momo gọi webhook để update status
6. ✅ Frontend tự động detect và đóng modal
7. ✅ Redirect to invoice page
8. ✅ Orders được tạo tự động

**🎉 Hoàn tất tích hợp Momo Payment Gateway với QR Code!**
