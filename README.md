# XDPM - Nền tảng Giao dịch Xe điện & Pin cũ

[![Status](https://img.shields.io/badge/status-production_ready-success)]()
[![Version](https://img.shields.io/badge/version-1.0.0-blue)]()
[![Docker](https://img.shields.io/badge/docker-compose-2496ED)]()
[![Python](https://img.shields.io/badge/python-3.11-3776AB)]()
[![PostgreSQL](https://img.shields.io/badge/postgresql-15-336791)]()

> Nền tảng giao dịch thương mại điện tử chuyên sâu cho xe điện và pin cũ, kết nối người mua và người bán trên toàn quốc.

---

## 🚀 Tính năng chính

### 1. 🛒 Mua bán trực tiếp

- **Mua ngay**: Thanh toán nhanh chóng, không cần qua giỏ hàng
- **Giỏ hàng**: Lưu trữ nhiều sản phẩm, mua sau
- **Checkout**: Quy trình thanh toán đơn giản, an toàn
- **Đặt hàng**: Theo dõi trạng thái đơn hàng realtime

### 2. 🔨 Đấu giá

- **Tạo phiên đấu giá**: Người bán tự tạo phiên đấu giá cho sản phẩm
- **Đặt giá**: Hệ thống đấu giá công bằng, minh bạch
- **Buy Now**: Mua ngay với giá đặt trước
- **Hiển thị realtime**: Cập nhật giá và trạng thái liên tục

### 3. ❤️ Yêu thích & So sánh

- **Lưu yêu thích**: Đánh dấu sản phẩm quan tâm
- **So sánh chi tiết**: So sánh 2-5 sản phẩm cùng loại
- **Bảng so sánh**: Hiển thị đầy đủ thông số, giá cả

### 4. 🔍 Tìm kiếm nâng cao

- **Bộ lọc đa tiêu chí**: Hãng, năm, giá, km, dung lượng, vị trí
- **Search Service**: Elasticsearch-based search (port 5010)
- **Real-time results**: Kết quả cập nhật ngay lập tức

### 5. 🤖 AI Gợi ý giá

- **Pricing Service**: Sử dụng OpenAI GPT-4o-mini / Google Gemini
- **Logic riêng**:
  - Xe điện: Khấu hao 8%/năm + 12% theo quãng đường
  - Pin: Khấu hao 15-20%/năm theo dung lượng
- **Đề xuất thông minh**: Dựa trên thị trường thực tế

### 6. 📝 Quản lý tin đăng

- **Đăng tin**: Upload ảnh, mô tả chi tiết
- **AI pricing**: Gợi ý giá tự động
- **Admin duyệt**: Kiểm duyệt trước khi công khai

### 7. ⭐ Đánh giá & Reviews

- **Rating system**: 1-5 sao
- **Upload ảnh**: Review kèm hình ảnh thực tế
- **Reputation**: Xây dựng uy tín người bán

### 8. 📦 Quản lý đơn hàng

- **Lịch sử mua**: Theo dõi đơn hàng đã đặt
- **Lịch sử bán**: Quản lý đơn hàng người mua
- **Trạng thái**: Đang xử lý / Đã giao / Đã hủy

---

## 🏗️ Kiến trúc hệ thống

### Microservices Architecture

```
Gateway (Port 8000) - API Gateway & Frontend
├── Auth Service (5001) - Xác thực, phân quyền
├── Listing Service (5002) - CRUD sản phẩm
├── Pricing Service (5003) - AI gợi ý giá
├── Favorites Service (5004) - Yêu thích
├── Orders Service (5005) - Đơn hàng
├── Auctions Service (5006) - Đấu giá
├── Reviews Service (5007) - Đánh giá
├── Admin Service (5008) - Quản trị
├── Transactions Service (5009) - Giao dịch
└── Search Service (5010) - Tìm kiếm nâng cao
```

### Tech Stack

**Backend:**

- Python 3.11 + Flask
- PostgreSQL 15
- SQLAlchemy ORM
- JWT Authentication

**Frontend:**

- Jinja2 Templates
- Vanilla JavaScript
- CSS3 (Responsive)
- Font Awesome Icons

**AI/ML:**

- OpenAI GPT-4o-mini
- Google Gemini 2.5-flash
- Custom pricing algorithms

**Infrastructure:**

- Docker & Docker Compose
- Nginx (future)
- Redis (future - caching)

---

## 📦 Cài đặt & Chạy

### Yêu cầu hệ thống

- Docker Desktop
- Docker Compose
- 4GB RAM minimum
- 10GB disk space

### Khởi động nhanh

```powershell
# Clone repository
git clone https://github.com/quynhmai06/XDPM.git
cd XDPM

# Tạo file .env
@"
PROVIDER=openai
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-4o-mini
GOOGLE_API_KEY=your-google-key
GEMINI_MODEL=gemini-2.5-flash
SOFT_TIMEOUT=8
HARD_TIMEOUT=15
CACHE_TTL=600
"@ | Out-File -FilePath ".env" -Encoding UTF8

# Build và khởi động containers
docker-compose build
docker-compose up -d

# Kiểm tra trạng thái
docker-compose ps

# Xem logs
docker-compose logs -f web_gateway
```

### Truy cập

- **Website**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin

### Test tính năng

```powershell
# Chạy script test
.\test-features.ps1
```

---

## 📚 Documentation

### Tài liệu chi tiết

- [FEATURE_COMPLETE.md](./FEATURE_COMPLETE.md) - Tổng hợp tính năng đầy đủ
- [USER_GUIDE.md](./USER_GUIDE.md) - Hướng dẫn sử dụng cho người dùng
- [PHASE1_COMPLETE.md](./PHASE1_COMPLETE.md) - Phase 1 completion notes
- [TEST_ADMIN.md](./TEST_ADMIN.md) - Hướng dẫn test admin features
- [docs/PAYMENT_FLOW_4_STEPS.md](./docs/PAYMENT_FLOW_4_STEPS.md) - Quy trình thanh toán 4 bước
- [docs/TESTING_PAYMENT_FLOW.md](./docs/TESTING_PAYMENT_FLOW.md) - Hướng dẫn kiểm thử thanh toán
- [docs/FEATURE_sold_hide_and_transactions.md](./docs/FEATURE_sold_hide_and_transactions.md) - Sản phẩm bán xong → ẩn khỏi nền tảng → ghi lịch sử giao dịch

### API Documentation

```
GET  /api/listings/<id>          # Lấy thông tin sản phẩm
POST /api/listings/mine          # Tin đã đăng
POST /cart/add                   # Thêm vào giỏ
POST /cart/update                # Cập nhật giỏ
POST /cart/remove                # Xóa khỏi giỏ
POST /checkout/place             # Đặt hàng
GET  /api/favorites              # Danh sách yêu thích
POST /api/favorites              # Thêm yêu thích
DELETE /api/favorites/<id>       # Xóa yêu thích
GET  /api/auctions/active        # Đấu giá đang diễn ra
POST /api/auctions/<id>/bid      # Đặt giá
POST /api/auctions/<id>/buy-now  # Mua ngay
POST /api/orders                 # Tạo đơn hàng
GET  /api/orders/history         # Lịch sử đơn hàng
```

---

## 🧪 Testing

### Manual Testing Flow

**1. Test mua hàng:**

```
Đăng nhập → Tìm sản phẩm → Chi tiết → Mua ngay → Checkout → Hoàn tất
```

**2. Test giỏ hàng:**

```
Đăng nhập → Thêm vào giỏ → /cart → Cập nhật → Checkout
```

**3. Test đấu giá:**

```
Tạo phiên đấu giá → Xem trang chủ → Chi tiết → Đặt giá/Mua ngay
```

**4. Test yêu thích & so sánh:**

```
Thêm yêu thích → /favorites → Chọn 2-5 sp → So sánh → /compare
```

### Automated Tests

```powershell
# Smoke test
.\scripts\smoke-test.ps1

# Feature test
.\test-features.ps1

# Admin test
.\test_admin.ps1
```

---

## 🗂️ Cấu trúc thư mục

```
XDPM/
├── gateway/                 # Gateway service (Frontend + API Gateway)
│   ├── app.py              # Main application
│   ├── templates/          # Jinja2 templates
│   ├── static/             # CSS, JS, images
│   └── requirements.txt
├── auth-service/           # Authentication service
├── listing-service/        # Product listings CRUD
├── pricing-service/        # AI price suggestions
├── favorites-service/      # Favorites management
├── orders-service/         # Order management
├── auctions-service/       # Auction system
├── reviews-service/        # Reviews & ratings
├── admin-service/          # Admin panel
├── transactions-service/   # Transaction history
├── search-service/         # Advanced search
├── docker-compose.yml      # Docker orchestration
├── .env                    # Environment variables
├── README.md              # This file
├── FEATURE_COMPLETE.md    # Feature documentation
└── USER_GUIDE.md          # User manual
```

---

## 🔧 Configuration

### Environment Variables (.env)

```env
# AI Provider
PROVIDER=openai              # openai hoặc gemini
OPENAI_API_KEY=sk-xxx       # OpenAI API key
OPENAI_MODEL=gpt-4o-mini    # Model name
GOOGLE_API_KEY=xxx          # Google API key
GEMINI_MODEL=gemini-pro     # Gemini model

# Timeouts
SOFT_TIMEOUT=8              # Soft timeout (seconds)
HARD_TIMEOUT=15             # Hard timeout (seconds)
CACHE_TTL=600               # Cache TTL (seconds)
```

### Database

- **Type**: PostgreSQL 15
- **Name**: evdb
- **Port**: 5432
- **Schema**: Auto-created by SQLAlchemy

---

## 👥 Team & Contributors

- **Owner**: quynhmai06
- **Branch**: quynam
- **Developers**: Full-stack development team

---

## 📝 License

Copyright © 2025 XDPM. All rights reserved.

---

## 🆘 Support

### Báo lỗi

- GitHub Issues: [Create Issue](https://github.com/quynhmai06/XDPM/issues)

### Liên hệ

- Email: support@xdpm.vn
- Hotline: 1900-xxxx

---

## 🎯 Roadmap

### Phase 2 (Upcoming)

- [ ] Payment gateway integration (VNPay, Momo)
- [ ] Real-time chat between buyer/seller
- [ ] Mobile app (React Native)
- [ ] Push notifications
- [ ] Advanced analytics dashboard

### Phase 3 (Future)

- [ ] Machine learning recommendations
- [ ] Blockchain for transaction verification
- [ ] Multi-language support
- [ ] API marketplace

---

**Status**: ✅ Production Ready  
**Version**: 1.0.0  
**Last Updated**: November 3, 2025
