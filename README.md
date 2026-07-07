# 芋虫ホッケー

**這うと体節が壁になる、エアホッケー** — ローカル2芋虫 or CPU芋虫対戦の Pygame ゲームです。

- **先取3点**で勝利
- **通常移動**で這った跡が**体節（壁）**になる（古い体節から消える）
- **Shift + 移動**でダッシュ（体節は出ない・既存の壁をすり抜ける）
- **体節貫通** — ダッシュで葉っぱを押し出した直後だけ、勢いを保って体節を抜ける

## ポートフォリオ

- 作品ページ: [koyomivanp.github.io/imomushi-hockey/](https://koyomivanp.github.io/imomushi-hockey/)
- リポジトリ: [github.com/koyomivanp/imomushi-hockey](https://github.com/koyomivanp/imomushi-hockey)
- itch.io: [koyomivanp.itch.io/imomushi-hockey](https://koyomivanp.itch.io/imomushi-hockey)（Windows 版ダウンロード）

## 必要環境

- Python 3.10 以上（推奨 3.11+）
- [pygame-ce](https://github.com/pygame-community/pygame-ce) 2.5+

## 起動方法

```bash
cd imomushi-hockey
pip install -r requirements.txt
python main.py
```

## 操作

### タイトル

| キー | 動作 |
|------|------|
| `↑` / `↓` | メニュー選択 |
| `Space` | 決定 |
| `H` | 操作説明 |
| `M` | BGM オン/オフ |
| `F` | フルスクリーン切替 |
| `Esc` | 終了 |

メニュー: **vs CPU芋虫** / **2芋虫対戦** / **終了**

### CPU難易度（CPU対戦のみ）

| キー | 動作 |
|------|------|
| `A` / `D`（または矢印左右） | 難易度選択 |
| `3` / `4` / `5` | のろのろ / ふつう / はげしい を直接選択 |
| `Space` | 決定 |
| `Esc` | タイトルへ戻る |

### バトル前

暗転 → **TIPS**（`Space` で次へ、最後で開始）→ カウントダウン → 対戦

### 対戦中

| プレイヤー | 移動 | ダッシュ |
|------------|------|----------|
| P1芋虫（左） | `WASD` | `Shift` + 移動 |
| P2芋虫（右） | 矢印キー | `Shift` + 移動 |
| CPU対戦時（P1のみ） | `WASD` | `Shift`（左右どちらでも） |

| キー | 動作 |
|------|------|
| `P` / `Esc` | ポーズ |
| `M` | BGM オン/オフ |
| `F` | フルスクリーン切替 |

### リザルト

| キー | 動作 |
|------|------|
| `Space` | もう一度 |
| `Esc` | タイトルへ |

## 開発用 — 画面スクショ出力

レイアウト確認用に、メニュー画面をヘッドレスで PNG 出力できます。

```bash
python dev/render_screens.py
```

`dev/out/` にタイトル・難易度・TIPS・リザルトの画像が保存されます。芋虫のスタンプ重なりやロゴ被りも自動検証します。

タイトル芋虫の見た目を変えたときは `caterpillar_art.py` 先頭付近の **タイトル芋虫シーン整備メモ** と `_title_worm_bezier` の座標を確認し、`python dev/render_screens.py` で再出力してください。

## Windows 用 exe のビルド

```powershell
pip install -r requirements-build.txt
.\build.ps1
```

`dist\ImomushiHockey\` に実行ファイルが出力されます。配布時はフォルダごと ZIP にしてください。

## itch.io 公開

Windows ZIP・カバー・ストア文案は `itch/` に用意しています。手順は [itch/README.md](itch/README.md)。

```powershell
# API キー設定後
$env:BUTLER_API_KEY = "your-key"
.\dev\publish_itch.ps1
```

## カスタム BGM / SE

`assets/sounds/` に音声ファイルを置くと自動で読み込まれます。詳細は [assets/sounds/README.md](assets/sounds/README.md)。

## ファイル構成

| ファイル | 内容 |
|----------|------|
| `main.py` | エントリ・ゲームループ・対戦描画 |
| `screens.py` | タイトル・TIPS・リザルトなどメニュー画面 |
| `game.py` | 試合ロジック・体節壁 |
| `physics.py` | 当たり判定 |
| `entities.py` | 芋虫・パック・体節 |
| `caterpillar_art.py` | 芋虫・葉っぱの描画 |
| `ai.py` | CPU芋虫 |
| `audio.py` | BGM / SE |
| `effects.py` | ゴール・貫通演出 |
| `sprites.py` | 葉っぱスプライト読み込み |
| `constants.py` | 定数・バージョン |
| `dev/render_screens.py` | 画面 PNG 出力・レイアウト検証 |

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE)

## クレジット

- 開発: 大島橙也
- エンジン: [pygame-ce](https://github.com/pygame-community/pygame-ce)

---

*バージョン: 0.1.0*
