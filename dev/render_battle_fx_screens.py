"""バトル演出の場面別スクリーンショットをヘッドレスで出力する"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from arena_assets import ArenaLightingState, draw_battle_backdrop, draw_arena_table, init_arena_assets
from caterpillar_art import draw_player_fences
from constants import (
    CATERPILLAR_BODY_RADIUS,
    FACEOFF_LIGHT_DURATION,
    GOAL_FIREFLY_DURATION,
    GOAL_SIDE_FLASH_DURATION,
    GOAL_WALL_PULSE_DURATION,
    PUCK_RESET_ANIM_DURATION,
    SCORE_POP_DURATION,
    SCREEN_H,
    SCREEN_W,
)
from effects import (
    PuckResetAnim,
    draw_breach_sparks,
    draw_goal_celebration,
    goal_mouth_anchor,
    spawn_breach_sparks,
    spawn_goal_celebration,
    update_goal_celebration,
)
from entities import Fence, Puck, playable_rect, table_rect
from game import GameState, Match
from hud_ui import draw_match_hud
from main import draw_countdown
from sprites import init_sprites
from title_typography import load_title_fonts

OUT_DIR = os.path.join(os.path.dirname(__file__), "out", "battle_fx")


def _save(surf: pygame.Surface, name: str) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    pygame.image.save(surf, path)
    return path


def _render_battle_frame(
    surf: pygame.Surface,
    match: Match,
    now: float,
    *,
    big_font: pygame.font.Font | None = None,
) -> None:
    lighting = match.arena_lighting
    draw_battle_backdrop(surf, now, lighting=lighting)
    draw_arena_table(surf, now, lighting=lighting)
    for owner in (0, 1):
        fences = [f for f in match.fences if f.owner == owner]
        draw_player_fences(surf, fences, now, CATERPILLAR_BODY_RADIUS)
    for puck in match.pucks:
        puck.draw(surf, now)
    if match.puck_reset_anim is not None:
        match.puck_reset_anim.draw(surf, now)
    draw_breach_sparks(surf, match.breach_sparks)
    for paddle in match.paddles:
        paddle.draw(surf, now)
    fonts = load_title_fonts()
    draw_match_hud(surf, match, fonts, now, bgm_muted=False)
    if match.goal_fx is not None:
        draw_goal_celebration(surf, match.goal_fx)
    if big_font is not None and match.state == GameState.COUNTDOWN:
        draw_countdown(surf, match, big_font)


def _base_match() -> Match:
    match = Match(audio=None)
    match.state = GameState.PLAYING
    match.vs_cpu = True
    match.pucks_frozen = True
    rect = table_rect()
    match.paddles[0].x = rect.left + rect.width * 0.25
    match.paddles[0].y = rect.centery - 50
    match.paddles[1].x = rect.right - rect.width * 0.25
    match.paddles[1].y = rect.centery + 40
    match.paddles[1].face_heading = 3.14
    match.match_time = 88.0
    return match


def render_all() -> list[str]:
    pygame.init()
    init_sprites()
    init_arena_assets()
    big_font = pygame.font.SysFont("meiryo", 96, bold=True)
    saved: list[str] = []
    now = 42.0

    # 通常プレイ
    match = _base_match()
    match.scores = [1, 1]
    match.pucks_frozen = False
    rect = table_rect()
    match.pucks = [Puck(x=rect.centerx, y=rect.centery - 60, vx=180, vy=50, wall_bounces=2)]
    now_f = now + 8.0
    match.fences = [
        Fence(owner=0, x1=rect.left + 100, y1=rect.centery, x2=rect.left + 200, y2=rect.centery + 40,
              until=now_f, created_at=now),
    ]
    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    _render_battle_frame(surf, match, now)
    saved.append(_save(surf, "01_battle_normal.png"))

    # ラリーグロー
    match = _base_match()
    match.scores = [0, 1]
    match.pucks = [Puck(x=rect.centerx + 40, y=rect.centery, vx=300, vy=-120, wall_bounces=5)]
    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    _render_battle_frame(surf, match, now)
    saved.append(_save(surf, "02_rally_glow.png"))

    # P1ゴール直後（左ゴール）— 壁沿い光パルス
    match = _base_match()
    match.scores = [2, 0]
    match.score_pop_player = 0
    match.score_pop_timer = SCORE_POP_DURATION * 0.55
    match.goal_fx = spawn_goal_celebration(conceded_side=0, scorer=0, points=1)
    match.goal_fx.timer = 0.9
    update_goal_celebration(match.goal_fx, 0.45)
    match.arena_lighting.goal_flash_side = 0
    match.arena_lighting.goal_flash_scorer = 0
    match.arena_lighting.goal_flash_timer = GOAL_WALL_PULSE_DURATION * 0.45
    match.pucks = []
    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    _render_battle_frame(surf, match, now)
    saved.append(_save(surf, "03_goal_p1_left.png"))

    # P2ゴール直後（右ゴール）
    match = _base_match()
    match.scores = [1, 2]
    match.score_pop_player = 1
    match.score_pop_timer = SCORE_POP_DURATION * 0.4
    match.goal_fx = spawn_goal_celebration(conceded_side=1, scorer=1, points=1)
    match.goal_fx.timer = 0.85
    update_goal_celebration(match.goal_fx, 0.5)
    match.arena_lighting.goal_flash_side = 1
    match.arena_lighting.goal_flash_scorer = 1
    match.arena_lighting.goal_flash_timer = GOAL_WALL_PULSE_DURATION * 0.55
    match.pucks = []
    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    _render_battle_frame(surf, match, now + 1.3)
    saved.append(_save(surf, "04_goal_p2_right.png"))

    # パック中央復帰アニメ中
    match = _base_match()
    match.scores = [2, 1]
    play = playable_rect()
    sx, sy = goal_mouth_anchor(1)
    match.puck_reset_anim = PuckResetAnim(
        start_x=sx, start_y=sy,
        end_x=play.centerx, end_y=play.centery,
        timer=PUCK_RESET_ANIM_DURATION * 0.55,
    )
    match.pucks = []
    match.goal_fx = spawn_goal_celebration(conceded_side=1, scorer=0, points=1)
    match.goal_fx.timer = 0.3
    update_goal_celebration(match.goal_fx, 1.05)
    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    _render_battle_frame(surf, match, now)
    saved.append(_save(surf, "05_puck_reset_mid.png"))

    # フェイスオフ木漏れ日
    match = _base_match()
    match.scores = [2, 2]
    match.arena_lighting.near_win = True
    match.arena_lighting.faceoff_pulse_timer = FACEOFF_LIGHT_DURATION * 0.6
    match.pucks = [Puck(x=play.centerx, y=play.centery, vx=0, vy=0)]
    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    _render_battle_frame(surf, match, now)
    saved.append(_save(surf, "06_faceoff_near_win.png"))

    # 貫通火花
    match = _base_match()
    match.scores = [0, 0]
    match.pucks = [Puck(x=rect.centerx, y=rect.centery, vx=400, vy=0, breach_flash_until=now + 0.2)]
    match.breach_sparks = spawn_breach_sparks(rect.centerx, rect.centery, 400, 0)
    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    _render_battle_frame(surf, match, now)
    saved.append(_save(surf, "07_breach_sparks.png"))

    # カウントダウン
    match = _base_match()
    match.state = GameState.COUNTDOWN
    match.countdown = 2
    match.pucks = [Puck(x=play.centerx, y=play.centery, vx=0, vy=0)]
    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    _render_battle_frame(surf, match, now, big_font=big_font)
    saved.append(_save(surf, "08_countdown.png"))

    pygame.quit()
    return saved


def main() -> int:
    paths = render_all()
    print(f"Wrote {len(paths)} battle FX screenshots to {OUT_DIR}")
    for p in paths:
        print(f"  {os.path.basename(p)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
