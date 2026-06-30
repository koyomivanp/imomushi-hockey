# 芋虫スプライト（Summer Engine 用）

| ファイル名 | 用途 | 備考 |
|-----------|------|------|
| `leaf_puck.png` | 葉っぱパック | **使用中**（透過処理あり） |
| `caterpillar_p1_segment.png` | P1 体節 | 現在オフ（俯瞰プロシージャル優先） |
| `caterpillar_p2_segment.png` | P2 体節 | 同上 |
| `caterpillar_p1_head.png` | 旧・頭 | 未使用（俯瞰顔はコード描画） |

体節・頭は `sprites.py` の `BODY_SPRITE_ENABLED = False` でプロシージャル描画を優先しています。

## 画像生成（Summer MCP）

```
summer_generate_image(model="gemini-flash", prompt="...", style="cartoon")
```

fal 残高エラー時は `gemini-flash` を指定。プロンプトは **top-down**（俯瞰）を明記すること。

## 葉っぱプロンプト例

```
top-down stylized green leaf with veins, glossy cartoon, solid black background
```

黒背景は起動時に自動でアルファ透過されます。
