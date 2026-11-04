"""スマホ縦画面 — 試合ロジックは横画面の座標のまま、表示と入力だけ90度回す"""

from __future__ import annotations

import math

import pygame

from ai import CPU_DIFFICULTY_ORDER, DIFFICULTIES
from arena_assets import draw_arena_table, draw_battle_backdrop, draw_menu_backdrop
from caterpillar_art import draw_player_fences
from constants import (
    CATERPILLAR_BODY_RADIUS,
    CPU_LABEL,
    GO_DISPLAY_DURATION,
    LOGO_FILL,
    LOGO_OUTLINE,
    MENU_BG,
    MENU_BORDER,
    MENU_CARD,
    MENU_PRIMARY_GLOW,
    MENU_TEXT,
    MENU_TEXT_DIM,
    MOBILE_ARENA_CROP_TOP,
    MOBILE_ARENA_Y,
    MOBILE_H,
    MOBILE_HELP_LINES,
    MOBILE_HUD_H,
    MOBILE_W,
    P1_COLOR,
    P2_COLOR,
    SCREEN_H,
    SCREEN_W,
    TITLE_CATCH_COPY,
    WIN_SCORE,
)
from effects import draw_breach_sparks, draw_goal_celebration
from game import GameState
from screens import result_headline
from title_typography import render_tilted_logo, render_ui_outlined

_BARK = (58, 38, 24)
_ARENA_CROP = pygame.Rect(0, MOBILE_ARENA_CROP_TOP, SCREEN_W, SCREEN_H - MOBILE_ARENA_CROP_TOP)


def logic_to_screen(x: float, y: float) -> tuple[float, float]:
    """横画面の座標 → 縦画面の座標（左ゴール=P1 が下、右ゴールが上）"""
    return y - MOBILE_ARENA_CROP_TOP, MOBILE_ARENA_Y + (SCREEN_W - x)


def screen_dir_to_logic(dx: float, dy: float) -> tuple[float, float]:
    """縦画面の向き → 横画面の向き（logic_to_screen の回転の逆）"""
    return -dy, dx


class Button:
    def __init__(self, rect: pygame.Rect, label: str, action: str) -> None:
        self.rect = rect
        self.label = label
        self.action = action

    def draw(self, surf: pygame.Surface, font: pygame.font.Font, *, primary: bool = False) -> None:
        fill = (42, 58, 44) if primary else (28, 44, 30)
        border = MENU_PRIMARY_GLOW if primary else MENU_BORDER
        pygame.draw.rect(surf, fill, self.rect, border_radius=16)
        pygame.draw.rect(surf, border, self.rect, 3 if primary else 2, border_radius=16)
        color = LOGO_FILL if primary else MENU_TEXT
        text = render_ui_outlined(self.label, font, color, outline=_BARK, outline_px=2)
        surf.blit(text, text.get_rect(center=self.rect.center))


def _column_button(y: int, label: str, action: str, *, h: int = 76, w: int = 420) -> Button:
    return Button(pygame.Rect((MOBILE_W - w) // 2, y, w, h), label, action)


def title_buttons(bgm_muted: bool) -> list[Button]:
    w, gap = 148, 10
    left = (MOBILE_W - (w * 3 + gap * 2)) // 2
    buttons = [
        Button(pygame.Rect(left + i * (w + gap), 512, w, 84), DIFFICULTIES[key].label, f"cpu:{i}")
        for i, key in enumerate(CPU_DIFFICULTY_ORDER)
    ]
    buttons.append(_column_button(632, "2人対戦（1台で上下に）", "two_player"))
    buttons.append(_column_button(724, "遊び方", "help"))
    buttons.append(_column_button(816, "BGM: オフ" if bgm_muted else "BGM: オン", "bgm", h=60))
    return buttons


def help_buttons() -> list[Button]:
    return [_column_button(MOBILE_H - 116, "とじる", "close_help")]


def pause_button_rect() -> pygame.Rect:
    return pygame.Rect(MOBILE_W - 76, 10, 64, MOBILE_HUD_H - 20)


def pause_buttons(bgm_muted: bool) -> list[Button]:
    return [
        _column_button(380, "つづける", "resume"),
        _column_button(472, "BGM: オフ" if bgm_muted else "BGM: オン", "bgm"),
        _column_button(564, "タイトルへ", "to_title"),
    ]


def result_buttons() -> list[Button]:
    return [
        _column_button(540, "もう一度", "rematch"),
        _column_button(632, "タイトルへ", "to_title"),
    ]


def hit_button(buttons: list[Button], x: float, y: float) -> str | None:
    for button in buttons:
        if button.rect.collidepoint(x, y):
            return button.action
    return None


def _draw_portrait_backdrop(surf: pygame.Surface, now: float, scratch: pygame.Surface) -> None:
    """森の背景は横長なので、高さに合わせて拡大し中央を切り出す"""
    draw_menu_backdrop(scratch, now)
    size = (int(SCREEN_W * MOBILE_H / SCREEN_H), MOBILE_H)
    scaled = pygame.transform.scale(scratch, size)
    surf.blit(scaled, (-(size[0] - MOBILE_W) // 2, 0))


def _draw_veil(surf: pygame.Surface, alpha: int) -> None:
    veil = pygame.Surface((MOBILE_W, MOBILE_H), pygame.SRCALPHA)
    veil.fill((8, 16, 10, alpha))
    surf.blit(veil, (0, 0))


def _centered(surf: pygame.Surface, text: pygame.Surface, y: int) -> None:
    surf.blit(text, text.get_rect(center=(MOBILE_W // 2, y)))


def draw_title(surf, fonts, ui_fonts, now, scratch, *, cpu_diff_index: int, buttons) -> None:
    _draw_portrait_backdrop(surf, now, scratch)
    logo, _ = render_tilted_logo("芋虫", "ホッケー", fonts, now=now)
    logo = pygame.transform.smoothscale_by(logo, 1.35)
    surf.blit(logo, logo.get_rect(center=(MOBILE_W // 2, 240)))
    catch = render_ui_outlined(TITLE_CATCH_COPY, ui_fonts.body, LOGO_FILL, outline=_BARK, outline_px=2)
    _centered(surf, catch, 66)
    label = render_ui_outlined(f"vs {CPU_LABEL}", ui_fonts.body, LOGO_FILL, outline=_BARK, outline_px=2)
    _centered(surf, label, 486)
    for button in buttons:
        button.draw(surf, ui_fonts.button, primary=button.action == f"cpu:{cpu_diff_index}")


def draw_help(surf, fonts, ui_fonts, now, scratch, buttons) -> None:
    _draw_portrait_backdrop(surf, now, scratch)
    _draw_veil(surf, 170)
    title = render_ui_outlined("遊び方", fonts.screen_title, LOGO_FILL, outline=_BARK, outline_px=3)
    _centered(surf, title, 92)
    y = 170
    for heading, body in MOBILE_HELP_LINES:
        head = render_ui_outlined(heading, ui_fonts.body, MENU_PRIMARY_GLOW, outline=_BARK, outline_px=2)
        surf.blit(head, (48, y))
        y += head.get_height() + 6
        for line in body:
            text = ui_fonts.small.render(line, True, MENU_TEXT)
            surf.blit(text, (48, y))
            y += text.get_height() + 4
        y += 20
    for button in buttons:
        button.draw(surf, ui_fonts.button, primary=True)


_court_cache: pygame.Surface | None = None
_screen_cache_key: object = None
_screen_cache: pygame.Surface | None = None


def blit_cached_screen(surf: pygame.Surface, key: object, build) -> None:
    """変化しない画面は一度だけ描く（スマホのブラウザでは文字描画と全画面合成が重い）"""
    global _screen_cache, _screen_cache_key
    if _screen_cache is None or _screen_cache_key != key:
        _screen_cache = pygame.Surface((MOBILE_W, MOBILE_H)).convert()
        build(_screen_cache)
        _screen_cache_key = key
    surf.blit(_screen_cache, (0, 0))


def _draw_court_floor(arena: pygame.Surface, match, now: float) -> None:
    """ゴール演出の間だけ毎フレーム描き、それ以外は焼いたコートを使う"""
    global _court_cache
    lighting = match.arena_lighting
    if lighting.goal_flash_timer > 0.0 or lighting.faceoff_pulse_timer > 0.0:
        draw_battle_backdrop(arena, now, lighting=lighting)
        draw_arena_table(arena, now, lighting=lighting)
        return
    if _court_cache is None:
        _court_cache = pygame.Surface((SCREEN_W, SCREEN_H)).convert()
        draw_battle_backdrop(_court_cache, 0.0)
        draw_arena_table(_court_cache, 0.0)
    arena.blit(_court_cache, (0, 0))


def draw_arena(surf: pygame.Surface, arena: pygame.Surface, match, now: float) -> None:
    """横画面用の描画をそのまま使い、回転してコート部分だけ載せる"""
    _draw_court_floor(arena, match, now)
    for owner in (0, 1):
        draw_player_fences(arena, [f for f in match.fences if f.owner == owner], now, CATERPILLAR_BODY_RADIUS)
    for puck in match.pucks:
        puck.draw(arena, now)
    if match.puck_reset_anim is not None:
        match.puck_reset_anim.draw(arena, now)
    draw_breach_sparks(arena, match.breach_sparks)
    for paddle in match.paddles:
        paddle.draw(arena, now)
    if match.goal_fx is not None:
        draw_goal_celebration(arena, match.goal_fx)
    rotated = pygame.transform.rotate(arena.subsurface(_ARENA_CROP), 90)
    surf.blit(rotated, (0, MOBILE_ARENA_Y))


def _draw_score_strip(surf, rect: pygame.Rect, label: str, score: int, color, font, *, pop: bool, now: float) -> None:
    pygame.draw.rect(surf, MENU_BG, rect)
    text = render_ui_outlined(label, font, LOGO_FILL, outline=_BARK, outline_px=2)
    surf.blit(text, text.get_rect(midleft=(rect.left + 16, rect.centery)))
    size, gap = 56, 10
    x = rect.left + 170
    for i in range(WIN_SCORE):
        slot = pygame.Rect(x + i * (size + gap), rect.centery - 13, size, 26)
        pygame.draw.rect(surf, MENU_CARD, slot, border_radius=8)
        if i < score:
            lit = color
            if pop and i == score - 1:
                lit = tuple(min(255, int(c + 70 * (0.5 + 0.5 * math.sin(now * 24.0)))) for c in color)
            pygame.draw.rect(surf, lit, slot, border_radius=8)
        pygame.draw.rect(surf, _BARK, slot, 2, border_radius=8)


_hud_cache_key: object = None
_hud_cache: tuple[pygame.Surface, pygame.Surface] | None = None


def draw_hud(surf, match, ui_fonts, now) -> None:
    global _hud_cache, _hud_cache_key
    popping = match.score_pop_player
    key = (match.vs_cpu, tuple(match.scores), popping, int(now * 12) if popping is not None else 0)
    if _hud_cache is None or _hud_cache_key != key:
        top = pygame.Surface((MOBILE_W, MOBILE_HUD_H)).convert()
        bottom = pygame.Surface((MOBILE_W, MOBILE_HUD_H)).convert()
        rect = top.get_rect()
        top_label = CPU_LABEL if match.vs_cpu else "P2"
        bottom_label = "あなた" if match.vs_cpu else "P1"
        _draw_score_strip(top, rect, top_label, match.scores[1], P2_COLOR, ui_fonts.button, pop=popping == 1, now=now)
        _draw_score_strip(bottom, rect, bottom_label, match.scores[0], P1_COLOR, ui_fonts.button, pop=popping == 0, now=now)
        pause = pause_button_rect()
        pygame.draw.rect(top, (28, 44, 30), pause, border_radius=12)
        pygame.draw.rect(top, MENU_BORDER, pause, 2, border_radius=12)
        for offset in (-9, 9):
            pygame.draw.rect(top, LOGO_FILL, (pause.centerx + offset - 4, pause.centery - 14, 8, 28), border_radius=3)
        _hud_cache = (top, bottom)
        _hud_cache_key = key
    surf.blit(_hud_cache[0], (0, 0))
    surf.blit(_hud_cache[1], (0, MOBILE_H - MOBILE_HUD_H))


def draw_countdown(surf, match, big_font) -> None:
    if match.state == GameState.COUNTDOWN and match.countdown > 0:
        text = render_ui_outlined(str(match.countdown), big_font, LOGO_FILL, outline=LOGO_OUTLINE, outline_px=4)
        _centered(surf, text, MOBILE_H // 2)
    elif match.go_timer > 0.0:
        text = render_ui_outlined("GO!", big_font, LOGO_FILL, outline=LOGO_OUTLINE, outline_px=4)
        text.set_alpha(int(255 * min(1.0, match.go_timer / (GO_DISPLAY_DURATION * 0.5))))
        _centered(surf, text, MOBILE_H // 2)


def draw_pause(surf, fonts, ui_fonts, buttons) -> None:
    _draw_veil(surf, 190)
    title = render_ui_outlined("ポーズ", fonts.screen_title, LOGO_FILL, outline=_BARK, outline_px=3)
    _centered(surf, title, 290)
    for button in buttons:
        button.draw(surf, ui_fonts.button, primary=button.action == "resume")


def draw_result(surf, match, fonts, ui_fonts, buttons) -> None:
    _draw_veil(surf, int(200 * match.result_dimness))
    if match.result_card_alpha <= 0.01:
        return
    alpha = int(255 * match.result_card_alpha)
    headline = render_ui_outlined(result_headline(match), ui_fonts.result, LOGO_FILL, outline=_BARK, outline_px=3)
    headline.set_alpha(alpha)
    _centered(surf, headline, 330)
    s0, s1 = match.scores
    score = render_ui_outlined(f"{s0}  -  {s1}", fonts.screen_title, MENU_TEXT, outline=_BARK, outline_px=3)
    score.set_alpha(alpha)
    _centered(surf, score, 410)
    mins, secs = int(match.match_time) // 60, int(match.match_time) % 60
    time_line = ui_fonts.small.render(f"試合時間 {mins:02d}:{secs:02d}", True, MENU_TEXT_DIM)
    time_line.set_alpha(alpha)
    _centered(surf, time_line, 478)
    for button in buttons:
        button.draw(surf, ui_fonts.button, primary=button.action == "rematch")
