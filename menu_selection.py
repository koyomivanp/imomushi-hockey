"""メニュー選択ハイライト — スムーズ移動と選択演出"""

from __future__ import annotations

import math


SEL_MOVE_SPEED = 16.0
SEL_PULSE_SPEED = 4.8
SEL_BUMP_DECAY = 9.0
SEL_BUMP_AMOUNT = 0.11


def _clamp01(t: float) -> float:
    return max(0.0, min(1.0, t))


def selection_strength(pos: float, item_index: int) -> float:
    """項目ごとの選択度（0–1）。pos が整数間を移動するとき中間値も出る。"""
    dist = abs(pos - float(item_index))
    if dist >= 1.0:
        return 0.0
    t = 1.0 - dist
    return t * t * (3.0 - 2.0 * t)


class SelectionHighlight:
    """カーソル位置を滑らかに追従させ、選択中のパルスを出す。"""

    def __init__(self, index: int = 0) -> None:
        self.index = index
        self.pos = float(index)
        self.pulse = 0.0
        self.bump = 0.0

    def snap_to(self, index: int) -> None:
        self.index = index
        self.pos = float(index)
        self.bump = SEL_BUMP_AMOUNT

    def set_index(self, index: int) -> None:
        if index != self.index:
            self.index = index
            self.bump = SEL_BUMP_AMOUNT

    def update(self, dt: float, target_index: int) -> None:
        self.set_index(target_index)
        delta = float(target_index) - self.pos
        self.pos += delta * min(1.0, dt * SEL_MOVE_SPEED)
        if abs(delta) < 0.0005:
            self.pos = float(target_index)
        self.pulse += dt * SEL_PULSE_SPEED
        if self.bump > 0.0:
            self.bump = max(0.0, self.bump - dt * SEL_BUMP_DECAY)

    def strength(self, item_index: int) -> float:
        return selection_strength(self.pos, item_index)

    def pulse_scale(self) -> float:
        wave = 0.5 + 0.5 * math.sin(self.pulse)
        return 1.0 + 0.045 * wave + self.bump
