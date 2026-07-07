"""対戦画面 HUD — 左右2本の連続スコアゲージ（得点で少しずつ満ちる）"""

from __future__ import annotations

import math

import pygame

from constants import (
    HUD_H,
    HUD_PLAQUE_H,
    HUD_PLAQUE_TOP,
    LOGO_FILL,
    MENU_BG,
    MENU_BORDER,
    P1_COLOR,
    P2_COLOR,
    SCORE_BAR_FULL_PULSE_DURATION,
    SCORE_POP_DURATION,
    SCREEN_W,
    WIN_SCORE,
)
from effects import score_segment_glow_strength, score_segment_light_progress
from entities import arena_frame_rect
from result_flow import ResultPhase, bar_full_overshoot
from title_typography import TitleFonts

_GAUGE_CENTER_GAP = 10
_SLOT_OFF = (12, 20, 14)
_SLOT_MID = (20, 32, 22)
_SLOT_EDGE = (48, 36, 26)
_BARK = (58, 38, 24)
_BEAM_TOP = (88, 68, 48)
_BEAM_BODY = (18, 32, 22)
_BEAM_INNER = (26, 40, 28)


def _hud_bar_rect() -> pygame.Rect:
    frame = arena_frame_rect()
    return pygame.Rect(frame.left, HUD_PLAQUE_TOP, frame.width, HUD_PLAQUE_H)


def _gauge_halves(bar: pygame.Rect) -> tuple[pygame.Rect, pygame.Rect]:
    inner = bar.inflate(-8, -10)
    half_w = max(24, (inner.width - _GAUGE_CENTER_GAP) // 2)
    p1 = pygame.Rect(inner.left, inner.top, half_w, inner.height)
    p2 = pygame.Rect(inner.right - half_w, inner.top, half_w, inner.height)
    return p1, p2


def _draw_hud_zone_backdrop(surf: pygame.Surface, bar: pygame.Rect) -> None:
    zone_h = max(HUD_H + 8, bar.bottom + 2)
    surf.fill(MENU_BG, pygame.Rect(0, 0, SCREEN_W, zone_h))

    for side_rect in (
        pygame.Rect(0, 0, bar.left, zone_h),
        pygame.Rect(bar.right, 0, SCREEN_W - bar.right, zone_h),
    ):
        if side_rect.width <= 0:
            continue
        shade = pygame.Surface(side_rect.size, pygame.SRCALPHA)
        shade.fill((4, 10, 6, 72))
        surf.blit(shade, side_rect.topleft)

    wash = pygame.Surface((bar.width, zone_h), pygame.SRCALPHA)
    for y in range(0, zone_h, 14):
        pygame.draw.line(wash, (18, 32, 22, 28), (8, y), (bar.width - 8, y + 3), 1)
    surf.blit(wash, (bar.left, 0))


def _draw_score_bar_frame(surf: pygame.Surface, bar: pygame.Rect) -> None:
    shadow = pygame.Surface((bar.width + 6, 10), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 36), shadow.get_rect())
    surf.blit(shadow, (bar.left - 3, bar.bottom - 4))

    pygame.draw.rect(surf, _BEAM_BODY, bar, border_radius=8)
    inner = bar.inflate(-6, -8)
    pygame.draw.rect(surf, _BEAM_INNER, inner, border_radius=6)
    grain = pygame.Surface(inner.size, pygame.SRCALPHA)
    for y in range(0, inner.height, 9):
        pygame.draw.line(grain, (42, 58, 44, 22), (4, y), (inner.width - 4, y + 2), 1)
    surf.blit(grain, inner.topleft)
    pygame.draw.line(surf, _BEAM_TOP, (bar.left + 10, bar.top + 5), (bar.right - 10, bar.top + 5), 1)
    pygame.draw.line(surf, _BARK, (bar.left + 8, bar.bottom - 2), (bar.right - 8, bar.bottom - 2), 2)
    pygame.draw.rect(surf, _BARK, bar, 2, border_radius=8)


def _draw_gauge_off(surf: pygame.Surface, rect: pygame.Rect) -> None:
    slot = rect.inflate(-2, -4)
    pygame.draw.rect(surf, _SLOT_OFF, slot, border_radius=4)
    pygame.draw.rect(surf, _SLOT_MID, slot.inflate(-2, -2), border_radius=3)
    pygame.draw.line(
        surf, _SLOT_EDGE,
        (slot.left + 4, slot.top + 3),
        (slot.right - 4, slot.top + 3), 1,
    )
    groove = pygame.Surface((slot.width, max(4, slot.height // 3)), pygame.SRCALPHA)
    groove.fill((6, 10, 8, 48))
    surf.blit(groove, (slot.left, slot.bottom - groove.get_height()))


def _lerp_rgb(
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_gauge_fill(
    surf: pygame.Surface,
    rect: pygame.Rect,
    color: tuple[int, int, int],
    *,
    fill_ratio: float,
    fill_from_left: bool,
    glow: float = 0.0,
    pulse: float = 1.0,
    bar_full: bool = False,
    full_pulse: float = 0.0,
) -> None:
    slot = rect.inflate(-2, -4)
    ratio = max(0.0, min(1.12, fill_ratio))
    if bar_full and full_pulse > 0.0 and fill_ratio >= 0.999:
        ratio = bar_full_overshoot(full_pulse)
    if ratio <= 0.001:
        return

    fill_w = max(2, int(slot.width * ratio))
    if fill_from_left:
        fill_left = slot.left
        local_fill = pygame.Rect(0, 0, fill_w, slot.height)
        crest_local_x = fill_w - 1
    else:
        fill_left = slot.right - fill_w
        local_fill = pygame.Rect(slot.width - fill_w, 0, fill_w, slot.height)
        crest_local_x = local_fill.left

    bloom_strength = glow + (0.65 if bar_full and full_pulse > 0.0 else 0.0)
    if bloom_strength > 0.02:
        bloom = pygame.Surface((fill_w + 18, slot.height + 16), pygame.SRCALPHA)
        bloom_rect = bloom.get_rect()
        bloom_rect.inflate_ip(4, 4)
        pygame.draw.ellipse(
            bloom,
            (*color, int(58 * bloom_strength)),
            bloom_rect,
        )
        surf.blit(bloom, (fill_left - 9, slot.top - 7))

    layer = pygame.Surface(slot.size, pygame.SRCALPHA)
    base = _lerp_rgb(_SLOT_MID, color, 0.35 + 0.25 * pulse)
    dark = _lerp_rgb(_SLOT_OFF, color, 0.55)
    lit_edge = _lerp_rgb(color, LOGO_FILL, 0.18 * pulse)

    pygame.draw.rect(layer, dark, local_fill, border_radius=3)
    pygame.draw.rect(layer, base, local_fill, border_radius=3)
    if fill_w > 5:
        shine_w = max(2, min(6, fill_w // 4))
        if fill_from_left:
            shine = pygame.Rect(local_fill.right - shine_w, 0, shine_w, slot.height)
        else:
            shine = pygame.Rect(local_fill.left, 0, shine_w, slot.height)
        pygame.draw.rect(layer, lit_edge, shine, border_radius=2)
        crest_y0, crest_y1 = 4, slot.height - 4
        crest_alpha = int(150 + 80 * bloom_strength)
        pygame.draw.line(
            layer,
            (*LOGO_FILL, crest_alpha),
            (crest_local_x, crest_y0),
            (crest_local_x, crest_y1),
            max(1, shine_w),
        )

    surf.blit(layer, slot.topleft)
    pygame.draw.rect(surf, _SLOT_EDGE, slot, 1, border_radius=4)

    if bar_full and full_pulse > 0.0:
        beam = pygame.Surface((slot.width + 12, slot.height + 10), pygame.SRCALPHA)
        beam_alpha = int(42 * math.sin(full_pulse * math.pi))
        if beam_alpha > 0:
            pygame.draw.rect(
                beam,
                (*color, beam_alpha),
                beam.get_rect().inflate(-8, -6),
                border_radius=5,
            )
            surf.blit(beam, (slot.left - 6, slot.top - 4))


def _team_color(
    base: tuple[int, int, int],
    *,
    near_win: bool,
    on_match_point: bool,
    pulse: float,
) -> tuple[int, int, int]:
    if near_win and on_match_point:
        boost = 0.86 + 0.14 * pulse
        return tuple(min(255, int(c * boost)) for c in base)
    return base


def _gauge_fill_ratio(
    score: int,
    *,
    is_popping: bool,
    pop_timer: float,
    pop_duration: float,
) -> float:
    if score <= 0:
        return 0.0
    target = score / WIN_SCORE
    if not is_popping:
        return target
    prev = (score - 1) / WIN_SCORE
    t = score_segment_light_progress(pop_timer, pop_duration)
    return prev + (target - prev) * t


def draw_score_gauges(
    surf: pygame.Surface,
    s0: int,
    s1: int,
    gauges: tuple[pygame.Rect, pygame.Rect],
    *,
    pulse: float = 1.0,
    near_win: bool = False,
    pop_player: int | None = None,
    pop_timer: float = 0.0,
    pop_duration: float = SCORE_POP_DURATION,
    winner: int | None = None,
    result_phase: ResultPhase | None = None,
    result_phase_progress: float = 0.0,
) -> None:
    pop_id = -1 if pop_player is None else pop_player
    teams = (
        (0, s0, gauges[0], P1_COLOR, True),
        (1, s1, gauges[1], P2_COLOR, False),
    )

    for player, score, rect, base_color, fill_from_left in teams:
        pygame.draw.rect(surf, _BARK, rect.inflate(1, 1), 1, border_radius=4)
        _draw_gauge_off(surf, rect)

        if score <= 0:
            continue

        on_match = score >= WIN_SCORE - 1
        color = _team_color(
            base_color, near_win=near_win, on_match_point=on_match, pulse=pulse,
        )
        is_popping = pop_id == player and pop_timer > 0.0
        fill = _gauge_fill_ratio(
            score, is_popping=is_popping, pop_timer=pop_timer, pop_duration=pop_duration,
        )
        glow = score_segment_glow_strength(pop_timer, pop_duration) if is_popping else 0.0

        bar_full = winner == player and score >= WIN_SCORE
        full_pulse = 0.0
        if bar_full and result_phase is not None:
            if result_phase == ResultPhase.CELEBRATE:
                full_pulse = min(1.0, result_phase_progress / SCORE_BAR_FULL_PULSE_DURATION)
            else:
                full_pulse = 1.0

        _draw_gauge_fill(
            surf, rect, color,
            fill_ratio=fill,
            fill_from_left=fill_from_left,
            glow=glow,
            pulse=pulse if on_match else 1.0,
            bar_full=bar_full,
            full_pulse=full_pulse,
        )


def draw_match_hud(
    surf: pygame.Surface,
    match,
    fonts: TitleFonts,
    now: float,
    *,
    bgm_muted: bool = False,
) -> None:
    _ = fonts, bgm_muted
    bar = _hud_bar_rect()
    gauges = _gauge_halves(bar)

    _draw_hud_zone_backdrop(surf, bar)
    _draw_score_bar_frame(surf, bar)

    s0, s1 = match.scores
    near_win = max(s0, s1) >= WIN_SCORE - 1
    pulse = 0.9 + 0.1 * math.sin(now * 3.0) if near_win else 1.0
    result_phase = getattr(match, "result_phase", None)
    draw_score_gauges(
        surf, s0, s1, gauges,
        pulse=pulse,
        near_win=near_win,
        pop_player=getattr(match, "score_pop_player", None),
        pop_timer=getattr(match, "score_pop_timer", 0.0),
        winner=getattr(match, "winner", None),
        result_phase=result_phase,
        result_phase_progress=getattr(match, "result_phase_progress", 0.0),
    )

    frame = arena_frame_rect()
    if frame.top > bar.bottom:
        post_h = frame.top - bar.bottom
        for px in (bar.left + 3, bar.right - 5):
            pygame.draw.rect(surf, (48, 34, 22), (px, bar.bottom, 4, post_h))
            pygame.draw.line(surf, MENU_BORDER, (px + 1, bar.bottom), (px + 1, bar.bottom + post_h), 1)


draw_score_segments = draw_score_gauges
draw_score_pips = draw_score_gauges
draw_score_leaves = draw_score_gauges
