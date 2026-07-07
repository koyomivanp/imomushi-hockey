# Summer MCP 接続確認（Windows / PowerShell）
$ErrorActionPreference = "Continue"

Write-Host "=== Summer MCP Diagnostics ===" -ForegroundColor Cyan

Write-Host "`n[1] Node.js"
node -v

Write-Host "`n[2] Doctor"
npx -y summer-engine@latest doctor

Write-Host "`n[3] Status"
npx -y summer-engine@latest status

Write-Host "`n[4] Summer.exe process"
$proc = Get-Process -Name "Summer" -ErrorAction SilentlyContinue
if ($proc) {
    $proc | Format-Table Id, ProcessName, StartTime -AutoSize
} else {
    Write-Host "  Summer.exe not running. Start from Start Menu or: npx -y summer-engine@latest run" -ForegroundColor Yellow
}

Write-Host "`n[5] Local API (localhost:6550)"
try {
    $token = Get-Content "$env:USERPROFILE\.summer\api-token" -Raw -ErrorAction Stop
    $headers = @{ Authorization = "Bearer $($token.Trim())" }
    $resp = Invoke-WebRequest -Uri "http://localhost:6550/v1/health" -Headers $headers -UseBasicParsing -TimeoutSec 5
    Write-Host "  OK: $($resp.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "  Not responding: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "  -> Open Summer Engine app and wait for it to finish loading." -ForegroundColor Yellow
}

Write-Host "`n[6] MCP config"
$userCfg = "$env:USERPROFILE\.cursor\mcp.json"
if (Test-Path $userCfg) {
    Write-Host "  User config: $userCfg"
    Get-Content $userCfg
} else {
    Write-Host "  Missing: $userCfg" -ForegroundColor Red
}

Write-Host "`n[7] MCP process smoke test"
$doctorOut = npx -y summer-engine@latest doctor 2>&1 | Out-String
if ($doctorOut -match "MCP Server\s+ready") {
    Write-Host "  OK: MCP Server ready (doctor)" -ForegroundColor Green
} else {
    Write-Host "  Check doctor output above" -ForegroundColor Yellow
}

Write-Host "`n[8] Image generation test (after Cursor restart)"
Write-Host "  In a NEW Cursor chat after MCP shows connected, ask:"
Write-Host '  "summer_generate_image で moss leaf icon を1枚生成して"'
Write-Host "  Success = image URL or file returned without auth error."

Write-Host "`n[9] Next steps"
Write-Host "  1. Summer Engine アプリを手動で開き、プロジェクトをロード（API :6550 が応答するまで待つ）"
Write-Host "  2. Cursor を完全終了して再起動"
Write-Host "  3. Settings > MCP > summer-engine が connected か確認（errored なら Restart）"
Write-Host "  4. 新チャットで summer_generate_image を試す"
