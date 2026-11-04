"""スマホ縦画面の画面構成 — 「絵本の庭」

試合ロジックは横画面(800x600)の座標のまま。ここで縦画面(540x960)へ直接描く。
"""

from __future__ import annotations

import math

import pygame

import tuning
from ai import CPU_DIFFICULTY_ORDER, DIFFICULTIES
from constants import (
    CPU_LABEL,
    GO_DISPLAY_DURATION,
    MOBILE_BUTTON_POP_DURATION,
    MOBILE_H,
    MOBILE_HELP_LINES,
    MOBILE_TAIL_SHRINK_TIME,
    MOBILE_W,
    PB_CREAM,
    PB_INK,
    PB_P1,
    PB_P2,
    PB_PINK,
    PB_SUN,
    PB_WHITE,
    TITLE_CATCH_COPY,
)
from game import GameState
from mobile_art import (
    court_screen_rect,
    court_surface,
    dash_tail_points,
    draw_face,
    draw_ladybug,
    draw_logo,
    draw_pause_button,
    draw_pill,
    draw_title_ladybug,
    draw_title_worm,
    draw_tube,
    logic_heading_to_screen,
    logic_to_screen,
    scaled,
    score_badge,
    screen_dir_to_logic,
    text,
    text_fit,
    title_backdrop,
)
from screens import result_headline

__all__ = [
    "Button",
    "blit_cached_screen",
    "draw_countdown",
    "draw_help",
    "draw_match",
    "draw_pause",
    "draw_result",
    "draw_title",
    "help_buttons",
    "hit_button",
    "logic_to_screen",
    "pause_button_rect",
    "pause_buttons",
    "result_buttons",
    "screen_dir_to_logic",
    "title_buttons",
]


class Button:
    def __init__(self, rect: pygame.Rect, label: str, action: str, *, fill=PB_CREAM, size: int = 30) -> None:
        self.rect = rect
        self.label = label
        self.action = action
        self.fill = fill
        self.size = size

    def draw(self, surf: pygame.Surface, *, pop: float = 0.0, selected: bool = False) -> None:
        fill = PB_SUN if selected else self.fill
        draw_pill(surf, self.rect, fill, pressed=pop, label=self.label, label_size=self.size)


def _pill(y: int, label: str, action: str, *, h: int = 78, w: int = 420, fill=PB_CREAM, size: int = 30) -> Button:
    return Button(pygame.Rect((MOBILE_W - w) // 2, y, w, h), label, action, fill=fill, size=size)


# --- 画面ごとのボタン ---

def title_buttons(bgm_muted: bool, cpu_diff_index: int = 1) -> list[Button]:
    w, gap, h = 150, 12, 66
    left = (MOBILE_W - (w * 3 + gap * 2)) // 2
    buttons = [
        Button(pygame.Rect(left + i * (w + gap), 430, w, h), DIFFICULTIES[key].label, f"cpu_diff:{i}", size=27)
        for i, key in enumerate(CPU_DIFFICULTY_ORDER)
    ]
    buttons.append(_pill(518, "CPU芋虫と対戦", f"cpu:{cpu_diff_index}", h=88, fill=PB_SUN, size=34))
    buttons.append(_pill(622, "2匹で対戦", "two_player", h=78))
    buttons.append(_pill(714, "遊び方", "help", h=66, w=320, size=28))
    buttons.append(_pill(794, "BGM: オフ" if bgm_muted else "BGM: オン", "bgm", h=58, w=280, size=25))
    return buttons


def help_buttons() -> list[Button]:
    return [_pill(MOBILE_H - 128, "とじる", "close_help", h=76, w=320, fill=PB_SUN, size=32)]


def pause_button_rect() -> pygame.Rect:
    return pygame.Rect(MOBILE_W - 92, 22, 64, 64)


def pause_buttons(bgm_muted: bool) -> list[Button]:
    return [
        _pill(392, "つづける", "resume", h=84, fill=PB_SUN, size=34),
        _pill(492, "BGM: オフ" if bgm_muted else "BGM: オン", "bgm", h=72),
        _pill(580, "タイトルへ", "to_title", h=72),
    ]


def result_buttons() -> list[Button]:
    return [
        _pill(640, "もう一度", "rematch", h=84, fill=PB_SUN, size=34),
        _pill(742, "タイトルへ", "to_title", h=76),
    ]


def hit_button(buttons: list[Button], x: float, y: float) -> str | None:
    for button in buttons:
        if button.rect.collidepoint(x, y):
            return button.action
    return None


def button_pop(action: str, pressed_action: str | None, pressed_at: float, now: float) -> float:
    """押したボタンだけ弾ませる（0→1→0）"""
    if pressed_action != action:
        return 0.0
    t = (now - pressed_at) / MOBILE_BUTTON_POP_DURATION
    if t < 0.0 or t > 1.0:
        return 0.0
    return math.sin(t * math.pi)


def _draw_buttons(surf, buttons, *, pressed_action=None, pressed_at=0.0, now=0.0, selected_action=None) -> None:
    for button in buttons:
        button.draw(
            surf,
            pop=button_pop(button.action, pressed_action, pressed_at, now),
            selected=button.action == selected_action,
        )


# --- 芋虫（体節＋頭を1本のチューブとして描く） ---

def _chain_points(fences, now: float) -> list[list[tuple[float, float]]]:
    """つながっている体節をひとつながりの点列にする（論理座標）"""
    chains: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    prev_end: tuple[float, float] | None = None
    for fence in sorted(fences, key=lambda f: f.created_at):
        start = (fence.x1, fence.y1)
        if prev_end is None or math.hypot(start[0] - prev_end[0], start[1] - prev_end[1]) > 1.5:
            if len(current) >= 2:
                chains.append(current)
            current = [start, (fence.x2, fence.y2)]
            tail_fence = fence
        else:
            current.append((fence.x2, fence.y2))
        prev_end = (fence.x2, fence.y2)
        if len(current) == 2:
            # 尻尾側の体節が消えるときは、尻尾から縮むように見せる
            remaining = tail_fence.until - now
            if remaining < MOBILE_TAIL_SHRINK_TIME:
                k = max(0.0, min(1.0, 1.0 - remaining / MOBILE_TAIL_SHRINK_TIME))
                x0, y0 = current[0]
                x1, y1 = current[1]
                current[0] = (x0 + (x1 - x0) * k, y0 + (y1 - y0) * k)
    if len(current) >= 2:
        chains.append(current)
    return chains


def draw_worm(surf: pygame.Surface, match, player: int, now: float, offset: tuple[float, float]) -> None:
    paddle = match.paddles[player]
    radius = scaled(tuning.body_radius())
    ox, oy = offset
    fences = [f for f in match.fences if f.owner == player]
    chains = _chain_points(fences, now)
    head_x, head_y = logic_to_screen(paddle.x, paddle.y)
    head_x += ox
    head_y += oy
    heading = logic_heading_to_screen(paddle.face_heading)

    max_gap = tuning.trail_max_gap() * 1.35
    for i, chain in enumerate(chains):
        pts = [(*map(sum, zip(logic_to_screen(x, y), (ox, oy))), radius) for x, y in chain]
        newest = chain[-1]
        if (
            i == len(chains) - 1
            and not paddle.is_dashing
            and math.hypot(newest[0] - paddle.x, newest[1] - paddle.y) <= max_gap
        ):
            pts.append((head_x, head_y, radius))
        draw_tube(surf, pts, player)

    if paddle.is_dashing:
        draw_tube(surf, dash_tail_points(head_x, head_y, heading, radius, now), player)
    else:
        draw_tube(surf, [(head_x, head_y, radius)], player)
    draw_face(surf, head_x, head_y, radius, heading, player)


# --- 試合画面 ---

def draw_match(surf: pygame.Surface, match, now: float, fx=None, shake: tuple[float, float] = (0.0, 0.0)) -> None:
    ox, oy = shake
    if ox or oy:
        surf.fill(PB_INK)
    surf.blit(court_surface(), (ox, oy))

    for player in (0, 1):
        draw_worm(surf, match, player, now, (ox, oy))

    puck_r = scaled(tuning.puck_radius())
    for puck in match.pucks:
        px, py = logic_to_screen(puck.x, puck.y)
        heading = logic_heading_to_screen(math.atan2(puck.vy, puck.vx))
        draw_ladybug(surf, px + ox, py + oy, puck_r, heading)

    if fx is not None:
        fx.draw(surf)


def draw_score(surf: pygame.Surface, match, *, pause_pop: float = 0.0) -> None:
    court = court_screen_rect()
    top = score_badge(1, match.scores[1])
    bottom = score_badge(0, match.scores[0])
    surf.blit(top, top.get_rect(center=(66, court.top + 36)))
    surf.blit(bottom, bottom.get_rect(center=(66, court.bottom - 36)))
    label_top = text(CPU_LABEL if match.vs_cpu else "P2", 22, PB_INK)
    label_bottom = text("あなた" if match.vs_cpu else "P1", 22, PB_INK)
    surf.blit(label_top, label_top.get_rect(center=(66, court.top - 26)))
    surf.blit(label_bottom, label_bottom.get_rect(center=(66, court.bottom + 26)))
    draw_pause_button(surf, pause_button_rect(), pause_pop)


def draw_countdown(surf: pygame.Surface, match, now: float) -> None:
    if match.state == GameState.COUNTDOWN and match.countdown > 0:
        shown = max(0.0, min(1.0, 1.0 - match.countdown_timer))  # 数字が出てからの経過
        scale = 1.0 + 0.45 * (1.0 - shown * 4.0) if shown < 0.25 else 1.0
        glyph = text(str(match.countdown), 180, PB_SUN, outline=PB_INK, outline_px=9)
        zoomed = pygame.transform.rotozoom(glyph, 0, max(0.3, scale))
        surf.blit(zoomed, zoomed.get_rect(center=(MOBILE_W // 2, MOBILE_H // 2)))
    elif match.go_timer > 0.0:
        k = min(1.0, match.go_timer / (GO_DISPLAY_DURATION * 0.6))
        glyph = text("GO!", 150, PB_PINK, outline=PB_INK, outline_px=9)
        zoomed = pygame.transform.rotozoom(glyph, 0, 0.9 + 0.5 * (1.0 - k))
        zoomed.set_alpha(int(255 * k))
        surf.blit(zoomed, zoomed.get_rect(center=(MOBILE_W // 2, MOBILE_H // 2)))


# --- タイトル・遊び方・ポーズ・結果 ---

PB_LOGO_ACCENT = (210, 66, 60)

_veil_cache: dict[int, pygame.Surface] = {}


def _veil(surf: pygame.Surface, alpha: int) -> None:
    cached = _veil_cache.get(alpha)
    if cached is None:
        cached = pygame.Surface((MOBILE_W, MOBILE_H), pygame.SRCALPHA)
        cached.fill((*PB_CREAM, alpha))
        _veil_cache[alpha] = cached
    surf.blit(cached, (0, 0))


def _centered(surf: pygame.Surface, glyph: pygame.Surface, y: int) -> None:
    surf.blit(glyph, glyph.get_rect(center=(MOBILE_W // 2, y)))


def draw_title(surf, now: float, *, cpu_diff_index: int, buttons, pressed_action=None, pressed_at=0.0) -> None:
    surf.blit(title_backdrop(), (0, 0))
    draw_logo(surf, (MOBILE_W // 2, 152), now)
    _centered(surf, text_fit(TITLE_CATCH_COPY, 26, PB_INK), 276)
    draw_title_worm(surf, now)
    draw_title_ladybug(surf, now)
    _centered(surf, text(f"つよさ（vs {CPU_LABEL}）", 24, PB_INK), 404)
    _draw_buttons(
        surf, buttons, pressed_action=pressed_action, pressed_at=pressed_at, now=now,
        selected_action=f"cpu_diff:{cpu_diff_index}",
    )


def draw_help(surf, now: float, buttons, pressed_action=None, pressed_at=0.0) -> None:
    surf.blit(title_backdrop(), (0, 0))
    _veil(surf, 225)
    _centered(surf, text("遊び方", 56, PB_INK), 86)
    y = 152
    for heading, body in MOBILE_HELP_LINES:
        glyph = text(heading, 28, PB_LOGO_ACCENT)
        surf.blit(glyph, (44, y))
        y += glyph.get_height() + 6
        for line in body:
            row = text_fit(line, 22, PB_INK, max_width=MOBILE_W - 88, medium=True)
            surf.blit(row, (44, y))
            y += row.get_height() + 5
        y += 18
    _draw_buttons(surf, buttons, pressed_action=pressed_action, pressed_at=pressed_at, now=now)


def draw_pause(surf, buttons, now: float = 0.0, pressed_action=None, pressed_at=0.0) -> None:
    _veil(surf, 215)
    _centered(surf, text("ポーズ", 64, PB_INK), 288)
    _draw_buttons(surf, buttons, pressed_action=pressed_action, pressed_at=pressed_at, now=now)


def draw_result(surf, match, buttons, butterfly=None, now: float = 0.0,
                pressed_action=None, pressed_at=0.0) -> None:
    _veil(surf, int(215 * match.result_dimness))
    if butterfly is not None:
        butterfly.draw(surf)
    if match.result_card_alpha <= 0.01:
        return
    alpha = int(255 * match.result_card_alpha)
    color = PB_P1 if match.winner == 0 else PB_P2
    headline = text_fit(result_headline(match), 54, color, outline=PB_INK, outline_px=6)
    headline.set_alpha(alpha)
    _centered(surf, headline, 180)
    score = text(f"{match.scores[0]}  -  {match.scores[1]}", 72, PB_INK)
    score.set_alpha(alpha)
    _centered(surf, score, 272)
    mins, secs = int(match.match_time) // 60, int(match.match_time) % 60
    time_line = text(f"試合時間 {mins:02d}:{secs:02d}", 24, PB_INK, medium=True)
    time_line.set_alpha(alpha)
    _centered(surf, time_line, 338)
    _draw_buttons(surf, buttons, pressed_action=pressed_action, pressed_at=pressed_at, now=now)


# --- 画面キャッシュ（変化しない画面は焼いて使い回す） ---

_screen_cache_key: object = None
_screen_cache: pygame.Surface | None = None


def blit_cached_screen(surf: pygame.Surface, key: object, build) -> None:
    global _screen_cache, _screen_cache_key
    if _screen_cache is None or _screen_cache_key != key:
        _screen_cache = pygame.Surface((MOBILE_W, MOBILE_H)).convert()
        build(_screen_cache)
        _screen_cache_key = key
    surf.blit(_screen_cache, (0, 0))


def goal_screen_pos(match) -> tuple[float, float]:
    """直前に決まったゴールの位置（演出の発生点）"""
    court = court_screen_rect()
    if match.score_pop_player == 1:
        return MOBILE_W / 2, court.top + 40
    return MOBILE_W / 2, court.bottom - 40

