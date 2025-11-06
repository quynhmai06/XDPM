# Test Admin & Profile Endpoints

## 1. Tạo Admin (nếu chưa có)

```powershell
docker-compose exec auth_service python create_admin.py
```

## 2. Login để lấy token

```powershell
# PowerShell
$body = @{username="admin";password="admin123"} | ConvertTo-Json
$response = Invoke-RestMethod -Method Post -Uri http://localhost:5001/auth/login -Body $body -ContentType "application/json"
$token = $response.access_token
Write-Host "Token: $token"
```

## 3. Test Admin Endpoints (Auth Service)

### Get all users (admin only)

```powershell
$headers = @{Authorization="Bearer $token"}
Invoke-RestMethod -Uri http://localhost:5001/auth/admin/users -Headers $headers
```

### Update user status (admin only)

```powershell
$body = @{approved=$true;locked=$false} | ConvertTo-Json
Invoke-RestMethod -Method Patch -Uri http://localhost:5001/auth/admin/users/2/status -Headers $headers -Body $body -ContentType "application/json"
```

## 4. Test Profile Endpoints (Any User)

### Get my profile

```powershell
Invoke-RestMethod -Uri http://localhost:5001/auth/profile -Headers $headers
```

### Update profile

```powershell
$body = @{
    full_name="Nguyen Van A"
    address="123 ABC Street"
    phone="0123456789"
} | ConvertTo-Json
Invoke-RestMethod -Method Put -Uri http://localhost:5001/auth/profile -Headers $headers -Body $body -ContentType "application/json"
```

## 5. Test via Gateway (Web UI)

### Admin Dashboard

http://localhost:8000/admin

### User Profile

http://localhost:8000/profile

### Profile Edit

http://localhost:8000/profile/edit

## 6. Direct Admin-Service Endpoints (Future Use)

Admin-service vẫn chạy ở port 5002 cho tương lai mở rộng:

```powershell
# Stats overview (requires admin token)
Invoke-RestMethod -Uri http://localhost:5002/admin/stats/overview -Headers $headers

# Config fees
Invoke-RestMethod -Uri http://localhost:5002/admin/config/fees -Headers $headers
```

## Notes

- Admin credentials: admin / admin123
- JWT token hết hạn sau 6 giờ
- Auth-service (5001): Xử lý user, profile, admin user management
- Admin-service (5002): Reserved cho admin operations như stats, config, complaints
- Gateway (8000): Web UI tích hợp tất cả services
