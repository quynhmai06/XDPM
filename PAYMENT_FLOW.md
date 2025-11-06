# Flow Thanh Toán Mới - Tích hợp Payment Service

## Khi nhấn nút "Thanh toán" trong giỏ hàng

### 🔄 Flow cũ (trước khi tích hợp payment-service):

1. User nhấn "Tiến hành thanh toán" từ `/cart`
2. Chuyển đến trang `/checkout` (xem tóm tắt đơn hàng)
3. Nhấn "Đặt hàng ngay"
4. ➡️ Gọi `POST /checkout/place`
5. ➡️ Tạo orders ngay lập tức trong orders-service
6. ➡️ Xóa giỏ hàng
7. ✅ Hiển thị "Đặt hàng thành công"

**Vấn đề:** Không có thanh toán thật, không có hóa đơn, không có hợp đồng số

---

### ✨ Flow mới (sau khi tích hợp payment-service):

#### **Bước 1: Từ giỏ hàng đến checkout**

- User nhấn **"Tiến hành thanh toán"** từ `/cart`
- Chuyển đến trang `/checkout`
- Hiển thị tóm tắt đơn hàng (items, tổng tiền)

#### **Bước 2: Tạo Payment**

- User nhấn **"Đặt hàng ngay"**
- ➡️ Frontend gọi `POST /checkout/place`
- ➡️ Gateway tính tổng tiền từ cart
- ➡️ Gateway tạo `order_id` unique: `ORD-{user_id}-{timestamp}-{random}`
- ➡️ Gateway gọi `POST /payment/create` đến payment-service với:
  ```json
  {
    "order_id": "ORD-123-1730000000-ABC123",
    "seller_id": 1,
    "amount": 500000,
    "method": "e-wallet",
    "cart_items": [
      { "item_type": "vehicle", "item_id": 5, "price": 500000, "quantity": 1 }
    ]
  }
  ```
- ➡️ Payment-service tạo Payment record với `status = pending`
- ➡️ Trả về `payment_id`

#### **Bước 3: Redirect đến Payment Checkout**

- Gateway lưu `payment_id` và `cart` vào session
- Gateway trả về response:
  ```json
  { "ok": true, "payment_id": 123, "redirect": "/payment/checkout/123" }
  ```
- Frontend tự động redirect đến **`/payment/checkout/123`**

#### **Bước 4: Trang Payment Checkout (từ payment-service)**

- URL: `/payment/checkout/{payment_id}`
- Hiển thị:
  - 📦 Thông tin đơn hàng (order_id, amount)
  - 💳 **Form chọn phương thức thanh toán:**
    - ✅ E-wallet (Momo, ZaloPay, VNPay)
    - ✅ Banking (chuyển khoản ngân hàng)
    - ✅ Cash (tiền mặt khi nhận hàng)
  - 🔘 **Nút "Xác nhận thanh toán"**

#### **Bước 5: Xác nhận thanh toán**

- User chọn phương thức và nhấn **"Xác nhận thanh toán"**
- ➡️ Frontend gọi `POST /api/payment/confirm/{payment_id}`
  ```json
  {
    "payment_method": "e-wallet",
    "provider": "Momo"
  }
  ```
- ➡️ Payment-service:
  - Cập nhật `payment.status = completed`
  - Tạo **Contract** (hóa đơn) với `contract_type = invoice`
  - Tạo **JWT signature** cho hợp đồng số
- ➡️ Trả về `contract_id`

#### **Bước 6: Hiển thị Invoice**

- Redirect đến **`/payment/invoice/{contract_id}`**
- Hiển thị:
  - 🧾 **Hóa đơn điện tử** (invoice)
  - 📝 Thông tin:
    - Order ID
    - Buyer info
    - Seller info
    - Items (product name, quantity, price)
    - Subtotal, VAT, Total
    - Payment method & provider
  - 🔒 **Chữ ký số** (JWT signature)
  - 📄 Nút **"Ký hợp đồng mua bán"** (optional)

#### **Bước 7: Tạo Orders (tự động sau payment completed)**

- Option 1: **Tự động khi confirm payment**
  - Gateway detect payment completed
  - Gọi helper function `_create_orders_from_payment()`
  - Tạo orders từ cart items trong session
  - Link orders với `payment_id`
- Option 2: **Manual callback** (nếu dùng external payment gateway)
  - Payment gateway gọi webhook `POST /api/payment/callback/{payment_id}`
  - Gateway verify payment status = completed
  - Tạo orders

#### **Bước 8: Dọn dẹp**

- Xóa giỏ hàng sau khi tạo orders thành công
- Xóa `pending_payment` trong session
- ✅ Hoàn tất!

---

## 📋 API Endpoints được thêm/sửa

### Gateway (gateway/app.py)

#### Modified:

- `POST /checkout/place`
  - **Trước:** Tạo orders ngay
  - **Sau:** Tạo payment và redirect đến payment checkout

#### Added:

- `POST /api/payment/create` - Proxy to payment-service
- `GET /payment/checkout/{id}` - Payment checkout page
- `POST /api/payment/confirm/{id}` - Xác nhận thanh toán
- `GET /payment/invoice/{contract_id}` - Trang hóa đơn
- `POST /api/payment/contract/sign` - Ký hợp đồng số
- `GET /api/payment/contract/preview/{id}` - Xem hợp đồng
- `POST /api/payment/simulate/{id}` - Simulate payment (testing)
- `GET /api/payment/{id}` - Get payment details
- `POST /api/payment/callback/{id}` - Webhook callback sau payment

#### Helper function:

- `_create_orders_from_payment(payment_id, user)` - Tạo orders sau khi payment completed

---

## 🖼️ UI Changes

### checkout.html JavaScript (modified)

```javascript
// Trước:
if (res.ok) {
  alert("Đặt hàng thành công! Mã đơn: " + data.order_ids.join(", "));
  window.location.href = "/";
}

// Sau:
if (res.ok && data.payment_id) {
  btn.innerHTML =
    '<i class="fas fa-check-circle"></i> Chuyển đến thanh toán...';
  setTimeout(() => {
    window.location.href = `/payment/checkout/${data.payment_id}`;
  }, 500);
}
```

---

## 🔐 Security & Data Flow

### Session Storage

```python
session['pending_payment'] = {
    'payment_id': 123,
    'order_id': 'ORD-456-...',
    'cart': [...]  # Original cart items
}
```

### Payment Data Stored

```python
Payment {
    id: 123,
    order_id: "ORD-456-1730000000-ABC123",
    buyer_id: 456,
    seller_id: 1,
    amount: 500000.0,
    method: PaymentMethod.E_WALLET,
    provider: "Momo",
    status: PaymentStatus.COMPLETED
}

Contract {
    id: 789,
    payment_id: 123,
    contract_type: ContractType.INVOICE,
    title: "Hóa đơn thanh toán ORD-456-...",
    content: "Chi tiết hóa đơn...",
    signer_name: "User Name",
    signature_jwt: "eyJhbGc...",  # JWT signature
    extra_data: {"items": [...], "vat_rate": 0.1}
}
```

### Order Creation (after payment)

```python
Order {
    buyer_id: 456,
    seller_id: 1,
    item_type: "vehicle",
    item_id: 5,
    price: 500000,
    payment_id: 123  # ← Link to payment
}
```

---

## 🧪 Testing

### Test Payment Flow:

```powershell
# 1. Start services
docker-compose up web_gateway payment_service

# 2. Thêm sản phẩm vào giỏ hàng (qua UI)
http://localhost:8000/cart

# 3. Nhấn "Tiến hành thanh toán"
# 4. Xem trang checkout
# 5. Nhấn "Đặt hàng ngay"
# 6. Sẽ redirect đến: http://localhost:8000/payment/checkout/123
# 7. Chọn phương thức thanh toán
# 8. Nhấn "Xác nhận thanh toán"
# 9. Xem invoice: http://localhost:8000/payment/invoice/789
```

### Simulate Payment (for testing without real gateway):

```bash
POST http://localhost:8000/api/payment/simulate/123
# Auto-complete payment without waiting for external gateway
```

---

## ✅ Benefits của Flow Mới

1. ✅ **Thanh toán thực tế** - User chọn phương thức thanh toán (e-wallet/banking/cash)
2. ✅ **Hóa đơn điện tử** - Tự động sinh invoice sau khi thanh toán
3. ✅ **Hợp đồng số hóa** - JWT-based digital signature
4. ✅ **Tracking** - Payment có status (pending → completed/failed)
5. ✅ **Audit trail** - Có record của payment trước khi tạo order
6. ✅ **Flexibility** - Dễ tích hợp external payment gateway (Momo, VNPay)
7. ✅ **Security** - Orders chỉ được tạo sau khi payment completed

---

## 🚀 Next Steps (Optional Enhancements)

1. **Real Payment Gateway Integration:**

   - Tích hợp Momo API
   - Tích hợp VNPay API
   - QR code generation for banking

2. **Email Notifications:**

   - Send invoice qua email sau thanh toán
   - Send order confirmation

3. **Admin Dashboard:**

   - View all payments
   - Approve/reject manual payments (cash)
   - Refund management

4. **Transaction History Sync:**

   - Sync payment data vào transactions-service
   - Unified history cho buyer/seller

5. **Contract Signing:**
   - Digital sale contract (hợp đồng mua bán)
   - Buyer & seller both sign
   - Legal binding document

---

## 📝 Summary

**Khi nhấn nút "Thanh toán" bây giờ sẽ:**

1. 🛒 Tạo payment từ giỏ hàng
2. 💳 Chuyển đến trang chọn phương thức thanh toán
3. ✅ Xác nhận thanh toán
4. 🧾 Hiển thị hóa đơn điện tử
5. 📦 Tự động tạo orders sau khi payment completed
6. ✨ Xóa giỏ hàng

**Flow hoàn chỉnh với thanh toán, hóa đơn, và hợp đồng số!** 🎉
