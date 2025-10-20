# Hướng dẫn tích hợp Đấu giá với Đăng bài

## Tổng quan

Chức năng đấu giá đã được xây dựng và sẵn sàng tích hợp với phần Đăng bài.

## Luồng hoạt động

### 1. Khi người dùng đăng bài (xe/pin)

Trong form đăng bài, thêm checkbox/option "Bán qua đấu giá" với các trường:

- **Giá khởi điểm** (starting_price): Bắt buộc
- **Giá mua ngay** (buy_now_price): Tùy chọn (nếu có thì hiện nút "Mua ngay")
- **Thời gian kết thúc** (ends_at): Bắt buộc

### 2. Backend endpoint đã có sẵn

#### Tạo phiên đấu giá

```
POST /auctions/create
Content-Type: application/x-www-form-urlencoded
hoặc gọi trực tiếp:
POST http://auctions_service:5006/auctions
Content-Type: application/json
```

**Payload:**

```json
{
  "item_type": "vehicle" | "battery",
  "item_id": 123,
  "seller_id": 1,
  "starting_price": 500000000,
  "buy_now_price": 800000000,  // tùy chọn
  "ends_at": "2025-12-31T23:59:59"  // ISO 8601 format
}
```

**Response:**

```json
{
  "id": 1,
  "item_type": "vehicle",
  "item_id": 123,
  "seller_id": 1,
  "starting_price": 500000000,
  "buy_now_price": 800000000,
  "status": "open",
  "created_at": "2025-10-20T10:00:00",
  "ends_at": "2025-12-31T23:59:59"
}
```

### 3. Các API endpoint khác

#### Lấy danh sách đấu giá đang hoạt động

```
GET /api/auctions/active
```

#### Lấy chi tiết một phiên đấu giá

```
GET /api/auctions/{auction_id}
```

#### Đặt giá

```
POST /api/auctions/{auction_id}/bid
Content-Type: application/json

{
  "amount": 550000000
}
```

#### Mua ngay

```
POST /api/auctions/{auction_id}/buy-now
```

- Tự động đóng phiên đấu giá
- Trả về thông tin item để thêm vào giỏ hàng
- Frontend tự động redirect user đến /cart

### 4. Database Schema

Bảng `auction` trong auctions-service:

```sql
CREATE TABLE auction (
    id INTEGER PRIMARY KEY,
    item_type TEXT NOT NULL,  -- 'vehicle' hoặc 'battery'
    item_id INTEGER NOT NULL,
    seller_id INTEGER NOT NULL,
    starting_price INTEGER NOT NULL,
    buy_now_price INTEGER,
    highest_bid INTEGER,
    status TEXT DEFAULT 'open',  -- 'open', 'closed', 'sold'
    created_at TIMESTAMP,
    ends_at TIMESTAMP
);
```

Bảng `bid`:

```sql
CREATE TABLE bid (
    id INTEGER PRIMARY KEY,
    auction_id INTEGER NOT NULL,
    bidder_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    created_at TIMESTAMP,
    FOREIGN KEY (auction_id) REFERENCES auction(id)
);
```

### 5. Cách tích hợp trong form Đăng bài

#### Option A: Checkbox riêng (Khuyến nghị)

```html
<div class="form-group">
  <label>
    <input type="checkbox" id="enableAuction" name="enable_auction" />
    Bán qua đấu giá
  </label>
</div>

<div id="auctionFields" style="display:none">
  <div class="form-group">
    <label>Giá khởi điểm (đ)</label>
    <input type="number" name="starting_price" min="0" />
  </div>

  <div class="form-group">
    <label>Giá mua ngay (đ) - Tùy chọn</label>
    <input type="number" name="buy_now_price" min="0" />
    <small>Để trống nếu chỉ đấu giá thông thường</small>
  </div>

  <div class="form-group">
    <label>Kết thúc lúc</label>
    <input type="datetime-local" name="ends_at_local" />
  </div>
</div>

<script>
  document.getElementById("enableAuction").addEventListener("change", (e) => {
    document.getElementById("auctionFields").style.display = e.target.checked
      ? "block"
      : "none";
  });
</script>
```

#### Option B: Dropdown loại bán

```html
<div class="form-group">
  <label>Hình thức bán</label>
  <select name="sale_type" id="saleType">
    <option value="direct">Bán trực tiếp</option>
    <option value="auction">Đấu giá</option>
  </select>
</div>
```

### 6. Backend xử lý khi submit form đăng bài

```python
@app.post('/listings/create')
def create_listing():
    user = get_current_user()
    if not user:
        return redirect(url_for('login_page'))

    # 1. Tạo listing trước (xe hoặc pin)
    item_type = request.form.get('item_type')  # 'vehicle' hoặc 'battery'
    listing_data = {
        'seller_id': user['sub'],
        # ... các field khác của xe/pin
    }

    if item_type == 'vehicle':
        r = requests.post(f"{LISTINGS_URL}/listings/vehicles", json=listing_data)
    else:
        r = requests.post(f"{LISTINGS_URL}/listings/batteries", json=listing_data)

    if not r.ok:
        flash('Đăng bài thất bại', 'error')
        return redirect(url_for('create_listing_page'))

    item_id = r.json().get('id')

    # 2. Nếu chọn đấu giá, tạo phiên đấu giá
    if request.form.get('enable_auction') or request.form.get('sale_type') == 'auction':
        auction_data = {
            'item_type': item_type,
            'item_id': item_id,
            'seller_id': user['sub'],
            'starting_price': int(request.form.get('starting_price', 0)),
            'buy_now_price': int(request.form.get('buy_now_price') or 0) or None,
            'ends_at': request.form.get('ends_at_local')
        }

        try:
            ar = requests.post(f"{AUCTIONS_URL}/auctions", json=auction_data, timeout=5)
            if ar.ok:
                flash('Đăng bài và tạo phiên đấu giá thành công!', 'success')
            else:
                flash('Đăng bài thành công nhưng tạo phiên đấu giá thất bại', 'warning')
        except Exception:
            flash('Đăng bài thành công nhưng không thể kết nối auctions service', 'warning')
    else:
        flash('Đăng bài thành công!', 'success')

    return redirect(url_for('my_listings'))
```

### 7. Hiển thị badge "Đấu giá" trên listing card

```html
<div class="product-card">
  {% if item.in_auction %}
  <div class="auction-badge"><i class="fas fa-gavel"></i> Đang đấu giá</div>
  {% endif %}
  <!-- ... nội dung card -->
</div>
```

Backend cần thêm endpoint để check xem item có đang trong phiên đấu giá không:

```python
@app.get('/api/listings/vehicles/<int:vid>')
def get_vehicle_detail(vid):
    # Lấy thông tin xe
    r = requests.get(f"{LISTINGS_URL}/listings/vehicles/{vid}")
    vehicle = r.json()

    # Check xem có đang đấu giá không
    try:
        ar = requests.get(f"{AUCTIONS_URL}/auctions/active")
        if ar.ok:
            auctions = ar.json().get('data', [])
            vehicle['in_auction'] = any(
                a['item_type'] == 'vehicle' and
                a['item_id'] == vid and
                a['status'] == 'open'
                for a in auctions
            )
            # Tìm auction_id nếu có
            for a in auctions:
                if a['item_type'] == 'vehicle' and a['item_id'] == vid:
                    vehicle['auction_id'] = a['id']
                    vehicle['auction'] = a
                    break
    except Exception:
        vehicle['in_auction'] = False

    return vehicle
```

### 8. UI Flow cho người dùng

#### Người bán (Đăng bài):

1. Vào trang "Đăng bài mới"
2. Điền thông tin xe/pin
3. Tick "Bán qua đấu giá"
4. Nhập giá khởi điểm, giá mua ngay (option), thời gian kết thúc
5. Submit → Tạo cả listing và phiên đấu giá

#### Người mua:

1. Vào trang "Đấu giá" → Thấy danh sách phiên đang mở
2. Click vào phiên → Xem chi tiết
3. Chọn "Đấu giá" (nhập giá) HOẶC "Mua ngay" (nếu có)
4. Nếu Mua ngay → Tự động vào giỏ hàng → Thanh toán

### 9. Service URLs (cho reference)

```python
# gateway/app.py
AUCTIONS_URL = os.getenv("AUCTIONS_URL", "http://127.0.0.1:5006")

# docker-compose.yml
auctions_service:
  ports:
    - "5006:5006"
  environment:
    - DATABASE_URL=sqlite:///instance/auctions.db
```

### 10. Test data script

Đã có sẵn `scripts/seed-auctions.ps1` để tạo data mẫu.

## Notes

- Endpoint `/auctions/create` trong gateway vẫn giữ nguyên để test, nhưng production sẽ gọi từ form Đăng bài
- Frontend tự động xử lý flow "Mua ngay" → Cart → Checkout
- Phiên đấu giá tự động đóng khi hết hạn (cần thêm cronjob/scheduler nếu cần)
- Chỉ seller mới được tạo phiên đấu giá cho item của mình

## TODO khi tích hợp

- [ ] Thêm checkbox "Đấu giá" vào form đăng bài
- [ ] Backend gọi API tạo auction sau khi tạo listing thành công
- [ ] Thêm badge "Đang đấu giá" trên listing card
- [ ] Link từ listing detail → auction detail nếu đang đấu giá
- [ ] Ẩn nút "Mua trực tiếp" nếu item đang trong phiên đấu giá open
