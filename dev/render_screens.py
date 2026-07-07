"""メニュー画面をヘッドレスで PNG 出力し、レイアウト検証を行う"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from caterpillar_art import reset_title_demo, update_title_demo
from constants import SCREEN_H, SCREEN_W
from dev.checks import run_title_checks
from game import GameState, Match
from match_prep import PrepPhase, draw_cinematic_veil
from result_flow import ResultPhase
from screens import (
    _draw_tips_subtitle_veil,
    draw_cpu_difficulty_screen,
    draw_result_screen,
    draw_title_screen,
    draw_tips_overlay,
    tips_for_match,
)
from sprites import init_sprites
from arena_assets import init_arena_assets
from title_typography import load_title_fonts

OUT_DIR = os.path.join(os.path.dirname(__file__), "out")


def _fonts() -> tuple:
    fonts = load_title_fonts()
    hud = pygame.font.SysFont("meiryo", 32, bold=True)
    return fonts, fonts.screen_title, fonts.screen_body, fonts.screen_small, hud


def _save(surf: pygame.Surface, name: str) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    pygame.image.save(surf, path)
    return path


def _render_arena_base(surf: pygame.Surface, match: Match, now: float = 42.0) -> None:
    from arena_assets import draw_arena_table, draw_battle_backdrop, init_arena_assets
    from hud_ui import draw_match_hud
    from title_typography import load_title_fonts

    init_arena_assets()
    draw_battle_backdrop(surf, now)
    draw_arena_table(surf, now)
    fonts = load_title_fonts()
    draw_match_hud(surf, match, fonts, now, bgm_muted=False)


def _render_battle_scene(surf: pygame.Surface, match: Match, now: float = 42.0) -> None:
    from caterpillar_art import draw_player_fences
    from constants import CATERPILLAR_BODY_RADIUS
    from entities import Fence, Puck, table_rect

    _render_arena_base(surf, match, now)
    rect = table_rect()
    match.paddles[0].x = rect.left + rect.width * 0.22
    match.paddles[0].y = rect.centery - 40
    match.paddles[1].x = rect.left + rect.width * 0.62
    match.paddles[1].y = rect.centery + 30
    match.paddles[1].face_heading = 3.14
    now_fence = now + 5.0
    match.fences = [
        Fence(owner=0, x1=rect.left + 120, y1=rect.centery - 20, x2=rect.left + 220, y2=rect.centery + 10, until=now_fence, created_at=now),
        Fence(owner=0, x1=rect.left + 220, y1=rect.centery + 10, x2=rect.left + 300, y2=rect.centery + 50, until=now_fence, created_at=now),
        Fence(owner=1, x1=rect.right - 280, y1=rect.centery - 40, x2=rect.right - 180, y2=rect.centery, until=now_fence, created_at=now),
    ]
    match.pucks = [Puck(x=rect.centerx - 60, y=rect.centery - 80, vx=120, vy=40)]
    for owner in (0, 1):
        player_fences = [f for f in match.fences if f.owner == owner]
        draw_player_fences(surf, player_fences, now, CATERPILLAR_BODY_RADIUS)
    for puck in match.pucks:
        puck.draw(surf, now)
    for paddle in match.paddles:
        paddle.draw(surf, now)


def render_all() -> list[str]:
    pygame.init()
    init_sprites()
    init_arena_assets()
    title_fonts, title_font, body_font, small_font, _ = _fonts()
    saved: list[str] = []
    now = 1.25

    reset_title_demo()
    for i in range(480):
        update_title_demo(1.0 / 60.0, i / 60.0)

    for idx in range(3):
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        draw_title_screen(
            surf, title_font, body_font, small_font,
            menu_index=idx,
            title_fonts=title_fonts, cpu_diff_index=1, now=now, dt=0.0,
        )
        saved.append(_save(surf, f"title_{idx}.png"))

    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    draw_cpu_difficulty_screen(
        surf, title_font, body_font, small_font, selected_index=1, now=now,
        title_fonts=title_fonts, morph_progress=1.0,
    )
    saved.append(_save(surf, "cpu_diff.png"))

    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    draw_cpu_difficulty_screen(
        surf, title_font, body_font, small_font, selected_index=1, now=now,
        title_fonts=title_fonts, morph_progress=0.55,
    )
    saved.append(_save(surf, "cpu_diff_morph.png"))

    from arena_assets import draw_menu_backdrop

    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    draw_menu_backdrop(surf, now)
    _draw_tips_subtitle_veil(surf, now)
    draw_tips_overlay(
        surf, body_font, small_font,
        tip_text=tips_for_match(vs_cpu=True)[0],
        tips_alpha=1.0,
    )
    draw_cinematic_veil(surf, 1.0, 0.0)
    saved.append(_save(surf, "prep_tips.png"))

    scenarios = (
        ("result_p1_win_2p", {"vs_cpu": False, "winner": 0, "scores": (3, 1)}),
        ("result_cpu_win", {"vs_cpu": True, "winner": 1, "scores": (2, 3)}),
        ("result_you_win_cpu", {"vs_cpu": True, "winner": 0, "scores": (3, 0)}),
    )
    for name, cfg in scenarios:
        match = Match(audio=None)
        match.state = GameState.RESULT
        match.vs_cpu = cfg["vs_cpu"]
        match.winner = cfg["winner"]
        match.scores = list(cfg["scores"])
        match.match_time = 127.5
        match.result_phase = ResultPhase.HOLD
        match.result_dimness = 1.0
        match.result_card_alpha = 1.0
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        _render_arena_base(surf, match, now=now)
        draw_result_screen(
            surf, match, title_font, body_font, small_font, now=now,
        )
        saved.append(_save(surf, f"{name}.png"))

    match = Match(audio=None)
    match.state = GameState.PLAYING
    match.vs_cpu = True
    match.scores = [2, 1]
    match.match_time = 66.0
    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    _render_battle_scene(surf, match, now=now)
    saved.append(_save(surf, "battle_playing.png"))

    match.scores = [1, 0]
    match.match_time = 61.0
    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    _render_arena_base(surf, match)
    saved.append(_save(surf, "arena_cpu.png"))

    pygame.quit()
    return saved


def main() -> int:
    errors = run_title_checks()
    if errors:
        print("CHECK FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    paths = render_all()
    print("CHECK OK - title demo / logo layout")
    print(f"Wrote {len(paths)} images to {OUT_DIR}")
    for p in paths:
        print(f"  {os.path.basename(p)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
