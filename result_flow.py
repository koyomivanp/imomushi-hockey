"""試合終了シネマ — バー満タン → 暗転 → リザルトカード入場"""

from __future__ import annotations

import math
from enum import Enum, auto

import pygame

from constants import (
    RESULT_CARD_IN_DURATION,
    RESULT_CELEBRATE_DURATION,
    RESULT_DIM_DURATION,
    SCREEN_H,
    SCREEN_W,
)


class ResultPhase(Enum):
    CELEBRATE = auto()
    DIM = auto()
    CARD_IN = auto()
    HOLD = auto()


def ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def ease_out_back(t: float, overshoot: float = 1.35) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 + (overshoot + 1.0) * (t - 1.0) ** 3 + overshoot * (t - 1.0) ** 2


def phase_duration(phase: ResultPhase) -> float:
    if phase == ResultPhase.CELEBRATE:
        return RESULT_CELEBRATE_DURATION
    if phase == ResultPhase.DIM:
        return RESULT_DIM_DURATION
    if phase == ResultPhase.CARD_IN:
        return RESULT_CARD_IN_DURATION
    return 0.0


def normalized_progress(phase: ResultPhase, elapsed: float) -> float:
    dur = phase_duration(phase)
    if dur <= 0.0:
        return 1.0
    return min(1.0, elapsed / dur)


def bar_full_overshoot(progress: float) -> float:
    """満タン時のゲージ先端オーバーシュート（1.0 を少し超えて戻る）"""
    t = max(0.0, min(1.0, progress))
    if t < 0.55:
        return ease_out_back(t / 0.55) * 1.08
    return 1.0 + (1.08 - 1.0) * (1.0 - ease_out_cubic((t - 0.55) / 0.45))


def draw_result_dim_overlay(surf: pygame.Surface, darkness: float) -> None:
    """リザルト暗転（0=なし, 1=フル）"""
    cover = max(0.0, min(1.0, darkness))
    if cover <= 0.01:
        return
    layer = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    layer.fill((4, 8, 6, int(200 * cover)))
    surf.blit(layer, (0, 0))
