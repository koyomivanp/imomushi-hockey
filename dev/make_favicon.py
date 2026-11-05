"""Web 版の favicon を描き出す（pygbag が CDN から取りに行かないようにする）

使い方: python dev/make_favicon.py  →  assets/web/favicon.png
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from constants import PB_CREAM, PB_INK, PB_P1, PB_WHITE

OUT = os.path.join(ROOT, "assets", "web", "favicon.png")
SIZE = 128


def build() -> pygame.Surface:
    big = SIZE * 4
    surf = pygame.Surface((big, big), pygame.SRCALPHA)
    c = big // 2
    pygame.draw.circle(surf, PB_INK, (c, c), int(big * 0.47))
    pygame.draw.circle(surf, PB_CREAM, (c, c), int(big * 0.43))
    # 芋虫の頭
    head_r = int(big * 0.31)
    pygame.draw.circle(surf, PB_INK, (c, c + int(big * 0.04)), head_r + int(big * 0.035))
    pygame.draw.circle(surf, PB_P1, (c, c + int(big * 0.04)), head_r)
    # 触角
    for side in (-1, 1):
        tip = (c + side * int(big * 0.26), c - int(big * 0.30))
        pygame.draw.line(surf, PB_INK, (c + side * int(big * 0.12), c - int(big * 0.14)), tip, int(big * 0.035))
        pygame.draw.circle(surf, PB_INK, tip, int(big * 0.045))
    # 目
    for side in (-1, 1):
        ex = c + side * int(big * 0.13)
        ey = c + int(big * 0.02)
        er = int(big * 0.12)
        pygame.draw.circle(surf, PB_INK, (ex, ey), er + int(big * 0.022))
        pygame.draw.circle(surf, PB_WHITE, (ex, ey), er)
        pygame.draw.circle(surf, PB_INK, (ex + side * int(big * 0.03), ey + int(big * 0.015)), int(er * 0.5))
    return pygame.transform.smoothscale(surf, (SIZE, SIZE))


def main() -> int:
    pygame.init()
    pygame.display.set_mode((8, 8))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pygame.image.save(build(), OUT)
    pygame.quit()
    print("saved", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
