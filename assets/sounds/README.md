# サウンド（任意）

このフォルダにファイルを置くと、内蔵のビープ音より優先して再生されます。

| ファイル名 | 用途 |
|------------|------|
| `bgm_title.mp3` / `.ogg` / `.wav` | タイトル BGM |
| `bgm_battle.mp3` / `.ogg` / `.wav` | 対戦 BGM |
| `wall_bounce.wav` | 壁反射 SE |
| `fence_breach.wav` | 体節貫通 SE |
| `goal.wav` | ゴール SE |
| `score_tick.wav` | スコアゲージ上昇 SE |
| `countdown.wav` | カウントダウン SE |
| `start.wav` | 試合開始 SE |
| `victory.wav` | 勝利ファンファーレ |
| `defeat.wav` | 敗北 SE（CPU 戦） |
| `menu_move.wav` | メニューカーソル移動 SE |
| `result_card.wav` | リザルトカード出現 SE |

ファイルが無い場合はプログラム内で生成した森テーマの簡易音が使われます。

MCP 不通時は `python dev/generate_sounds.py` で WAV を一括生成できます（`.summer/audio-bible.md` 参照）。
