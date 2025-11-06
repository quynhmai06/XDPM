#requires -Version 5.1
$ErrorActionPreference = 'Stop'

function Invoke-JsonPost($url, $body) {
  $json = $body | ConvertTo-Json -Depth 5
  return Invoke-RestMethod -Method Post -Uri $url -Body $json -ContentType 'application/json'
}

Write-Host '=== Fetch listings via gateway ==='
$vehicles = Invoke-RestMethod -Uri 'http://localhost:8000/api/search/vehicles'
$batteries = Invoke-RestMethod -Uri 'http://localhost:8000/api/search/batteries'
$vid = if ($vehicles.items.Count -gt 0) { $vehicles.items[0].id } else { 1 }
$bid = if ($batteries.items.Count -gt 0) { $batteries.items[0].id } else { 1 }

Write-Host '=== Create auctions directly on auctions_service ==='
$end1 = (Get-Date).ToUniversalTime().AddMinutes(30).ToString('s')
$end2 = (Get-Date).ToUniversalTime().AddMinutes(40).ToString('s')
$null = Invoke-JsonPost 'http://localhost:5006/auctions' @{ item_type='vehicle'; item_id=$vid; seller_id=1; starting_price=45000000; buy_now_price=55000000; ends_at=$end1 }
$null = Invoke-JsonPost 'http://localhost:5006/auctions' @{ item_type='battery'; item_id=$bid; seller_id=1; starting_price=5000000; buy_now_price=6500000; ends_at=$end2 }

Write-Host '=== Verify via gateway ==='
$active = Invoke-RestMethod -Uri 'http://localhost:8000/api/auctions/active'
$active | ConvertTo-Json -Depth 6 | Write-Output
