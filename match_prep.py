"""試合前シネマ — 暗転 → TIPS → コート明転"""

from __future__ import annotations

import math
from enum import Enum, auto

import pygame

from constants import (
    PREP_DARKEN_DURATION,
    PREP_REVEAL_DURATION,
    SCREEN_H,
    SCREEN_W,
    TIPS_DISPLAY_DURATION,
    TIPS_FADE_IN_DURATION,
    TIPS_FADE_OUT_DURATION,
)


class PrepPhase(Enum):
    DARKEN = auto()
    TIPS_IN = auto()
    TIPS_HOLD = auto()
    TIPS_OUT = auto()
    REVEAL = auto()


def ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def phase_duration(phase: PrepPhase) -> float:
    if phase == PrepPhase.DARKEN:
        return PREP_DARKEN_DURATION
    if phase == PrepPhase.TIPS_IN:
        return TIPS_FADE_IN_DURATION
    if phase == PrepPhase.TIPS_HOLD:
        return TIPS_DISPLAY_DURATION
    if phase == PrepPhase.TIPS_OUT:
        return TIPS_FADE_OUT_DURATION
    return PREP_REVEAL_DURATION


def normalized_progress(phase: PrepPhase, elapsed: float) -> float:
    dur = phase_duration(phase)
    if dur <= 0.0:
        return 1.0
    return min(1.0, elapsed / dur)


def draw_cinematic_veil(surf: pygame.Surface, darkness: float, reveal: float) -> None:
    """darkness 0–1 で暗く、reveal 0–1 で明転（コート露出）"""
    cover = max(0.0, min(1.0, darkness * (1.0 - reveal)))
    if cover <= 0.01:
        return

    layer = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    base_a = int(215 * cover)
    layer.fill((4, 8, 6, base_a))

    for i in range(6):
        margin = 8 + i * 24
        ring_a = int((28 + i * 16) * cover)
        pygame.draw.rect(
            layer,
            (2, 5, 4, ring_a),
            pygame.Rect(margin, margin, SCREEN_W - margin * 2, SCREEN_H - margin * 2),
            width=20,
        )

    cx, cy = SCREEN_W // 2, SCREEN_H // 2
    for r in range(280, 0, -12):
        t = 1.0 - r / 280.0
        alpha = int(18 * t * cover)
        if alpha > 0:
            pygame.draw.circle(layer, (8, 14, 10, alpha), (cx, cy), r)

    surf.blit(layer, (0, 0))
