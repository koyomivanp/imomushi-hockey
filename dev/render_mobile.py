"""スマホ縦画面をヘッドレスで PNG 出力し、描画時間も測る"""

from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("IMOMUSHI_SETTINGS_DIR", os.path.join(ROOT, "dev", "out", "mobile_settings"))

import pygame

from arena_assets import init_arena_assets
from constants import MOBILE_H, MOBILE_W, SCREEN_H, SCREEN_W
from entities import Fence
from game import GameState
from mobile_main import MobileGame, UIFonts, draw_frame
from result_flow import ResultPhase
from sprites import init_sprites
from title_typography import _load_font, load_title_fonts

OUT_DIR = os.path.join(ROOT, "dev", "out", "mobile")


def main() -> int:
    pygame.init()
    screen = pygame.display.set_mode((MOBILE_W, MOBILE_H))
    init_sprites()
    init_arena_assets()
    arena = pygame.Surface((SCREEN_W, SCREEN_H)).convert()
    scratch = pygame.Surface((SCREEN_W, SCREEN_H)).convert()
    fonts, ui, big = load_title_fonts(), UIFonts(), _load_font(120)
    os.makedirs(OUT_DIR, exist_ok=True)
    game = MobileGame(None)

    def shot(name: str) -> None:
        draw_frame(screen, scratch, arena, game, fonts, ui, big, 42.0)
        pygame.image.save(screen, os.path.join(OUT_DIR, f"{name}.png"))

    def bench(name: str, frames: int = 60) -> None:
        start = time.perf_counter()
        for i in range(frames):
            draw_frame(screen, scratch, arena, game, fonts, ui, big, 42.0 + i / 60)
        print(f"{name}: {(time.perf_counter() - start) / frames * 1000:.1f} ms/frame")

    shot("title")
    bench("title")
    game.match.open_help()
    shot("help")
    game.match.close_help()
    game.perform("cpu:1")
    shot("countdown")
    match = game.match
    match.state = GameState.PLAYING
    match.pucks_frozen = False
    match.scores = [2, 1]
    match.fences = [
        Fence(owner=0, x1=170, y1=300, x2=260, y2=240, until=99.0, created_at=41.0, half_width=12.0),
        Fence(owner=1, x1=620, y1=400, x2=520, y2=350, until=99.0, created_at=41.0, half_width=12.0),
    ]
    match.paddles[0].x, match.paddles[0].y = 270, 230
    match.paddles[1].x, match.paddles[1].y = 510, 345
    shot("playing")
    bench("playing")
    match.toggle_pause()
    shot("pause")
    match.toggle_pause()
    match.scores = [3, 1]
    match.winner = 0
    match.state = GameState.RESULT
    match.result_phase = ResultPhase.HOLD
    match.result_dimness = 1.0
    match.result_card_alpha = 1.0
    shot("result")
    pygame.quit()
    print("saved to", OUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
