"""スマホ操作 — スライドパッドで這い、ダッシュボタンで一気に進む（座標は縦画面の論理px）"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from constants import (
    MOBILE_H,
    MOBILE_W,
    STICK_DEADZONE,
    STICK_RADIUS,
    TOUCH_CONTROL_Y,
    TOUCH_DASH_MARGIN,
    TOUCH_DASH_RADIUS,
    TOUCH_DASH_TAP_TIME,
    TOUCH_DASH_X,
    TOUCH_PAD_RADIUS,
    TOUCH_PAD_X,
)


def _unit(dx: float, dy: float) -> tuple[float, float]:
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return 0.0, 0.0
    return dx / d, dy / d


# キーボード（PC ブラウザ用）。向きは画面の上下左右
_WASD = {pygame.K_a: (-1, 0), pygame.K_d: (1, 0), pygame.K_w: (0, -1), pygame.K_s: (0, 1)}
_ARROWS = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}


def keyboard_output(keys, player: int, *, two_player: bool) -> tuple[float, float, bool]:
    """画面座標の向きとダッシュ。CPU 戦はどちらのキーでも自分を動かす"""
    if two_player:
        layouts = [_WASD] if player == 0 else [_ARROWS]
        dash = keys[pygame.K_LSHIFT] if player == 0 else keys[pygame.K_RSHIFT]
    else:
        if player != 0:
            return 0.0, 0.0, False
        layouts = [_WASD, _ARROWS]
        dash = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
    dx = dy = 0.0
    for layout in layouts:
        for key, (kx, ky) in layout.items():
            if keys[key]:
                dx += kx
                dy += ky
    ux, uy = _unit(dx, dy)
    return ux, uy, bool(dash) and bool(ux or uy)


def pad_home(player: int) -> tuple[int, int]:
    """下の人は右下、向かい合う上の人は左上"""
    if player == 0:
        return MOBILE_W - TOUCH_PAD_X, MOBILE_H - TOUCH_CONTROL_Y
    return TOUCH_PAD_X, TOUCH_CONTROL_Y


def dash_button_center(player: int) -> tuple[int, int]:
    """下の人は左下、向かい合う上の人は右上"""
    if player == 0:
        return TOUCH_DASH_X, MOBILE_H - TOUCH_CONTROL_Y
    return MOBILE_W - TOUCH_DASH_X, TOUCH_CONTROL_Y


@dataclass
class PlayerTouch:
    """1人分のパッドとダッシュボタン"""

    player: int = 0
    finger: int | None = None
    anchor_x: float = 0.0
    anchor_y: float = 0.0
    x: float = 0.0
    y: float = 0.0
    dash_finger: int | None = None
    dash_until: float = 0.0
    last_dir: tuple[float, float] = (0.0, 0.0)

    def __post_init__(self) -> None:
        self.last_dir = (0.0, -1.0) if self.player == 0 else (0.0, 1.0)

    def press_pad(self, finger: int, x: float, y: float) -> None:
        if self.finger is not None:
            return
        self.finger = finger
        hx, hy = pad_home(self.player)
        # パッドの上ならそこを中心に。外れていたら触った場所を中心にする
        if math.hypot(x - hx, y - hy) <= TOUCH_PAD_RADIUS:
            self.anchor_x, self.anchor_y = hx, hy
        else:
            self.anchor_x, self.anchor_y = x, y
        self.x, self.y = x, y

    def press_dash(self, finger: int, t: float) -> None:
        if self.dash_finger is None:
            self.dash_finger = finger
            self.dash_until = t + TOUCH_DASH_TAP_TIME

    def move(self, finger: int, x: float, y: float) -> None:
        if finger != self.finger:
            return
        self.x, self.y = x, y
        # 中心を指に追従させ、切り返しをすぐ効かせる
        ax, ay = x - self.anchor_x, y - self.anchor_y
        dist = math.hypot(ax, ay)
        if dist > STICK_RADIUS:
            self.anchor_x = x - ax / dist * STICK_RADIUS
            self.anchor_y = y - ay / dist * STICK_RADIUS

    def release(self, finger: int) -> None:
        if finger == self.finger:
            self.finger = None
        if finger == self.dash_finger:
            self.dash_finger = None

    def reset(self) -> None:
        self.finger = None
        self.dash_finger = None
        self.dash_until = 0.0

    def is_dash_active(self, t: float) -> bool:
        return self.dash_finger is not None or t < self.dash_until

    def knob_offset(self) -> tuple[float, float]:
        if self.finger is None:
            return 0.0, 0.0
        return self.x - self.anchor_x, self.y - self.anchor_y

    def output(self, t: float) -> tuple[float, float, bool]:
        """画面座標の向き (dx, dy) とダッシュ中か"""
        dash = self.is_dash_active(t)
        dx, dy = self.knob_offset()
        if math.hypot(dx, dy) >= STICK_DEADZONE:
            self.last_dir = _unit(dx, dy)
            return self.last_dir[0], self.last_dir[1], dash
        if dash:  # パッドに触れていなければ、最後に向いていた方へ
            return self.last_dir[0], self.last_dir[1], True
        return 0.0, 0.0, False


class TouchControls:
    """指を担当プレイヤーへ振り分ける。下半分=P1、上半分=P2（CPU戦は全面 P1）"""

    def __init__(self, screen_h: int) -> None:
        self.screen_h = screen_h
        self.sticks = (PlayerTouch(0), PlayerTouch(1))
        self.visible = True  # キーボードで遊んでいる間は隠す

    def press(self, finger: int, x: float, y: float, t: float, *, two_player: bool) -> None:
        player = 1 if two_player and y < self.screen_h / 2 else 0
        stick = self.sticks[player]
        bx, by = dash_button_center(player)
        if math.hypot(x - bx, y - by) <= TOUCH_DASH_RADIUS + TOUCH_DASH_MARGIN:
            stick.press_dash(finger, t)
        else:
            stick.press_pad(finger, x, y)

    def move(self, finger: int, x: float, y: float, t: float) -> None:
        for stick in self.sticks:
            stick.move(finger, x, y)

    def release(self, finger: int, x: float, y: float, t: float) -> None:
        for stick in self.sticks:
            stick.release(finger)

    def reset(self) -> None:
        for stick in self.sticks:
            stick.reset()
