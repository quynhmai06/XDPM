# Sản phẩm bán xong → ẩn khỏi nền tảng → ghi lịch sử giao dịch

Tài liệu mô tả chức năng sau khi một sản phẩm (xe điện/pin) được bán thành công trong EV-Platform. Bạn có thể chép nguyên nội dung này vào báo cáo dự án.

## Tóm tắt nội dung chính

- 3 hành động sau khi bán xong: ẩn tin (ACTIVE → SOLD), ghi Transactions (kèm snapshot), phân phối thông tin cho Buyer/Seller/Admin.
- Vai trò và dữ liệu hiển thị cho từng bên: a) Người mua, b) Người bán, c) Quản trị viên.
- Luồng xử lý map vào các service: payment-service → gateway callback → orders-service → listing-service (mark SOLD) → transactions-service (ghi 2 giao dịch buyer/seller + timeline).
- JSON gợi ý cho snapshot metadata (đính kèm mỗi transaction).
- Pseudo-code tích hợp vào gateway sau khi payment completed.
- KPI/Báo cáo gợi ý để đánh giá hiệu quả.

---

## 1) Quy trình tổng thể

Khi một sản phẩm được thanh toán thành công, hệ thống tự động thực hiện 3 tác vụ chính:

1. Ẩn sản phẩm khỏi nền tảng (ACTIVE → SOLD)

   - Tin đăng chuyển trạng thái từ ACTIVE → SOLD.
   - Không hiển thị ở trang chủ, tìm kiếm, danh sách đang bán.
   - Chỉ người bán và quản trị viên có thể xem lại chi tiết tin sau bán.

2. Ghi nhận lịch sử giao dịch (Transactions)

   - Tạo một bản ghi giao dịch lưu: người mua, người bán, sản phẩm, số tiền, thời gian, phương thức thanh toán, trạng thái.
   - Lưu kèm “snapshot” dữ liệu sản phẩm tại thời điểm bán (tên/ảnh/giá/thuộc tính), phục vụ tra cứu, in hóa đơn, xử lý khiếu nại.

3. Phân phối thông tin đến các bên liên quan
   - Người mua: thêm vào mục "Lịch sử mua hàng".
   - Người bán: thêm vào mục "Lịch sử bán hàng".
   - Quản trị viên: dùng cho báo cáo thống kê, giám sát, tranh chấp.

---

## 2) Vai trò và thông tin được lưu

### a) Người mua (Buyer)

- Nhận thông báo “Thanh toán thành công”.
- Sản phẩm biến mất khỏi giỏ hàng, yêu thích, danh sách mua sắm.
- Phần "Lịch sử mua hàng" hiển thị: tên sản phẩm, ảnh, giá thanh toán, ngày thanh toán, người bán, phương thức thanh toán, trạng thái giao hàng (nếu có).
- Có thể xem chi tiết giao dịch hoặc xuất hóa đơn.

### b) Người bán (Seller)

- Nhận thông báo “Sản phẩm đã bán thành công”.
- Tin đăng chuyển về "Đã bán" (SOLD) và ẩn khỏi nền tảng công khai.
- Phần "Lịch sử bán hàng" hiển thị: tên sản phẩm, người mua, giá bán, thời gian bán, phí nền tảng (nếu có), trạng thái thanh toán, ảnh/snapshot sản phẩm tại thời điểm bán.
- Theo dõi tổng doanh thu, thống kê, khiếu nại giao dịch.

### c) Quản trị viên (Admin)

- Có quyền xem toàn bộ giao dịch của hệ thống.
- Xem mã giao dịch, người mua, người bán, giá trị, phương thức thanh toán, ngày thanh toán, trạng thái.
- Phục vụ giám sát hoạt động, phát hiện gian lận, xử lý tranh chấp.

---

## 3) Luồng xử lý (map vào các service hiện có)

1. Buyer thanh toán thành công (payment-service → status = completed/paid).
2. Gateway nhận callback/confirm → tạo đơn (orders-service) từ giỏ hàng (đã có luồng cơ bản).
3. Cập nhật tin đăng thành SOLD (listing-service)
   - API đề xuất: `PUT /listings/{id}/mark-sold`
   - Tác dụng: chuyển trạng thái ACTIVE → SOLD, ẩn khỏi public feed.
4. Ghi Transaction (transactions-service)
   - API: `POST /transactions`
   - Trường dữ liệu khuyến nghị:
     - transaction_type: `order_purchase` (buyer) / `order_sale` (seller)
     - user_id, partner_id, order_id
     - item_type, item_id, item_name, item_image (snapshot)
     - amount, fee, net_amount
     - payment_method, status (completed)
     - description/metadata (chứa snapshot sản phẩm và thông tin hợp đồng/hóa đơn nếu có)
5. Ghi timeline sự kiện (transactions-service)
   - API: `POST /transactions/{id}/events` với event_type: `created` → `paid` → `completed`.
6. Phân phối hiển thị
   - Buyer: gateway gọi `GET /transactions/user/{buyer_id}?tab=purchase` → "Lịch sử mua".
   - Seller: gateway gọi `GET /transactions/user/{seller_id}?tab=sale` → "Lịch sử bán".
   - Admin: `GET /transactions/admin/all` → thống kê, giám sát.

Ghi chú triển khai hiện tại:

- Đã có: tạo order sau khi simulate/payment completed (gateway → orders-service).
- Có sẵn: transactions-service (tạo transaction, lưu timeline, API theo user/admin).
- Cần nối thêm:
  - Sau payment completed → gateway tạo 2 bản ghi giao dịch: `order_purchase` (buyer) và `order_sale` (seller), kèm snapshot.
  - Gọi listing-service để mark SOLD tin đăng tương ứng.

---

## 4) JSON snapshot metadata (gợi ý)

```json
{
  "item": {
    "type": "car|battery",
    "id": 123,
    "name": "VinFast VF e34",
    "image": "/static/uploads/products/vfe34.jpg",
    "attributes": { "year": 2022, "mileage": 15000, "capacity_kwh": 42 }
  },
  "pricing": {
    "price": 385000000,
    "currency": "VND",
    "fee": 0,
    "net_amount": 385000000
  },
  "payment": {
    "method": "bank_transfer",
    "payment_id": 4,
    "contract_id": 7,
    "contract_code": "HD7"
  }
}
```

---

## 5) Pseudo-code tích hợp vào gateway sau payment completed

```python
# Sau khi xác minh payment completed trong /api/payment/callback/<payment_id>
for item in cart:
    # 1) Tạo order
    post(ORDERS_URL + "/orders", {
        buyer_id: user.sub,
        seller_id: item.seller_id,
        item_type: item.item_type,
        item_id: item.item_id,
        price: item.price,
        payment_id: payment_id
    })

    # 2) Gọi listing-service mark SOLD (nếu có API)
    put(LISTING_URL + f"/listings/{item.item_id}/mark-sold")

    # 3) Ghi transaction cho buyer (purchase) và seller (sale)
    snapshot = {...}  # như cấu trúc metadata ở trên
    for tx_type, u_id, p_id in (
        ("order_purchase", user.sub, item.seller_id),
        ("order_sale", item.seller_id, user.sub)
    ):
        post(TRANSACTIONS_URL + "/transactions", {
            transaction_type: tx_type,
            user_id: u_id,
            partner_id: p_id,
            order_id: created_order_id,
            item_type: item.item_type,
            item_id: item.item_id,
            item_name: item.item.name,
            item_image: item.item.main_image_url,
            amount: item.price,
            payment_method: "bank_transfer",
            status: "completed",
            metadata: snapshot
        })
```

---

## 6) KPI & báo cáo gợi ý

- Số sản phẩm bán ra theo thời gian/loại.
- Doanh thu gộp, doanh thu ròng (sau phí).
- Tỷ lệ hoàn tất thanh toán.
- Thời gian từ “đặt hàng” → “bán xong”.

---

Tài liệu này giúp thống nhất kỳ vọng chức năng và là checklist tích hợp giữa các service. Khi cần, có thể mở rộng webhook, thông báo đẩy, hoặc tự động sinh hóa đơn từ dữ liệu snapshot.
