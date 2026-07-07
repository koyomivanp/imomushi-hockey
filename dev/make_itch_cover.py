"""itch.io カバー画像 (630x500) を生成"""

from __future__ import annotations

import sys
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "dev" / "out" / "battle_playing.png"
OUT = ROOT / "itch" / "cover.png"
W, H = 630, 500


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.HIDDEN)
    src = pygame.image.load(str(SRC)).convert()
    sw, sh = src.get_size()
    scale = max(W / sw, H / sh)
    scaled = pygame.transform.smoothscale(src, (int(sw * scale), int(sh * scale)))
    canvas = pygame.Surface((W, H))
    canvas.fill((14, 28, 18))
    x = (W - scaled.get_width()) // 2
    y = (H - scaled.get_height()) // 2
    canvas.blit(scaled, (x, y))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(canvas, str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
    sys.exit(0)
