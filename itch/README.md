# itch.io 公開手順

## ビルド済みファイル

| ファイル | 用途 |
|----------|------|
| `release/ImomushiHockey-win64.zip` | Windows 向けダウンロード（約 39 MB） |
| `cover.png` | カバー画像 630×500 |
| `screenshots/` | ギャラリー用スクショ |
| `STORE_DESCRIPTION.html` | ストアページ本文（コピペ用） |

ZIP の作り直し:

```powershell
python -m PyInstaller --noconfirm --clean --windowed --name ImomushiHockey --add-data "assets;assets" main.py
Compress-Archive -Path dist\ImomushiHockey\* -DestinationPath itch\release\ImomushiHockey-win64.zip -Force
python dev/make_itch_cover.py
```

## 方法 A — itch アプリ（おすすめ）

1. [itch アプリ](https://itch.io/app) をインストールしてログイン
2. [Create new project](https://itch.io/game/new) で新規作成
   - **Title:** 芋虫ホッケー
   - **URL:** `imomushi-hockey`（→ `https://koyomivanp.itch.io/imomushi-hockey`）
   - **Classification:** Games
   - **Kind of project:** Downloadable
   - **Release status:** Released
   - **Pricing:** Free（または任意）
   - **Platforms:** Windows にチェック
3. 本文に `STORE_DESCRIPTION.html` の内容を貼る
4. `cover.png` と `screenshots/` をアップロード
5. アプリの **Upload** タブ → ZIP を `release/ImomushiHockey-win64.zip` から push
   - Channel: `windows`
   - **Executable:** `ImomushiHockey.exe` を指定
6. **Public** にして保存

## 方法 B — butler CLI

1. [API キー](https://itch.io/user/settings/api-keys) を発行
2. PowerShell:

```powershell
$env:BUTLER_API_KEY = "あなたのAPIキー"
.\dev\publish_itch.ps1
```

初回は itch 上でプロジェクトを作成しておくか、butler がチャンネル作成まで行います。

## ストア設定メモ

- **Tags:** `Sports`, `Local multiplayer`, `Singleplayer`, `2D`, `Arcade`, `Short`
- **Language:** Japanese
- **Made with:** Python, pygame
