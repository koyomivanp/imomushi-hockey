# スマホ版 見た目の作り直し — 作業指示

オーナーは席を外しているので、質問せず自分で判断し、最後に日本語で報告する。

## リポジトリ
- ゲーム: `koyomivanp/imomushi-hockey`。`claude/mobile-web` から `claude/mobile-visual-polish` を切って作業し、こまめに push する。master にはマージしない。`claude/mobile-web` 向けの Draft PR を作る。
- 公開先: `koyomivanp/koyomivanp.github.io` の master。`imomushi-hockey/play/` の下だけを更新し、`index.html`, `favicon.png`, `imomushi-hockey.tar.gz` を置く。ほかのファイルは触らない。公開はオーナーの承認済み。push できなければ成果はブランチに残し、その旨を報告する。

## 構成
試合ロジックは横画面(800x600)座標のまま、`mobile_view.py` で90度回転して縦画面(540x960)に表示する。入口 `mobile_main.py`、操作 `touch_input.py`、定数 `constants.py`。

- ビルド: `python dev/build_web.py`（pygbag, ffmpeg。`pip install -r requirements-build.txt`）
- テスト: `python dev/test_mobile.py`, `python dev/test_gameplay.py`
- 画面出力: `python dev/render_mobile.py`（`dev/out/mobile/` に PNG。必ず目で確認する）
- ヘッドレス実行: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`

## オーナーの要望
芋虫の身体が表示されない。演出がダサく、かっこよさを感じない。芋虫以外の見た目にも問題がある。小さくて見づらいので、パッと見て分かるものにしたい。今の見た目を残す必要はないので、コート、タイトル、ボールなどの案をいくつか出してほしい。

## 1. 体節が表示されないバグ（最優先）
壁は内部で生成されるのに画面に出ない。有力な原因（未検証）: `Fence.until` は `game.game_time` 基準なのに、`mobile_main.py` の main ループは描画に `time.perf_counter() - start_time` を渡しており、`caterpillar_art.fence_fade` が寿命切れと判定している疑い。再現してから直す。実際のループと同じ時計の渡し方で「這った跡のピクセルが描かれる」ことを確かめる回帰テストを追加する。

## 2. 見た目の3案を実装する
次の3案をスマホ版のスキンとして実装する。各案でコート、タイトル画面、ボール、芋虫、ゴール、スコア表示、ボタンを統一してデザインする。既存のアセットや森テーマには縛られない。タイトル画面で案を切り替えられるようにし、選択を保存する。既定は A にする。オーナーは静止画でこの3案を見ており、まだどれか選んでいない。

- **A 夜のネオンアリーナ:** 地 `#07070F`、コート `#0C0E22` に `#1B2040` のグリッド。P1 シアン `#19F0E6`、相手マゼンタ `#FF2E88`、発光表現。ボールは残像つきの黄色い光の玉 `#FFE600`。スコアは大きな発光数字。
- **B 真昼のポップスタジアム:** 緑の芝 `#1F9D4D` / `#29B45C` の縞と白線。P1 赤 `#FF4B3E`、相手 青 `#2447F9`、太い黒フチ。ボールは黒と白のサッカーボール風。タイトルは黄 `#FFD60A` の放射背景と影つきボタン。
- **C 墨絵の決闘:** 和紙 `#EFE6D2` に筆の枠。P1 墨 `#16130F`、相手 朱 `#C92A16`。ボールは墨で描いた円。スコアは漢数字。タイトルは朱の丸と縦書きの筆文字。

文字は Web 版に同梱できるフォントを使い、追加するならライセンスを確認して README に記す。

全案共通:
- パッと見で分かること。芋虫とボールを大きくし、背景との明度差を十分取る。コート両脇の黒い帯をなくして画面を広く使う。スコアは遠目でも読める大きさにする。
- サイズ変更で当たり判定が変わる値はスマホ版専用にする。PC版(`main.py`)の見た目とバランスは変えない。
- 演出: ダッシュの残像、強打時の画面の揺れと一瞬の停止、壁を貫通するときの火花、大きな GOAL 表示、勝利演出、ボタンの動き。処理落ちと酔いを避け、控えめな強さから調整する。
- 性能: スマホのブラウザで動く前提。静的な部分はキャッシュし、毎フレームの全画面合成や文字描画を増やさない。`dev/render_mobile.py` の ms/frame を報告する。

## 3. 提出
- 案ごとにタイトルと試合中の PNG を `dev/out` 以外の追跡対象フォルダ `docs/mobile-concepts/` に保存し、PR 本文から参照する。
- テストを通してからビルドして公開する。公開できたら URL が 200 を返すことを確認する。
- コミット末尾に `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`、PR 本文末尾に `🤖 Generated with [Claude Code](https://claude.com/claude-code)` を入れる。

## 報告
PR の URL、公開できたか、3案の概要、バグの原因が事実だったか、テスト結果、確認できなかった点（実機のプレイ感と音）を書く。
