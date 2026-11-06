# 芋虫ホッケー

**這うと体節が壁になる、エアホッケー** — ローカル2芋虫 or CPU芋虫対戦の Pygame ゲームです。

- **先取3点**で勝利
- **通常移動**で這った跡が**体節（壁）**になる（古い体節から消える）
- **Shift + 移動**でダッシュ（体節は出ない・打った葉っぱが強く飛ぶ）
- **体節貫通** — ダッシュで打った直後の葉っぱだけ、勢いを保って相手の体節を抜ける
- 体節がはね返すのは葉っぱだけ（芋虫は通り抜けられる）。葉っぱが当たった体節は消える

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
| `H` | 遊び方（`H` / `Esc` / `Space` で戻る） |
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

暗転 → **TIPS**（1 件表示。`Space` でスキップ）→ カウントダウン（3・2・1・GO!）→ 対戦

### 対戦中

| プレイヤー | 移動 | ダッシュ |
|------------|------|----------|
| P1芋虫（左） | `WASD` | 左 `Shift` + 移動 |
| P2芋虫（右） | 矢印キー | 右 `Shift` + 移動 |
| CPU対戦時（P1のみ） | `WASD` | `Shift`（左右どちらでも） |

| キー | 動作 |
|------|------|
| `P` / `Esc` | ポーズ（ポーズ中は `P` で再開、`Esc` でタイトルへ） |
| `M` | BGM オン/オフ |
| `F` | フルスクリーン切替 |

ウィンドウのフォーカスが外れると自動でポーズします。

### リザルト

| キー | 動作 |
|------|------|
| `Space` | もう一度（同じ難易度で TIPS なしで再戦） |
| `Esc` | タイトルへ |

## 設定の保存

BGM のオン/オフ、フルスクリーン、最後に選んだ CPU 難易度を次の場所に保存します。読めない場合は既定値で起動します。

- Windows: `%APPDATA%\ImomushiHockey\settings.json`
- その他: `$XDG_CONFIG_HOME/ImomushiHockey/settings.json`（未設定時は `~/.config/`）

## 開発用 — テスト・計測

```bash
python dev/test_gameplay.py      # 回帰テスト（ヘッドレスで main() を実行）
python dev/sim_cpu_balance.py    # CPU の勝率・自殺点・膠着などを計測
```

## 開発用 — 画面スクショ出力

レイアウト確認用に、メニュー画面をヘッドレスで PNG 出力できます。

```bash
python dev/render_screens.py
```

`dev/out/` にタイトル・難易度・遊び方・TIPS・ポーズ・リザルトの画像が保存されます。芋虫のスタンプ重なりやロゴ被りも自動検証します。

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

## スマホ版（ブラウザ）

縦画面で上下に対戦する Web 版です。試合の処理は PC 版と共通で、表示と操作だけ縦画面用になっています。

| 操作 | 動作 |
|------|------|
| 指を置いてなぞる | なぞった方向へ這う（跡が体節の壁になる） |
| 左下のボタン | ダッシュ（PC は Shift） |
| 右上の `II` | ポーズ |

2人対戦は1台を挟み、画面の下半分と上半分でそれぞれ操作します。CPU 戦は画面のどこでも操作できます。

ビルドには ffmpeg が必要です。インターネット接続がある環境で動作します（Python 実行環境を pygbag の CDN から読み込みます）。

```bash
pip install -r requirements-build.txt
python dev/build_web.py --serve   # dist-web/ に出力し http://localhost:8000 で確認
python dev/test_mobile.py         # 操作の回帰テスト
python dev/render_mobile.py       # 画面 PNG を dev/out/mobile/ に出力
```

PC で動作だけ確認するなら `python mobile_main.py`（マウスで操作）でも起動できます。

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
| `mobile_main.py` | スマホ版のエントリ・入力・進行 |
| `mobile_view.py` | スマホ版の縦画面の画面構成 |
| `mobile_art.py` | スマホ版の絵（絵本の庭・芋虫・てんとう虫） |
| `mobile_fx.py` | スマホ版の演出（花びら・土ぼこり・サナギと蝶） |
| `tuning.py` | 実行時の寸法（スマホ版だけ太くする） |
| `touch_input.py` | フリック操作の判定 |
| `settings.py` | 設定の読み書き |
| `dev/render_screens.py` | 画面 PNG 出力・レイアウト検証 |
| `dev/test_gameplay.py` | 回帰テスト |
| `dev/sim_cpu_balance.py` | CPU の挙動計測 |

## フォント

| フォント | 用途 | ライセンス |
|----------|------|------------|
| [Zen Maru Gothic](https://fonts.google.com/specimen/Zen+Maru+Gothic) | PC版・スマホ版の全文字 | [SIL Open Font License 1.1](https://scripts.sil.org/OFL) |

スマホ版の「絵本の庭」デザインは Mochiy Pop One を想定していましたが、
この環境から Google Fonts へ接続できず同梱できませんでした。
丸ゴシックで雰囲気の近い同梱済みの Zen Maru Gothic を使っています。

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE)

## クレジット

- 開発: 大島橙也
- エンジン: [pygame-ce](https://github.com/pygame-community/pygame-ce)

---

*バージョン: 0.1.0*
