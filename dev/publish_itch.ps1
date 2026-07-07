# itch.io へ Windows ビルドを push（butler）
# 使い方:
#   $env:BUTLER_API_KEY = "itch.io で発行した API キー"
#   .\dev\publish_itch.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$User = "koyomivanp"
$Game = "imomushi-hockey"
$Channel = "windows"
$Zip = Join-Path $Root "itch\release\ImomushiHockey-win64.zip"
$ButlerDir = Join-Path $Root "itch\tools\butler"

if (-not $env:BUTLER_API_KEY) {
    Write-Host "BUTLER_API_KEY が未設定です。"
    Write-Host "https://itch.io/user/settings/api-keys でキーを発行し、"
    Write-Host '  $env:BUTLER_API_KEY = "..."' 
    Write-Host "を実行してから再試行してください。"
    Write-Host ""
    Write-Host "手動アップロード: itch\README.md を参照"
    exit 1
}

if (-not (Test-Path $Zip)) {
    Write-Host "ZIP がありません: $Zip"
    Write-Host "先に build.ps1 または README のビルド手順を実行してください。"
    exit 1
}

$ButlerExe = Join-Path $ButlerDir "butler.exe"
if (-not (Test-Path $ButlerExe)) {
    Write-Host "butler を取得中..."
    New-Item -ItemType Directory -Force -Path $ButlerDir | Out-Null
    $Archive = Join-Path $env:TEMP "butler-windows-amd64.zip"
    Invoke-WebRequest -Uri "https://broth.itch.zone/butler/windows-amd64/LATEST/archive/default" -OutFile $Archive
    Expand-Archive -Path $Archive -DestinationPath $ButlerDir -Force
    Remove-Item $Archive -Force
}

& $ButlerExe push $Zip "${User}/${Game}:${Channel}" --userversion "0.1.0"
Write-Host ""
Write-Host "Upload complete: https://${User}.itch.io/${Game}"
