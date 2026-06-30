# 芋虫ホッケー

**這うと体節が壁になる、エアホッケー** — ローカル2芋虫 or CPU芋虫対戦の Pygame ゲームです。

- **先取3点**で勝利
- **通常移動**で這った跡が**体節（壁）**になる（古い体節から消える）
- **Shift + 移動**でダッシュ（体節は出ない・既存の壁をすり抜ける）
- **体節貫通** — 高速の葉っぱ、ダッシュ直後のヒット、同じ壁への連続ヒットで勢いを保って抜ける

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
| `1` | vs CPU芋虫 |
| `2` | 2芋虫対戦 |
| `3` / `4` / `5` | CPU難易度（のろのろ / ふつう / はげしい） |
| `Space` | ゲーム開始 |
| `H` | 操作説明 |
| `M` | BGM オン/オフ |
| `F` | フルスクリーン切替 |
| `Esc` | 終了 |

### 対戦中

| プレイヤー | 移動 | ダッシュ |
|------------|------|----------|
| P1芋虫（左） | `WASD` | `Shift` + 移動 |
| P2芋虫（右） | 矢印キー | `Shift` + 移動 |

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

## Windows 用 exe のビルド

```powershell
pip install -r requirements-build.txt
.\build.ps1
```

`dist\ImomushiHockey\` に実行ファイルが出力されます。配布時はフォルダごと ZIP にしてください。

## カスタム BGM / SE

`assets/sounds/` に音声ファイルを置くと自動で読み込まれます。詳細は [assets/sounds/README.md](assets/sounds/README.md)。

## ファイル構成

| ファイル | 内容 |
|----------|------|
| `main.py` | エントリ・描画・入力 |
| `game.py` | 試合ロジック・体節壁 |
| `physics.py` | 当たり判定 |
| `entities.py` | 芋虫・パック・体節 |
| `caterpillar_art.py` | 芋虫・葉っぱの描画 |
| `ai.py` | CPU芋虫 |
| `audio.py` | BGM / SE |
| `effects.py` | ゴール演出 |
| `sprites.py` | 葉っぱスプライト読み込み |
| `constants.py` | 定数・バージョン |

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE)

## クレジット

- 開発: 大島橙也
- エンジン: [pygame-ce](https://github.com/pygame-community/pygame-ce)

---

*バージョン: 0.1.0*
