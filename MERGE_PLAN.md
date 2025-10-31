# 📋 KẾ HOẠCH MERGE CODE - XDPM

**Ngày:** 31/10/2025  
**Người thực hiện:** quynam (lead)  
**Mục tiêu:** Merge code từ 4 nhánh thành 1 web hoàn chỉnh

---

## 🔍 PHÂN TÍCH CÁC NHÁNH

### **1. NHÁNH QUYNAM** (BASE - 9 services)

```
quynam/
├── auth-service (5001)          ✅ Xác thực JWT
├── admin-service (5002)         ✅ Quản trị (chưa đầy đủ)
├── listings-service (5003)      ✅ Xe/Pin listings (search, CRUD)
├── favorites-service (5004)     ✅ Yêu thích
├── orders-service (5005)        ✅ Đơn hàng, giỏ hàng
├── auctions-service (5006)      ✅ Đấu giá với countdown
├── reviews-service (5007)       ✅ Đánh giá 2 chiều
├── transactions-service (5008)  ✅ Lịch sử giao dịch + timeline
└── gateway (8000)               ✅ API Gateway + UI
```

**Tính năng đầy đủ:**

- ✅ Tìm kiếm đa tiêu chí (brand, model, year, km, price, condition, battery_capacity)
- ✅ Yêu thích, so sánh sản phẩm
- ✅ Đấu giá real-time với countdown timer
- ✅ Mua ngay + giỏ hàng
- ✅ Đánh giá đa tiêu chí (professionalism, payment, product, cooperation, overall)
- ✅ Lịch sử giao dịch 3 tabs (Mua/Bán/Ví) + timeline
- ✅ Microservices architecture hoàn chỉnh

**Thiếu:**

- ❌ Form đăng tin bán xe/pin (Member đăng bán)
- ❌ AI gợi ý giá
- ❌ Thanh toán online (e-wallet, banking)
- ❌ Admin routes đầy đủ (users, posts, stats management)

---

### **2. NHÁNH QUYNHMAI** (Admin features)

```
quynhmai/
├── admin-service/
│   ├── routes/
│   │   ├── users.py      ✅ Quản lý users (approve, lock, stats)
│   │   ├── posts.py      ✅ Quản lý tin đăng (kiểm duyệt, spam filter)
│   │   ├── stats.py      ✅ Thống kê (users, transactions, revenue)
│   │   ├── transactions.py ✅ Quản lý giao dịch, khiếu nại
│   │   └── config.py     ✅ Cấu hình phí, hoa hồng
│   └── models.py         (Users, Posts, Transactions extended)
├── auth-service/
│   └── routes_oauth.py   ✅ OAuth (Google, Facebook login)
└── gateway/
    └── templates/admin.html ✅ Admin dashboard UI
```

**Tính năng:**

- ✅ **Admin Dashboard:** Quản lý users, posts, transactions
- ✅ **OAuth Login:** Đăng nhập qua Google, Facebook
- ✅ **Statistics:** Doanh thu, xu hướng thị trường
- ✅ **Content Moderation:** Kiểm duyệt, lọc spam, gắn nhãn "đã kiểm định"
- ✅ **Fee Management:** Thiết lập phần trăm phí, hoa hồng

**Cần merge vào quynam:**

- ✅ admin-service/routes/\* → Merge tất cả routes vào admin-service
- ✅ auth-service/routes_oauth.py → Thêm OAuth vào auth-service
- ✅ gateway/templates/admin.html → Update admin UI

---

### **3. NHÁNH THANHDAT** (Payment + Similar services)

```
thanhdat/
├── payment-service (NEW!)       🆕 Thanh toán online
│   ├── models.py                (Payment, PaymentMethod, Transaction)
│   ├── routes.py                (Momo, VNPay, Banking, E-wallet)
│   └── payment_gateways/
│       ├── momo.py
│       ├── vnpay.py
│       └── banking.py
├── auctions-service             (Trùng với quynam)
├── favorites-service            (Trùng với quynam)
├── listings-service             (Trùng với quynam)
└── orders-service               (Trùng với quynam)
```

**Tính năng:**

- 🆕 **Payment Service:** Thanh toán online (Momo, VNPay, Banking, E-wallet)
- 🆕 **Payment Methods:** Quản lý phương thức thanh toán
- 🆕 **Payment History:** Lịch sử thanh toán chi tiết
- ⚠️ Các services khác trùng với quynam → Không merge

**Cần merge vào quynam:**

- ✅ payment-service/ → Thêm service mới (port 5009)
- ❌ Các services khác → BỎ QUA (đã có trong quynam)

---

### **4. NHÁNH TRUNGQUAN** (Đăng tin + AI Pricing)

```
trungquan/
├── listing-service/             🆕 Đăng tin bán xe/pin
│   ├── models.py                (VehicleListing, BatteryListing tách riêng)
│   ├── routes.py
│   │   ├── POST /vehicles/post  ✅ Form đăng xe
│   │   ├── POST /batteries/post ✅ Form đăng pin
│   │   └── File upload          ✅ Upload 10 ảnh
│   └── templates/
│       ├── post_vehicle.html
│       └── post_battery.html
├── pricing-service/             🆕 AI gợi ý giá
│   ├── models.py                (PriceHistory, MarketTrend)
│   ├── routes.py
│   │   ├── POST /pricing/suggest ✅ AI suggest price
│   │   └── GET /pricing/market   ✅ Market trend analysis
│   └── ai_model.py              (OpenAI/Local model)
├── auth-service                 (Trùng)
└── gateway                      (Trùng)
```

**Tính năng:**

- 🆕 **Post Listing:** Form đăng tin bán xe/pin với upload ảnh
- 🆕 **AI Pricing:** Gợi ý giá bán dựa trên:
  - Thông số xe/pin (brand, model, year, km, battery_health)
  - Dữ liệu thị trường (PriceHistory)
  - Xu hướng giá (MarketTrend)
- 🆕 **Separate Forms:** Xe và Pin tách riêng UI
- 🆕 **Market Analysis:** Thống kê xu hướng giá

**Cần merge vào quynam:**

- ✅ listing-service/routes.py POST methods → Merge vào listings-service
- ✅ pricing-service/ → Thêm service mới (port 5010)
- ✅ gateway/templates/post\_\*.html → Thêm vào gateway/templates
- ❌ auth-service, gateway khác → BỎ QUA

---

## 🎯 CHIẾN LƯỢC MERGE

### **PHASE 1: Merge Admin Features (quynhmai)**

**Mục tiêu:** Hoàn thiện admin-service và OAuth login

**Bước 1: Merge admin-service**

```bash
# Checkout files từ quynhmai
git checkout quynhmai -- admin-service/routes/
git checkout quynhmai -- admin-service/models.py
git checkout quynhmai -- gateway/templates/admin.html
```

**Conflicts dự kiến:**

- `admin-service/routes.py` → Merge 2 file (import routes từ routes/)
- `admin-service/models.py` → Merge models (User, Post, Transaction extended)

**Bước 2: Merge OAuth**

```bash
git checkout quynhmai -- auth-service/routes_oauth.py
git checkout quynhmai -- gateway/.venv/Lib/site-packages/authlib/
```

**Update auth-service/app.py:**

```python
from routes_oauth import oauth_bp
app.register_blueprint(oauth_bp, url_prefix='/oauth')
```

**Update gateway/app.py:**

```python
# Add OAuth routes
@app.route('/login/google')
@app.route('/login/facebook')
@app.route('/auth/callback')
```

---

### **PHASE 2: Merge Payment Service (thanhdat)**

**Mục tiêu:** Thêm thanh toán online

**Bước 1: Copy payment-service**

```bash
git checkout thanhdat -- payment-service/
```

**Bước 2: Update docker-compose.yml**

```yaml
payment_service:
  build: ./payment-service
  environment:
    DATABASE_URL: postgresql+psycopg2://ev:evpass@db:5432/evdb
    MOMO_API_KEY: ${MOMO_API_KEY}
    VNPAY_API_KEY: ${VNPAY_API_KEY}
  depends_on: [db]
  ports: ["5009:5009"]
```

**Bước 3: Update gateway/app.py**

```python
PAYMENT_URL = os.getenv('PAYMENT_URL', 'http://payment_service:5009')

@app.route('/payment/methods')
@app.route('/payment/process')
@app.route('/payment/callback')
```

---

### **PHASE 3: Merge Listing + AI Pricing (trungquan)**

**Mục tiêu:** Thêm form đăng tin và AI gợi ý giá

**Bước 1: Merge POST listing routes**

```bash
# Lấy routes POST từ trungquan
git show trungquan:listing-service/routes.py > temp_routes.py
# Manual merge vào listings-service/routes.py
```

**Update listings-service/routes.py:**

```python
# Add POST methods
@app.route('/vehicles/post', methods=['POST'])
def post_vehicle():
    # Form đăng xe với file upload

@app.route('/batteries/post', methods=['POST'])
def post_battery():
    # Form đăng pin với file upload
```

**Bước 2: Copy pricing-service**

```bash
git checkout trungquan -- pricing-service/
```

**Bước 3: Update docker-compose.yml**

```yaml
pricing_service:
  build: ./pricing-service
  environment:
    DATABASE_URL: postgresql+psycopg2://ev:evpass@db:5432/evdb
    OPENAI_API_KEY: ${OPENAI_API_KEY}
  depends_on: [db]
  ports: ["5010:5010"]
```

**Bước 4: Copy post templates**

```bash
git checkout trungquan -- gateway/templates/post_vehicle.html
git checkout trungquan -- gateway/templates/post_battery.html
```

**Update gateway/app.py:**

```python
PRICING_URL = os.getenv('PRICING_URL', 'http://pricing_service:5010')

@app.route('/post/vehicle')
@app.route('/post/battery')
@app.route('/api/pricing/suggest')
```

---

### **PHASE 4: Integration & Testing**

**Bước 1: Update docker-compose.yml**

```yaml
services:
  db: ...
  auth_service: ...
  admin_service: ...
  listings_service: ...
  favorites_service: ...
  orders_service: ...
  auctions_service: ...
  reviews_service: ...
  transactions_service: ...
  payment_service: # 🆕 NEW
  pricing_service: # 🆕 NEW
  web_gateway:
    environment:
      # ... existing URLs ...
      PAYMENT_URL: http://payment_service:5009
      PRICING_URL: http://pricing_service:5010
```

**Bước 2: Test flow hoàn chỉnh**

```
1. Register → Login (Email/Google/Facebook)
2. Post Vehicle/Battery → AI Suggest Price
3. Create Auction → Real-time Countdown
4. Buy Now → Add to Cart → Checkout
5. Payment → Momo/VNPay/Banking
6. Review → 5-criteria rating
7. Transaction History → 3 tabs + timeline
8. Admin → Manage users, posts, stats
```

---

## 📊 KẾT QUẢ SAU MERGE

### **Architecture Hoàn Chỉnh (11 Services)**

```
XDPM/
├── auth-service (5001)          ✅ JWT + OAuth (Google, Facebook)
├── admin-service (5002)         ✅ Full admin features
├── listings-service (5003)      ✅ Search + Post listings
├── favorites-service (5004)     ✅ Favorites
├── orders-service (5005)        ✅ Orders + Cart
├── auctions-service (5006)      ✅ Auctions + Countdown
├── reviews-service (5007)       ✅ 2-way reviews
├── transactions-service (5008)  ✅ Transaction history
├── payment-service (5009)       🆕 Online payment
├── pricing-service (5010)       🆕 AI pricing
└── gateway (8000)               ✅ API Gateway + Full UI
```

### **Tính Năng Hoàn Chỉnh 100%**

**1. Member Features ✅**

- ✅ Đăng ký/đăng nhập (Email, Google, Facebook)
- ✅ Quản lý hồ sơ (profile, avatar, listings, transactions)
- ✅ Đăng tin bán xe/pin (Form tách riêng, upload 10 ảnh)
- ✅ AI gợi ý giá bán (dựa trên market data)
- ✅ Tìm kiếm đa tiêu chí (brand, model, year, km, price, condition)
- ✅ Yêu thích + So sánh (max 4 products)
- ✅ Đấu giá + Mua ngay
- ✅ Thanh toán online (Momo, VNPay, Banking, E-wallet)
- ✅ Ký hợp đồng số hóa (PDF contract)
- ✅ Đánh giá 2 chiều (5 criteria)
- ✅ Lịch sử giao dịch (3 tabs + timeline)

**2. Admin Features ✅**

- ✅ Quản lý users (approve, lock, stats)
- ✅ Quản lý tin đăng (kiểm duyệt, spam filter, gắn nhãn "đã kiểm định")
- ✅ Quản lý giao dịch (theo dõi, xử lý khiếu nại)
- ✅ Quản lý phí & hoa hồng (thiết lập %, tracking)
- ✅ Thống kê & Báo cáo (users, transactions, revenue, market trends)

---

## ⚠️ LƯU Ý QUAN TRỌNG

### **Conflicts Có Thể Xảy Ra**

1. **docker-compose.yml**

   - Conflict: Services configuration
   - Giải pháp: Merge manual, giữ tất cả services, cập nhật ports

2. **gateway/app.py**

   - Conflict: Routes registration
   - Giải pháp: Merge manual, thêm tất cả routes mới

3. **listings-service/routes.py**

   - Conflict: GET vs POST methods
   - Giải pháp: Merge manual, giữ cả GET (search) và POST (create)

4. **admin-service/models.py**
   - Conflict: Model definitions
   - Giải pháp: Merge manual, extend existing models

### **Dependencies Cần Thêm**

```bash
# payment-service
pip install requests python-dotenv stripe momo-sdk vnpay-sdk

# pricing-service
pip install openai scikit-learn pandas numpy
```

### **Environment Variables Mới**

```env
# OAuth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
FACEBOOK_APP_ID=...
FACEBOOK_APP_SECRET=...

# Payment
MOMO_API_KEY=...
VNPAY_API_KEY=...
BANKING_API_KEY=...

# AI Pricing
OPENAI_API_KEY=...
```

---

## 🚀 LỆNH MERGE STEP-BY-STEP

```bash
# BƯỚC 1: Backup nhánh hiện tại
git checkout quynam
git branch quynam-backup

# BƯỚC 2: Merge admin features
git checkout quynhmai -- admin-service/routes/
git checkout quynhmai -- auth-service/routes_oauth.py
git checkout quynhmai -- gateway/templates/admin.html
git add .
git commit -m "Merge: Admin features from quynhmai"

# BƯỚC 3: Merge payment service
git checkout thanhdat -- payment-service/
git add .
git commit -m "Merge: Payment service from thanhdat"

# BƯỚC 4: Merge listing + pricing
git checkout trungquan -- pricing-service/
git checkout trungquan -- gateway/templates/post_vehicle.html
git checkout trungquan -- gateway/templates/post_battery.html
# Manual merge listing routes
git add .
git commit -m "Merge: Listing posts & AI pricing from trungquan"

# BƯỚC 5: Update docker-compose
# Edit docker-compose.yml manually
git add docker-compose.yml
git commit -m "Update: Add payment & pricing services to docker-compose"

# BƯỚC 6: Test
docker-compose down
docker-compose up --build -d
```

---

**Status:** ⏳ READY TO MERGE  
**Next Action:** Execute merge commands step by step
