# バトルアリーナ（Living Forest）



| ファイル | 用途 |

|----------|------|

| `battle_bg.png` | 800×600 夜の森シルエット背景（木・星空・ホタル） |

| `court_floor.png` | コート床（暗い土・苔 wash、極低コントラスト） |

| `court_frame.png` | 9-slice 用 暗い木幹・樹皮枠 |

| `goal_post.png` | ゴール柱（暗い切り株シルエット） |

| `hud_plaque.png` | スコア看板（暗い粗木パネル） |



## トーン



暗く、平坦で、少しへたくそな lo-fi 2D。鮮やかな苔・lush な有機装飾は避ける。

詳細は `.summer/art-bible.md` を参照。



## 生成方法



Summer MCP（`summer_generate_image`, model `nano-banana-2`, style `none`）で `.summer/art-bible.md` のプロンプトから生成済み。



| 生成元 | 備考 |

|--------|------|

| MCP `summer_generate_image` | 2026-07 夜の森シルエット背景（battle_bg 更新） |

| MCP `summer_generate_image` | 2026-07 暗 lo-fi 化（floor / frame / goal / plaque 再生成） |



ファイルが無い場合は起動時に同パレットのプロシージャル fallback が使われます。



MCP 不通時は `python dev/generate_arena_assets.py` で PNG を再生成できます。



## コード側の暗化



- `arena_assets.py`: 床 PNG に `TABLE_COLOR` wash（α58）、看板に暗 overlay（α64）

- `hud_ui.py`: 看板外枠を低コントラスト暗パネルに変更

