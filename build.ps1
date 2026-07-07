# Windows 向け配布ビルド（PyInstaller）
# 使い方: .\build.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    if (-not (python -m PyInstaller --version 2>$null)) {
        Write-Host "PyInstaller not found. Run: pip install -r requirements-build.txt"
        exit 1
    }
    $PyInstaller = "python -m PyInstaller"
} else {
    $PyInstaller = "pyinstaller"
}

Invoke-Expression "$PyInstaller --noconfirm --clean --windowed --name ImomushiHockey --add-data `"assets;assets`" main.py"

Write-Host ""
Write-Host "ビルド完了: dist\ImomushiHockey\ImomushiHockey.exe"
Write-Host "配布時は dist\ImomushiHockey フォルダを ZIP にしてください。"
