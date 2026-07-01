"""メニュー画面をヘッドレスで PNG 出力し、レイアウト検証を行う"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from constants import SCREEN_H, SCREEN_W
from dev.checks import run_title_checks
from game import GameState, Match
from screens import (
    draw_cpu_difficulty_screen,
    draw_fade_screen,
    draw_result_screen,
    draw_title_screen,
    draw_tips_screen,
    tips_for_match,
)
from sprites import init_sprites

OUT_DIR = os.path.join(os.path.dirname(__file__), "out")


def _fonts() -> tuple[pygame.font.Font, pygame.font.Font, pygame.font.Font, pygame.font.Font]:
    title = pygame.font.SysFont("meiryo", 52, bold=True)
    body = pygame.font.SysFont("meiryo", 20)
    small = pygame.font.SysFont("meiryo", 16)
    hud = pygame.font.SysFont("meiryo", 32, bold=True)
    return title, body, small, hud


def _save(surf: pygame.Surface, name: str) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    pygame.image.save(surf, path)
    return path


def _render_arena_base(surf: pygame.Surface, match: Match) -> None:
    from main import draw_hud, draw_table

    surf.fill((0, 0, 0))
    draw_table(surf)
    _, _, small, hud = _fonts()
    draw_hud(surf, match, hud, small, now=42.0)


def render_all() -> list[str]:
    pygame.init()
    init_sprites()
    title_font, body_font, small_font, _ = _fonts()
    saved: list[str] = []
    now = 1.25

    for idx in range(3):
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        draw_title_screen(
            surf, title_font, body_font, small_font,
            menu_index=idx, show_help=False, now=now,
        )
        saved.append(_save(surf, f"title_{idx}.png"))

    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    draw_title_screen(
        surf, title_font, body_font, small_font,
        menu_index=0, show_help=True, now=now,
    )
    saved.append(_save(surf, "title_help.png"))

    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    draw_cpu_difficulty_screen(
        surf, title_font, body_font, small_font, selected_index=1,
    )
    saved.append(_save(surf, "cpu_diff.png"))

    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    draw_fade_screen(surf, 0.5)
    saved.append(_save(surf, "fade.png"))

    tips = tips_for_match(vs_cpu=True)
    for idx, tip in enumerate(tips):
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        draw_tips_screen(
            surf, title_font, body_font, small_font,
            tip_index=idx,
            tip_count=len(tips),
            tip_text=tip,
            is_last=(idx + 1 >= len(tips)),
        )
        suffix = "last" if idx + 1 >= len(tips) else str(idx)
        saved.append(_save(surf, f"tips_{suffix}.png"))

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
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        _render_arena_base(surf, match)
        draw_result_screen(
            surf, match, title_font, body_font, small_font, now=now,
        )
        saved.append(_save(surf, f"{name}.png"))

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
    print("CHECK OK - title worms / logo layout")
    print(f"Wrote {len(paths)} images to {OUT_DIR}")
    for p in paths:
        print(f"  {os.path.basename(p)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
