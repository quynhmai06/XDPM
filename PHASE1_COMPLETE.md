# ✅ PHASE 1 HOÀN TẤT - HƯỚNG DẪN TEST

## 📊 Trạng thái hiện tại

**Đã merge từ nhánh quynhmai vào quynam:**

- ✅ Admin routes trong auth-service (quản lý users, approve, lock)
- ✅ Profile management (get/update profile, avatar upload)
- ✅ Email/phone normalization
- ✅ Admin UI templates (admin.html, profile pages)
- ✅ UserProfile model
- ✅ Tất cả services đang chạy

**Commit:** `1bcc0c7` - phase1(fix): merge admin logic from quynhmai

## 🌐 Links hoạt động

### Web UI

- **Trang chủ:** http://localhost:8000
- **Admin Dashboard:** http://localhost:8000/admin
- **Login:** http://localhost:8000/login
- **Register:** http://localhost:8000/register

### API Endpoints

**Auth Service (5001):**

- GET http://localhost:5001/auth/ - Health check
- POST http://localhost:5001/auth/register - Đăng ký
- POST http://localhost:5001/auth/login - Đăng nhập
- GET http://localhost:5001/auth/me - Thông tin user (cần token)
- GET http://localhost:5001/auth/admin/users - List users (cần admin token)
- PATCH http://localhost:5001/auth/users/{id}/status - Approve/lock user (admin)

**Admin Service (5002):** - Giữ lại cho tương lai mở rộng

- GET http://localhost:5002/health

**Other Services:**

- Listings: http://localhost:5003
- Favorites: http://localhost:5004
- Orders: http://localhost:5005
- Auctions: http://localhost:5006
- Reviews: http://localhost:5007
- Transactions: http://localhost:5008

## 🧪 Cách test Admin

### 1. Tạo user admin (nếu chưa có)

```powershell
docker-compose exec auth_service python create_admin.py
```

Credentials mặc định:

- Username: `admin`
- Password: `admin123`

### 2. Login qua Web UI

```
1. Mở http://localhost:8000/login
2. Nhập username: admin
3. Nhập password: admin123
4. Sau khi login thành công, vào http://localhost:8000/admin
```

### 3. Test Admin API với PowerShell

```powershell
# Login để lấy token
$loginBody = @{
    username = "admin"
    password = "admin123"
} | ConvertTo-Json

$loginResponse = Invoke-RestMethod -Method Post -Uri "http://localhost:5001/auth/login" -Body $loginBody -ContentType "application/json"
$token = $loginResponse.access_token

# List users
$headers = @{
    Authorization = "Bearer $token"
}
Invoke-RestMethod -Uri "http://localhost:5001/auth/admin/users" -Headers $headers

# Approve user (thay {id} bằng user ID thực)
$approveBody = @{status = "approved"} | ConvertTo-Json
Invoke-RestMethod -Method Patch -Uri "http://localhost:5001/auth/users/2/status" -Headers $headers -Body $approveBody -ContentType "application/json"
```

### 4. Test Profile Management

```powershell
# Register user mới
$registerBody = @{
    username = "testuser"
    email = "test@example.com"
    password = "test123"
    phone = "0901234567"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:5001/auth/register" -Body $registerBody -ContentType "application/json"

# Login với user mới (cần admin approve trước)
# ... (tương tự bước trên)

# Get profile
Invoke-RestMethod -Uri "http://localhost:5001/auth/profile" -Headers $headers

# Update profile
$profileBody = @{
    full_name = "Nguyễn Văn A"
    bio = "Test user"
} | ConvertTo-Json

Invoke-RestMethod -Method Put -Uri "http://localhost:5001/auth/profile" -Headers $headers -Body $profileBody -ContentType "application/json"
```

## ✨ Các tính năng đã merge từ quynhmai

### Auth Service

1. **Email/Phone Normalization:**
   - Email tự động lowercase
   - Phone chuẩn hóa (84 → 0, bỏ ký tự đặc biệt)
2. **Profile Management:**

   - GET/PUT /auth/profile - API
   - GET /auth/profile/page - HTML form
   - POST /auth/profile/update - Form submission
   - Avatar upload (png, jpg, jpeg, gif, webp)

3. **Admin Endpoints:**
   - GET /auth/admin/users - List tất cả users
   - PATCH /auth/users/{id}/status - Approve/lock user
   - Kiểm tra JWT role=admin

### Gateway

1. **Admin Dashboard:**

   - http://localhost:8000/admin
   - Hiển thị stats: số members, tin chờ duyệt, giao dịch
   - List users với approve/lock actions
   - Responsive design

2. **Templates:**
   - admin.html - Dashboard chính
   - profile.html - View profile
   - profile_edit.html - Edit profile form

## 🔧 Troubleshooting

### Gateway timeout

```powershell
docker-compose restart web_gateway
docker-compose logs web_gateway
```

### Auth service lỗi

```powershell
docker-compose logs auth_service
docker-compose exec auth_service python -c "from models import db; from app import app; app.app_context().push(); db.create_all(); print('DB OK')"
```

### Reset admin password

```powershell
docker-compose exec auth_service python -c "
from models import db, User
from werkzeug.security import generate_password_hash
from app import app
with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if admin:
        admin.password = generate_password_hash('admin123')
        db.session.commit()
        print('✅ Reset password thành công')
"
```

## 📝 Next Steps

### PHASE 2: Merge Pricing Service (trungquan)

- AI gợi ý giá dựa trên market data
- POST /pricing/suggest
- GET /pricing/market

### PHASE 3: Merge Payment Service (thanhdat)

- Momo, VNPay, Banking integration
- POST /payment/process
- GET /payment/callback

### PHASE 4: Merge Listing Features (trungquan)

- POST /vehicles/post - Form đăng tin xe
- POST /batteries/post - Form đăng tin pin
- Upload 10 ảnh

## 📊 Architecture hiện tại

```
┌─────────────────────────────────────────────────────────┐
│                    Gateway (8000)                       │
│  - UI: login, register, admin, profile                  │
│  - Proxy: forward requests to microservices             │
└────────────┬──────────────────────────────┬─────────────┘
             │                              │
    ┌────────▼────────┐          ┌─────────▼────────────┐
    │ Auth (5001)     │          │ Admin (5002)         │
    │ ✅ Merged from  │          │ - Reserved for future│
    │   quynhmai:     │          │ - API layer only     │
    │ • Admin routes  │          └──────────────────────┘
    │ • Profile mgmt  │
    │ • Normalize     │
    └─────────────────┘
             │
    ┌────────▼────────────────────────────────────────────┐
    │  Other Services (5003-5008)                         │
    │  - Listings, Favorites, Orders, Auctions            │
    │  - Reviews, Transactions                            │
    └─────────────────────────────────────────────────────┘
```

## ✅ Verified Working

- [x] Web gateway accessible at localhost:8000
- [x] Admin dashboard loads at /admin
- [x] Auth endpoints respond correctly
- [x] JWT token generation works
- [x] Admin user exists and can login
- [x] Profile management API available
- [x] All services healthy

**Status:** ✅ PHASE 1 COMPLETE - Ready for Phase 2
