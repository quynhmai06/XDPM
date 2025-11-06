# Script test các tính năng chính của XDPM

Write-Host "=== XDPM Feature Test Script ===" -ForegroundColor Cyan
Write-Host ""

# Base URLs
$gateway = "http://localhost:8000"
$headers = @{
    "Content-Type" = "application/json"
}

# Test 1: Gateway Health Check
Write-Host "[1] Testing Gateway..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri $gateway -Method GET -TimeoutSec 5
    Write-Host "✅ Gateway OK (Status: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "❌ Gateway Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 2: Listings (Products)
Write-Host "`n[2] Testing Listings..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$gateway/api/listings/mine" -Method GET -Headers $headers -TimeoutSec 5
    Write-Host "✅ Listings API OK" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Listings requires authentication" -ForegroundColor Yellow
}

# Test 3: Auctions
Write-Host "`n[3] Testing Auctions..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$gateway/api/auctions/active" -Method GET -Headers $headers -TimeoutSec 5
    $count = if ($response.data) { $response.data.Count } elseif ($response -is [array]) { $response.Count } else { 0 }
    Write-Host "✅ Auctions API OK - Found $count active auctions" -ForegroundColor Green
} catch {
    Write-Host "❌ Auctions Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 4: Cart
Write-Host "`n[4] Testing Cart..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$gateway/cart" -Method GET -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Cart Page OK" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Cart Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 5: Checkout
Write-Host "`n[5] Testing Checkout..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$gateway/checkout" -Method GET -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Checkout Page OK" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Checkout Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 6: Favorites
Write-Host "`n[6] Testing Favorites..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$gateway/favorites" -Method GET -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Favorites Page OK" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Favorites Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 7: Compare
Write-Host "`n[7] Testing Compare..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$gateway/compare" -Method GET -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Compare Page OK" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Compare Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 8: Auctions Pages
Write-Host "`n[8] Testing Auctions Pages..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$gateway/auctions" -Method GET -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Auctions Page OK" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Auctions Page Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 9: Transactions
Write-Host "`n[9] Testing Transactions..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$gateway/transactions" -Method GET -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Transactions Page OK" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Transactions Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 10: Reviews
Write-Host "`n[10] Testing Reviews..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$gateway/reviews" -Method GET -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Reviews Page OK" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Reviews Failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n=== Test Summary ===" -ForegroundColor Cyan
Write-Host "All critical endpoints tested!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Login at: $gateway/login" -ForegroundColor White
Write-Host "2. Browse products at: $gateway/" -ForegroundColor White
Write-Host "3. Test buying flow: Product → Add to Cart → Checkout" -ForegroundColor White
Write-Host "4. Test auction flow: Create Auction → Place Bid → Buy Now" -ForegroundColor White
Write-Host ""
