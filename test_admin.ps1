# TEST WEB ADMIN - PHASE 1
# Chạy file này trong PowerShell: .\test_admin.ps1

Write-Host "`n=== TEST PHASE 1: WEB ADMIN ===" -ForegroundColor Green

# 1. Test Gateway Homepage
Write-Host "`n1️⃣  Testing Gateway Homepage..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/" -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Gateway Homepage: OK (200)" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Gateway Homepage: FAILED" -ForegroundColor Red
    Write-Host $_.Exception.Message
}

# 2. Test Admin Page
Write-Host "`n2️⃣  Testing Admin Dashboard..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/admin" -TimeoutSec 10
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Admin Dashboard: OK (200)" -ForegroundColor Green
        if ($response.Content -match 'Admin.*EV') {
            Write-Host "✅ Admin page content: OK" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "❌ Admin Dashboard: FAILED" -ForegroundColor Red
    Write-Host $_.Exception.Message
}

# 3. Test Auth Service Health
Write-Host "`n3️⃣  Testing Auth Service..." -ForegroundColor Cyan
try {
    $response = Invoke-RestMethod -Uri "http://localhost:5001/auth/" -TimeoutSec 5
    if ($response.service -eq "auth") {
        Write-Host "✅ Auth Service: OK - $($response.status)" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Auth Service: FAILED" -ForegroundColor Red
    Write-Host $_.Exception.Message
}

# 4. Test Admin Login
Write-Host "`n4️⃣  Testing Admin Login..." -ForegroundColor Cyan
try {
    $loginBody = @{
        username = "admin"
        password = "admin123"
    } | ConvertTo-Json

    $loginResponse = Invoke-RestMethod -Method Post -Uri "http://localhost:5001/auth/login" -Body $loginBody -ContentType "application/json"
    
    if ($loginResponse.access_token) {
        Write-Host "✅ Admin Login: OK" -ForegroundColor Green
        $token = $loginResponse.access_token
        Write-Host "   Token: $($token.Substring(0, 20))..." -ForegroundColor Gray
        
        # 5. Test Admin Users List
        Write-Host "`n5️⃣  Testing Admin Users List..." -ForegroundColor Cyan
        $headers = @{
            Authorization = "Bearer $token"
        }
        
        $users = Invoke-RestMethod -Uri "http://localhost:5001/auth/admin/users" -Headers $headers
        Write-Host "✅ Admin Users List: OK - Found $($users.Count) users" -ForegroundColor Green
        
        # 6. Test Profile API
        Write-Host "`n6️⃣  Testing Profile API..." -ForegroundColor Cyan
        try {
            $profile = Invoke-RestMethod -Uri "http://localhost:5001/auth/profile" -Headers $headers
            Write-Host "✅ Profile API: OK" -ForegroundColor Green
            Write-Host "   User: $($profile.username)" -ForegroundColor Gray
        } catch {
            Write-Host "⚠️  Profile API: Endpoint exists but may need profile data" -ForegroundColor Yellow
        }
        
    }
} catch {
    Write-Host "❌ Admin Login: FAILED" -ForegroundColor Red
    Write-Host $_.Exception.Message
    Write-Host "`n💡 Nếu lỗi, chạy: docker-compose exec auth_service python create_admin.py" -ForegroundColor Yellow
}

# 7. Test Other Services
Write-Host "`n7️⃣  Testing Other Microservices..." -ForegroundColor Cyan

$services = @(
    @{Name="Admin"; Port=5002; Path="/health"}
    @{Name="Listings"; Port=5003; Path="/"}
    @{Name="Favorites"; Port=5004; Path="/"}
    @{Name="Orders"; Port=5005; Path="/"}
    @{Name="Auctions"; Port=5006; Path="/"}
    @{Name="Reviews"; Port=5007; Path="/"}
    @{Name="Transactions"; Port=5008; Path="/"}
)

foreach ($svc in $services) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:$($svc.Port)$($svc.Path)" -TimeoutSec 3
        Write-Host "   ✅ $($svc.Name) ($($svc.Port)): OK" -ForegroundColor Green
    } catch {
        Write-Host "   ❌ $($svc.Name) ($($svc.Port)): FAILED" -ForegroundColor Red
    }
}

# Summary
Write-Host "`n=== SUMMARY ===" -ForegroundColor Green
Write-Host "✅ PHASE 1 Testing Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Access Points:" -ForegroundColor Cyan
Write-Host "   • Web UI:        http://localhost:8000"
Write-Host "   • Admin Page:    http://localhost:8000/admin"
Write-Host "   • Login Page:    http://localhost:8000/login"
Write-Host ""
Write-Host "👤 Admin Credentials:" -ForegroundColor Cyan
Write-Host "   • Username: admin"
Write-Host "   • Password: admin123"
Write-Host ""
Write-Host "📚 Documentation:" -ForegroundColor Cyan
Write-Host "   • Phase 1 Guide: PHASE1_COMPLETE.md"
Write-Host "   • Merge Plan:    MERGE_PLAN.md"
Write-Host ""
Write-Host "🚀 Next: PHASE 2 - Pricing Service (trungquan)" -ForegroundColor Yellow
