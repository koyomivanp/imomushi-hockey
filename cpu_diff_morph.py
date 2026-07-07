"""CPU難易度 — タイトルボタンが変形して3択に分裂（スタッガー）"""

from __future__ import annotations

import math

import pygame

from ai import CPU_DIFFICULTY_ORDER, DIFFICULTIES
from constants import (
    CPU_LABEL,
    LOGO_FILL,
    MENU_BORDER,
    MENU_CARD_BORDER,
    MENU_PRIMARY_GLOW,
    MENU_TEXT_DIM,
    MENU_TITLE_GLOW,
    SCREEN_W,
    TITLE_MENU_H,
    TITLE_MENU_TOP,
    TITLE_MENU_W,
)
from title_typography import TitleFonts, render_ui_outlined

MORPH_DURATION = 0.95
SPLIT_START = 0.36
STAGGER_STEP = 0.1
SPLIT_DURATION = 0.38

_BTN_W = 148
_BTN_H = 48
_BTN_GAP = 14
_TARGET_Y = 248
_TOTAL_W = _BTN_W * 3 + _BTN_GAP * 2
_START_X = SCREEN_W // 2 - _TOTAL_W // 2

_SOURCE_CY = TITLE_MENU_TOP + TITLE_MENU_H // 2
_TARGET_CY = _TARGET_Y + _BTN_H // 2

_TARGET_CX = tuple(
    _START_X + i * (_BTN_W + _BTN_GAP) + _BTN_W // 2
    for i in range(3)
)

_BARK = (58, 38, 24)
_SOURCE_LABEL = f"vs {CPU_LABEL}"


def _clamp01(t: float) -> float:
    return max(0.0, min(1.0, t))


def _ease_out_cubic(t: float) -> float:
    t = _clamp01(t)
    return 1.0 - (1.0 - t) ** 3


def _ease_out_back(t: float, overshoot: float = 1.35) -> float:
    t = _clamp01(t)
    return 1.0 + (overshoot + 1.0) * (t - 1.0) ** 3 + overshoot * (t - 1.0) ** 2


def update_morph_progress(progress: float, dt: float) -> float:
    return min(1.0, progress + dt / MORPH_DURATION)


def morph_ready(progress: float) -> bool:
    return progress >= 1.0


def _button_rect(cx: float, cy: float, w: float, h: float) -> pygame.Rect:
    return pygame.Rect(0, 0, max(1, int(w)), max(1, int(h))).move(
        int(cx - w / 2), int(cy - h / 2),
    )


def _lerp_color(
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    t = _clamp01(t)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_selection_glow(
    surf: pygame.Surface,
    rect: pygame.Rect,
    *,
    strength: float,
    now: float,
) -> None:
    if strength <= 0.03:
        return
    pulse = 0.55 + 0.45 * math.sin(now * 5.2)
    for expand, alpha_mult in ((10, 0.42), (20, 0.24), (34, 0.13)):
        glow = pygame.Surface((rect.width + expand * 2, rect.height + expand * 2), pygame.SRCALPHA)
        inner = pygame.Rect(expand, expand, rect.width, rect.height)
        alpha = int((78 + 52 * pulse) * strength * alpha_mult)
        pygame.draw.rect(glow, (*MENU_PRIMARY_GLOW, alpha), inner, border_radius=14)
        surf.blit(glow, (rect.x - expand, rect.y - expand))


def _draw_button(
    surf: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    *,
    selected: bool = False,
    sel_strength: float | None = None,
    alpha: int = 255,
    text_alpha: int | None = None,
    outlined: bool = False,
    now: float = 0.0,
) -> None:
    if alpha <= 0:
        return
    s = _clamp01(sel_strength if sel_strength is not None else (1.0 if selected else 0.0))
    pulse = 0.5 + 0.5 * math.sin(now * 5.0)
    scale = 1.0 + 0.08 * s * (0.82 + 0.18 * pulse)
    draw_rect = rect.copy()
    if s > 0.02:
        grow_w = int(rect.width * (scale - 1.0))
        grow_h = int(rect.height * (scale - 1.0))
        draw_rect.inflate_ip(grow_w, grow_h)
        draw_rect.center = rect.center

    layer = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
    fill = _lerp_color((28, 44, 30), (42, 58, 44), s)
    border_col = _lerp_color(MENU_CARD_BORDER, MENU_BORDER, s)
    border_w = max(1, int(1 + s * 2.5))
    pygame.draw.rect(layer, (*fill, alpha), layer.get_rect(), border_radius=12)
    pygame.draw.rect(layer, (*border_col, alpha), layer.get_rect(), border_w, border_radius=12)

    if s > 0.12:
        bar_w = max(3, int(3 + 3 * s))
        bar_h = max(8, draw_rect.height - 16)
        bar = pygame.Rect(7, draw_rect.centery - draw_rect.y - bar_h // 2, bar_w, bar_h)
        bar_col = _lerp_color(MENU_BORDER, MENU_TITLE_GLOW, 0.35 + 0.65 * s * pulse)
        pygame.draw.rect(layer, (*bar_col, alpha), bar, border_radius=3)

    ta = alpha if text_alpha is None else text_alpha
    if label and draw_rect.height >= 14 and ta > 0:
        text_color = _lerp_color(MENU_TEXT_DIM, LOGO_FILL, s)
        if s > 0.45 or outlined:
            text = render_ui_outlined(label, font, text_color, outline=_BARK, outline_px=2)
        else:
            text = font.render(label, True, text_color)
        if ta < 255:
            text = text.copy()
            text.set_alpha(ta)
        layer.blit(text, text.get_rect(center=layer.get_rect().center))

    surf.blit(layer, draw_rect.topleft)

    if s > 0.05 and alpha >= 160:
        _draw_selection_glow(surf, draw_rect, strength=s * alpha / 255.0, now=now)


def draw_cpu_diff_morph(
    surf: pygame.Surface,
    fonts: TitleFonts,
    *,
    selected_index: int,
    sel_strengths: tuple[float, float, float] | None = None,
    progress: float,
    now: float = 0.0,
) -> None:
    p = _clamp01(progress)
    expand_t = _ease_out_cubic(p / SPLIT_START) if p < SPLIT_START else 1.0

    if p < SPLIT_START:
        w = TITLE_MENU_W + (_TOTAL_W - TITLE_MENU_W) * expand_t
        h = TITLE_MENU_H + (_BTN_H - TITLE_MENU_H) * expand_t
        cx = SCREEN_W / 2
        cy = _SOURCE_CY + (_TARGET_CY - _SOURCE_CY) * expand_t * 0.55
        pulse = 1.0 + 0.04 * (1.0 - abs(p * 8.0 - 1.0)) if p < 0.25 else 1.0
        w *= pulse
        h *= pulse
        label_alpha = int(255 * max(0.0, 1.0 - expand_t * 1.2))
        rect = _button_rect(cx, cy, w, h)
        _draw_button(
            surf, rect, _SOURCE_LABEL, fonts.menu,
            selected=True, sel_strength=1.0, alpha=255,
            text_alpha=max(0, label_alpha), outlined=False, now=now,
        )
    else:
        for i, key in enumerate(CPU_DIFFICULTY_ORDER):
            local_p = _clamp01((p - SPLIT_START - i * STAGGER_STEP) / SPLIT_DURATION)
            if local_p <= 0.0 and not morph_ready(p):
                continue
            ease = _ease_out_back(local_p)
            cx = SCREEN_W / 2 + (_TARGET_CX[i] - SCREEN_W / 2) * ease
            cy = _SOURCE_CY + (_TARGET_CY - _SOURCE_CY) * _ease_out_cubic(local_p)
            slot_w = _TOTAL_W / 3
            w = slot_w + (_BTN_W - slot_w) * ease
            h = TITLE_MENU_H + (_BTN_H - TITLE_MENU_H) * ease
            shell_alpha = 255 if morph_ready(p) else int(255 * _ease_out_cubic(local_p))
            label_alpha = int(255 * _ease_out_cubic(max(0.0, (local_p - 0.12) / 0.88)))
            rect = _button_rect(cx, cy, w, h)
            ready = morph_ready(p)
            selected = (i == selected_index and ready)
            strength = sel_strengths[i] if sel_strengths is not None else (1.0 if selected else 0.0)
            _draw_button(
                surf, rect, DIFFICULTIES[key].label, fonts.menu,
                selected=selected,
                sel_strength=strength if ready else 0.0,
                alpha=shell_alpha,
                text_alpha=label_alpha if label_alpha > 0 else (255 if ready else 0),
                outlined=ready and strength > 0.45,
                now=now,
            )

    if p > 0.55:
        heading_alpha = int(255 * min(1.0, (p - 0.55) / 0.3))
        heading = render_ui_outlined(
            "CPUの強さ", fonts.screen_title, LOGO_FILL, outline=_BARK, outline_px=3,
        )
        heading.set_alpha(heading_alpha)
        surf.blit(heading, heading.get_rect(center=(SCREEN_W // 2, 168)))
