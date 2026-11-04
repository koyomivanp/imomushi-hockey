"""スマホ操作 — 指を置いてなぞると這い、素早くはじくとダッシュ（座標は縦画面の論理px）"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from constants import (
    FLICK_DASH_DURATION,
    FLICK_MIN_DISTANCE,
    FLICK_RELEASE_WINDOW,
    FLICK_SAMPLE_WINDOW,
    FLICK_SPEED,
    STICK_DEADZONE,
    STICK_RADIUS,
)


def _unit(dx: float, dy: float) -> tuple[float, float]:
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return 0.0, 0.0
    return dx / d, dy / d


@dataclass
class FlickStick:
    """1人分の操作。指の接地点からの向きで這い、指の速さがしきい値を超えるとダッシュ"""

    finger: int | None = None
    anchor_x: float = 0.0
    anchor_y: float = 0.0
    x: float = 0.0
    y: float = 0.0
    start_x: float = 0.0
    start_y: float = 0.0
    start_t: float = 0.0
    dash_dir: tuple[float, float] = (0.0, 0.0)
    dash_until: float = 0.0
    samples: list[tuple[float, float, float]] = field(default_factory=list)

    def press(self, finger: int, x: float, y: float, t: float) -> bool:
        if self.finger is not None:
            return False
        self.finger = finger
        self.anchor_x = self.start_x = self.x = x
        self.anchor_y = self.start_y = self.y = y
        self.start_t = t
        self.samples = [(t, x, y)]
        return True

    def _begin_dash(self, dx: float, dy: float, t: float) -> None:
        self.dash_dir = _unit(dx, dy)
        self.dash_until = t + FLICK_DASH_DURATION

    def move(self, finger: int, x: float, y: float, t: float) -> None:
        if finger != self.finger:
            return
        self.x, self.y = x, y
        self.samples.append((t, x, y))
        self.samples = [s for s in self.samples if t - s[0] <= FLICK_SAMPLE_WINDOW]

        oldest_t, oldest_x, oldest_y = self.samples[0]
        dx, dy = x - oldest_x, y - oldest_y
        travel = math.hypot(dx, dy)
        elapsed = t - oldest_t
        if elapsed > 1e-6 and travel >= FLICK_MIN_DISTANCE and travel / elapsed >= FLICK_SPEED:
            self._begin_dash(dx, dy, t)

        # 接地点を指に追従させ、切り返しをすぐ効かせる
        ax, ay = x - self.anchor_x, y - self.anchor_y
        dist = math.hypot(ax, ay)
        if dist > STICK_RADIUS:
            self.anchor_x = x - ax / dist * STICK_RADIUS
            self.anchor_y = y - ay / dist * STICK_RADIUS

    def release(self, finger: int, x: float, y: float, t: float) -> None:
        if finger != self.finger:
            return
        dx, dy = x - self.start_x, y - self.start_y
        if t - self.start_t <= FLICK_RELEASE_WINDOW and math.hypot(dx, dy) >= FLICK_MIN_DISTANCE:
            self._begin_dash(dx, dy, t)
        self.finger = None
        self.samples = []

    def reset(self) -> None:
        self.finger = None
        self.samples = []
        self.dash_until = 0.0

    def output(self, t: float) -> tuple[float, float, bool]:
        """画面座標の向き (dx, dy) とダッシュ中か"""
        if t < self.dash_until:
            return self.dash_dir[0], self.dash_dir[1], True
        if self.finger is None:
            return 0.0, 0.0, False
        dx, dy = self.x - self.anchor_x, self.y - self.anchor_y
        if math.hypot(dx, dy) < STICK_DEADZONE:
            return 0.0, 0.0, False
        ux, uy = _unit(dx, dy)
        return ux, uy, False


class TouchControls:
    """指を担当プレイヤーへ振り分ける。下半分=P1、上半分=P2（CPU戦は全面 P1）"""

    def __init__(self, screen_h: int) -> None:
        self.screen_h = screen_h
        self.sticks = (FlickStick(), FlickStick())

    def press(self, finger: int, x: float, y: float, t: float, *, two_player: bool) -> None:
        player = 1 if two_player and y < self.screen_h / 2 else 0
        self.sticks[player].press(finger, x, y, t)

    def move(self, finger: int, x: float, y: float, t: float) -> None:
        for stick in self.sticks:
            stick.move(finger, x, y, t)

    def release(self, finger: int, x: float, y: float, t: float) -> None:
        for stick in self.sticks:
            stick.release(finger, x, y, t)

    def reset(self) -> None:
        for stick in self.sticks:
            stick.reset()
