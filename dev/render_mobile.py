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

import tuning
from constants import MOBILE_H, MOBILE_W
from entities import Fence
from game import GameState
from mobile_main import MobileGame, draw_frame
from result_flow import ResultPhase
from sprites import init_sprites

OUT_DIR = os.path.join(ROOT, "dev", "out", "mobile")
DT = 1 / 60


def _crawl(game: MobileGame, x: float, y: float, steps: int, dx: float = 0.0, dy: float = -5.0) -> None:
    """指でなぞって体節を残す（実際の入力と同じ経路）"""
    game.on_press(1, x, y)
    for i in range(1, steps + 1):
        game.on_move(1, x + dx * i, y + dy * i)
        game.step(DT * 2)
    game.on_release(1, x + dx * steps, y + dy * steps)


def main() -> int:
    pygame.init()
    screen = pygame.display.set_mode((MOBILE_W, MOBILE_H))
    init_sprites()
    os.makedirs(OUT_DIR, exist_ok=True)
    game = MobileGame(None)

    def shot(name: str) -> None:
        draw_frame(screen, game, game.game_time)
        pygame.image.save(screen, os.path.join(OUT_DIR, f"{name}.png"))

    def bench(name: str, frames: int = 120) -> None:
        start = time.perf_counter()
        for _ in range(frames):
            draw_frame(screen, game, game.game_time)
        print(f"{name}: {(time.perf_counter() - start) / frames * 1000:.2f} ms/frame")

    shot("title")
    bench("title")
    game.match.open_help()
    shot("help")
    game.match.close_help()

    game.perform("cpu:1")
    for _ in range(30):
        game.step(DT)
    shot("countdown")
    bench("countdown")

    match = game.match
    for _ in range(60 * 4):
        game.step(DT)
        if match.state == GameState.PLAYING:
            break
    _crawl(game, 300, 760, 26)
    shot("playing")
    bench("playing")

    # ゴール演出
    game.fx.burst_goal(MOBILE_W / 2, 140, 0)
    game.shake_timer = 0.2
    for _ in range(14):
        game.step(DT)
    shot("goal")
    bench("goal_fx")

    # ダッシュ中
    game.fx.reset()
    game.on_press(1, 200, 700)
    game.step(DT)
    game.on_move(1, 320, 700)
    for _ in range(8):
        game.step(DT)
    shot("dash")

    match.toggle_pause()
    shot("pause")
    match.toggle_pause()

    match.scores = [3, 1]
    match.winner = 0
    match.state = GameState.RESULT
    match.result_phase = ResultPhase.HOLD
    match.result_dimness = 1.0
    match.result_card_alpha = 1.0
    game.butterfly.start(0, MOBILE_W / 2, 620)
    game.butterfly.t = 0.4
    shot("result_pupa")
    game.butterfly.t = 2.6
    shot("result")

    pygame.quit()
    print("body px:", round(tuning.body_radius() * 2 * 1.15, 1), " ball px:", round(tuning.puck_radius() * 2 * 1.15, 1))
    print("saved to", OUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
