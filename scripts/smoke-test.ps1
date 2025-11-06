#requires -Version 5.1
$ErrorActionPreference = 'Stop'

function Invoke-JsonPost($url, $body, $headers=@{}) {
  $json = $body | ConvertTo-Json -Depth 5
  return Invoke-RestMethod -Method Post -Uri $url -Headers $headers -Body $json -ContentType 'application/json'
}

Write-Host '=== Health checks ==='
Invoke-RestMethod http://localhost:8000/api/search/vehicles | Out-Null

# Admin login to approve user later
$adminLogin = Invoke-JsonPost 'http://localhost:5001/auth/login' @{ username='admin'; password='12345' }
$adminToken = $adminLogin.access_token

# Register test user (ignore if exists)
try { $null = Invoke-JsonPost 'http://localhost:5001/auth/register' @{ username='tester'; email='t@ex.com'; password='test123' } } catch {}

# Approve tester
$headersAdmin = @{ Authorization = "Bearer $adminToken" }
$users = Invoke-RestMethod -Uri 'http://localhost:5001/auth/admin/users' -Headers $headersAdmin
$tester = $users.data | Where-Object { $_.username -eq 'tester' } | Select-Object -First 1
if (-not $tester) { throw 'tester not found' }
$null = Invoke-RestMethod -Method Patch -Uri "http://localhost:5001/auth/users/$($tester.id)/status" -Headers $headersAdmin -ContentType 'application/json' -Body '{"status":"approved"}'

# Tester login to get JWT
$login = Invoke-JsonPost 'http://localhost:5001/auth/login' @{ username='tester'; password='test123' }
$token = $login.access_token
$headers = @{ Authorization = "Bearer $token" }

Write-Host '=== Seed one listing ==='
try {
  $veh = Invoke-JsonPost 'http://localhost:5003/listings/vehicles' @{ brand='Vinfast'; model='VF8'; year=2023; km=5000; price=45000; condition='used'; battery_capacity=87.7; seller_id=$tester.id }
  $vehId = $veh.id
} catch {
  # if endpoint requires unique, ignore
}

Write-Host '=== Search vehicles via gateway ==='
$search = Invoke-RestMethod -Uri 'http://localhost:8000/api/search/vehicles?brand=Vin'
$firstId = if ($search.items.Count -gt 0) { $search.items[0].id } else { 1 }

Write-Host '=== Favorites add & list ==='
$null = Invoke-JsonPost 'http://localhost:8000/api/favorites' @{ item_type='vehicle'; item_id=$firstId } -headers $headers
$favs = Invoke-RestMethod -Uri 'http://localhost:8000/api/favorites' -Headers $headers
$favs | ConvertTo-Json -Depth 5 | Write-Output

Write-Host '=== Orders create & history ==='
$null = Invoke-JsonPost 'http://localhost:8000/api/orders' @{ seller_id=1; item_type='vehicle'; item_id=$firstId; price=42000 } -headers $headers
$hist = Invoke-RestMethod -Uri 'http://localhost:8000/api/orders/history' -Headers $headers
$hist | ConvertTo-Json -Depth 5 | Write-Output

Write-Host '=== Reviews create & list ==='
$null = Invoke-JsonPost 'http://localhost:8000/api/reviews' @{ target_user_id=1; rating=5; comment='Great seller' } -headers $headers
$r = Invoke-RestMethod -Uri 'http://localhost:8000/api/reviews/user/1' -Headers $headers
$r | ConvertTo-Json -Depth 5 | Write-Output

Write-Host 'All smoke tests executed.'