"""バトル描画のボトルネック計測（ヘッドレス）"""

from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from arena_assets import ArenaLightingState, draw_arena_table, draw_battle_backdrop, init_arena_assets
from caterpillar_art import draw_player_fences
from constants import CATERPILLAR_BODY_RADIUS, SCREEN_H, SCREEN_W
from entities import Fence, Paddle, Puck, spawn_center_puck
from game import Match
from sprites import init_sprites


def _make_fences(count: int, owner: int, now: float) -> list[Fence]:
    fences: list[Fence] = []
    x, y = 120.0, 200.0
    for i in range(count):
        nx = x + 28.0
        ny = y + (6.0 if i % 2 else -4.0)
        fences.append(
            Fence(
                owner=owner,
                x1=x,
                y1=y,
                x2=nx,
                y2=ny,
                until=now + 2.6,
                created_at=now - (count - i) * 0.08,
                half_width=CATERPILLAR_BODY_RADIUS,
            )
        )
        x, y = nx, ny
    return fences


def _bench(label: str, fn, repeats: int = 30) -> float:
    t0 = time.perf_counter()
    for _ in range(repeats):
        fn()
    return (time.perf_counter() - t0) / repeats * 1000.0


def main() -> None:
    pygame.init()
    init_sprites()
    init_arena_assets()
    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    now = 10.0
    lighting = ArenaLightingState.inactive()

    match = Match()
    match.state = match.state.PLAYING
    match.paddles = [Paddle(0, 140, 260), Paddle(1, 660, 320)]
    match.pucks = [spawn_center_puck()]
    match.fences = _make_fences(8, 0, now) + _make_fences(8, 1, now)

    def draw_backdrop() -> None:
        draw_battle_backdrop(surf, now, lighting=lighting)

    def draw_table() -> None:
        draw_arena_table(surf, now, lighting=lighting)

    def draw_fences() -> None:
        for owner in (0, 1):
            fences = [f for f in match.fences if f.owner == owner]
            draw_player_fences(surf, fences, now, CATERPILLAR_BODY_RADIUS)

    def draw_entities() -> None:
        for puck in match.pucks:
            puck.draw(surf, now)
        for paddle in match.paddles:
            paddle.draw(surf, now)

    backdrop_ms = _bench("backdrop", draw_backdrop)
    table_ms = _bench("table", draw_table)
    fences_ms = _bench("fences", draw_fences)
    entities_ms = _bench("entities", draw_entities)

    print(
        f"backdrop={backdrop_ms:.2f}ms table={table_ms:.2f}ms "
        f"fences={fences_ms:.2f}ms entities={entities_ms:.2f}ms"
    )


if __name__ == "__main__":
    main()
