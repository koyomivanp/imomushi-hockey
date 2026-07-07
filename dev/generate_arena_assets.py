"""Living forest arena PNG をプロシージャル生成（Gemini / Summer MCP 代替）"""

from __future__ import annotations

import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from arena_assets import (
    bake_battle_bg,
    bake_court_floor,
    bake_court_frame,
    bake_goal_post,
    bake_hud_plaque,
)

OUT_DIR = os.path.join(ROOT, "assets", "arena")


def main() -> int:
    pygame.init()
    os.makedirs(OUT_DIR, exist_ok=True)
    assets = {
        "battle_bg.png": bake_battle_bg(),
        "court_floor.png": bake_court_floor(),
        "court_frame.png": bake_court_frame(),
        "goal_post.png": bake_goal_post(),
        "hud_plaque.png": bake_hud_plaque(),
    }
    for name, surf in assets.items():
        path = os.path.join(OUT_DIR, name)
        pygame.image.save(surf, path)
        print(f"  {path}")
    pygame.quit()
    print(f"Wrote {len(assets)} arena assets to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
