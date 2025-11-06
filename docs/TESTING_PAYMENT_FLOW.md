# Testing Flow Thanh Toán 4 Bước

## Chuẩn bị

### 1. Build và khởi động services

```bash
# Build payment_service với model mới
docker-compose build --no-cache payment_service

# Build gateway với routes mới
docker-compose build web_gateway

# Start all services
docker-compose up -d
```

### 2. Run migration

```bash
# Option 1: Run Python migration script
docker-compose exec payment_service python migrate_contracts.py

# Option 2: Run SQL directly
docker-compose exec -T db psql -U postgres -d ev_platform < payment-service/migrations/add_signature_fields.sql
```

### 3. Kiểm tra services đang chạy

```bash
docker-compose ps
```

Đảm bảo các services sau đang running:

- `db` (PostgreSQL)
- `payment_service` (Port 5011:5003)
- `web_gateway` (Port 5000:5000)
- `auth_service` (Port 5001:5001)
- `listing_service`

---

## Test Flow Từng Bước

### BƯỚC 1: Đặt Hàng

1. **Login** vào hệ thống:

   - URL: `http://localhost:5000/login`
   - Email: `buyer@test.com` / Password: `password`

2. **Thêm sản phẩm vào giỏ**:

   - Vào trang chủ: `http://localhost:5000/`
   - Browse sản phẩm (xe điện hoặc pin)
   - Click "Thêm vào giỏ hàng"

3. **Vào giỏ hàng**:

   - URL: `http://localhost:5000/cart`
   - Kiểm tra sản phẩm đã thêm
   - Click "Thanh toán" → Redirect đến `/checkout`

4. **Checkout**:

   - URL: `http://localhost:5000/checkout`
   - Kiểm tra:
     - ✓ Danh sách sản phẩm hiển thị đúng
     - ✓ Tổng tiền tính chính xác
     - ✓ **CHỈ CÓ 1 phương thức**: "Chuyển khoản ngân hàng" (đã checked)
   - Click "Đặt hàng ngay"

5. **Verify kết quả**:
   - JavaScript console không có lỗi
   - Redirect đến `/contract/sign/{contract_id}`
   - Trong network tab, kiểm tra:
     ```json
     Response from /checkout/place:
     {
       "ok": true,
       "payment_id": 1,
       "contract_id": 1,
       "redirect": "/contract/sign/1"
     }
     ```

---

### BƯỚC 2: Ký Hợp Đồng

1. **Trang ký hợp đồng**:

   - URL: `http://localhost:5000/contract/sign/{contract_id}`
   - Kiểm tra hiển thị:
     - ✓ Mã hợp đồng: `HD1` (hoặc số khác)
     - ✓ Status badge: "Chờ ký" (màu vàng)
     - ✓ Nội dung hợp đồng scrollable
     - ✓ 2 tabs: "Nhập tên đầy đủ" và "Upload chữ ký"
     - ✓ Checkbox đồng ý điều khoản
     - ✓ Nút "XÁC NHẬN KÝ HỢP ĐỒNG" (disabled ban đầu)

2. **Test ký bằng TEXT**:

   - Tab "Nhập tên đầy đủ" active
   - Nhập họ tên: `Nguyễn Văn A`
   - Check checkbox đồng ý
   - Nút "XÁC NHẬN KÝ" enabled
   - Click nút → Kiểm tra:
     - ✓ Loading spinner hiển thị
     - ✓ Redirect đến `/payment/checkout/{payment_id}`
     - ✓ Network request thành công

3. **Test ký bằng IMAGE** (nếu chưa ký):

   - Reload lại trang contract signing
   - Switch sang tab "Upload chữ ký"
   - Upload file ảnh (PNG/JPG, < 2MB)
   - Kiểm tra:
     - ✓ Preview ảnh hiển thị
     - ✓ Check checkbox và click ký
     - ✓ Redirect thành công

4. **Verify Database**:

   ```bash
   docker-compose exec db psql -U postgres -d ev_platform -c "SELECT id, contract_status, buyer_signature_type, buyer_signed_at FROM contracts ORDER BY id DESC LIMIT 1;"
   ```

   Kết quả mong đợi:

   ```
    id | contract_status | buyer_signature_type |    buyer_signed_at
   ----+-----------------+----------------------+------------------------
     1 | signed          | text                 | 2025-11-04 20:30:00
   ```

---

### BƯỚC 3: Thanh Toán VietQR

1. **Trang thanh toán**:

   - URL: `http://localhost:5000/payment/checkout/{payment_id}`
   - Kiểm tra hiển thị:
     - ✓ Mã đơn hàng: `ORD-...`
     - ✓ Mã hợp đồng: `HD1`
     - ✓ Số tiền (font lớn, màu cam)
     - ✓ Nội dung CK: `HD1`
     - ✓ Hướng dẫn 5 bước
     - ✓ **Mã QR Code** hiển thị từ VietQR
     - ✓ Thông tin ngân hàng:
       - MB Bank (Ngân hàng Quân Đội)
       - STK: 0359506148
       - Chủ TK: Lê Quý Nam
       - Nội dung: HD1
     - ✓ Warning box màu vàng
     - ✓ Nút "TÔI ĐÃ CHUYỂN TIỀN" (màu xanh lá)

2. **Kiểm tra QR Code**:

   - Right-click vào QR code → "Open image in new tab"
   - URL format:
     ```
     https://img.vietqr.io/image/MB-0359506148-compact2.jpg
     ?amount=500000000
     &addInfo=HD1
     &accountName=N%E1%BB%81n%20t%E1%BA%A3ng%20giao%20d%E1%BB%8Bch%20pin%20v%C3%A0%20xe%20%C4%91i%E1%BB%87n
     ```
   - QR code hiển thị rõ ràng (không bị lỗi 404)

3. **Test quét QR**:

   - Mở app ngân hàng có tính năng QR
   - Quét mã QR trên màn hình
   - Kiểm tra:
     - ✓ Số tiền tự động điền đúng
     - ✓ Nội dung CK là `HD1`
     - ✓ Tài khoản nhận: 0359506148 - Lê Quý Nam

4. **Click "TÔI ĐÃ CHUYỂN TIỀN"**:
   - Confirm dialog hiển thị
   - Click OK → Redirect đến `/payment/thankyou/{payment_id}`

---

### BƯỚC 4: Trang Cảm Ơn

1. **Trang thank you**:

   - URL: `http://localhost:5000/payment/thankyou/{payment_id}`
   - Kiểm tra hiển thị:
     - ✓ Icon success ✓ (animation scale in)
     - ✓ Tiêu đề: "Cảm ơn quý khách!"
     - ✓ Thông điệp cảm ơn đầy đủ
     - ✓ Order Summary:
       - Mã đơn hàng
       - Mã hợp đồng
       - Số tiền (format: 500,000,000 đ)
     - ✓ Status badge: "Đang chờ xác nhận" (màu vàng)
     - ✓ Info box với 4 điểm quan trọng
     - ✓ 2 nút: "Quay về trang chủ" và "Kiểm tra trạng thái"

2. **Test "Kiểm tra trạng thái"**:

   - Click nút → Loading spinner
   - Alert hiển thị:
     - Nếu chưa verify: "Thanh toán chưa được xác nhận..."
     - Nếu đã verify: "✓ Thanh toán đã được xác nhận!"

3. **Test auto-check** (optional):

   - Mở Console → Network tab
   - Sau 30s, tự động gọi `/api/payment/status/{payment_id}`
   - Status badge tự cập nhật nếu payment verified

4. **Test "Quay về trang chủ"**:
   - Click nút → Redirect đến `/`

---

## Verify Database Changes

### Check Payment

```bash
docker-compose exec db psql -U postgres -d ev_platform -c "
SELECT
  id,
  order_id,
  buyer_id,
  amount,
  method,
  status,
  created_at
FROM payments
ORDER BY id DESC
LIMIT 1;
"
```

### Check Contract

```bash
docker-compose exec db psql -U postgres -d ev_platform -c "
SELECT
  id,
  payment_id,
  title,
  contract_status,
  buyer_signature_type,
  LEFT(buyer_signature_data, 30) as signature_preview,
  buyer_signed_at,
  created_at
FROM contracts
ORDER BY id DESC
LIMIT 1;
"
```

Expected output:

```
 id | payment_id | title | contract_status | buyer_signature_type | signature_preview | buyer_signed_at | created_at
----+------------+-------+-----------------+----------------------+-------------------+-----------------+------------
  1 |          1 | HỢP   | signed          | text                 | Nguyễn Văn A      | 2025-11-04...   | 2025-11-04...
```

---

## Common Issues & Solutions

### Issue 1: Mã QR không hiển thị

**Nguyên nhân**: Lỗi CORS hoặc URL sai
**Solution**:

```javascript
// Check console for errors
// URL should be: https://img.vietqr.io/image/MB-0359506148-compact2.jpg?amount=...&addInfo=...&accountName=...
```

### Issue 2: Không redirect sau khi ký

**Nguyên nhân**: API `/contract/sign/{id}` lỗi
**Check**:

```bash
docker-compose logs payment_service | grep -i error
```

### Issue 3: Payment status không có contract_code

**Nguyên nhân**: Contract chưa được tạo
**Solution**:

```bash
# Check if contract exists for payment
docker-compose exec db psql -U postgres -d ev_platform -c "
SELECT p.id, p.order_id, c.id as contract_id
FROM payments p
LEFT JOIN contracts c ON c.payment_id = p.id
ORDER BY p.id DESC
LIMIT 5;
"
```

### Issue 4: Browser cache vẫn hiển thị phương thức thanh toán cũ

**Solution**:

- Hard refresh: `Ctrl + Shift + R`
- Clear cache: `Ctrl + Shift + Delete`
- Hoặc dùng Incognito: `Ctrl + Shift + N`

---

## Success Criteria

✅ **Flow hoàn chỉnh**:

1. ✓ Checkout → Tạo payment & contract
2. ✓ Contract signing → Lưu chữ ký
3. ✓ Payment QR → Hiển thị VietQR đúng
4. ✓ Thank you → Hiển thị thông tin đầy đủ

✅ **Database**:

- ✓ Payment record created với status `pending`
- ✓ Contract record created với status `signed`
- ✓ Buyer signature saved (type + data + timestamp)

✅ **UX**:

- ✓ Không có lỗi JavaScript
- ✓ Redirect mượt mà giữa các bước
- ✓ Loading states hiển thị đúng
- ✓ Thông báo lỗi rõ ràng (nếu có)

---

## Next Steps

Sau khi test thành công, bạn có thể:

1. **Implement seller signature** (optional):

   - Thêm trang để seller ký hợp đồng
   - Chỉ khi cả buyer và seller ký → status = signed

2. **Auto-verify payment**:

   - Tích hợp với banking API để auto-check giao dịch
   - Match transfer content với contract code
   - Auto update payment status

3. **Order creation**:

   - Tạo order records sau khi payment verified
   - Clear cart items
   - Send confirmation email

4. **Notification system**:

   - Email khi hợp đồng được ký
   - SMS khi thanh toán được xác nhận
   - Push notification cho status changes

5. **Tự động ẩn tin & ghi lịch sử giao dịch**:
   - Sau khi payment completed, hệ thống sẽ tạo Order và 2 bản ghi Transactions (mua/bán)
   - Tham khảo: docs/FEATURE_sold_hide_and_transactions.md
