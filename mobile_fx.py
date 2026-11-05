"""スマホ版の演出 — 花びら・葉っぱ・土ぼこり・サナギと蝶

塗りつぶし図形だけで描き、毎フレームの全画面合成や文字描画を増やさない。
粒は消えるときに縮める（半透明サーフェスを作らないため）。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from constants import (
    MOBILE_GOAL_TEXT_DURATION,
    MOBILE_H,
    MOBILE_W,
    PB_CREAM,
    PB_HILL_HI,
    PB_HILL_LO,
    PB_INK,
    PB_PINK,
    PB_SUN,
    PB_WHITE,
)
from mobile_art import palette, text_fit

GRAVITY = 420.0
MAX_PARTICLES = 150


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    rot: float
    vrot: float
    size: float
    life: float
    age: float
    color: tuple[int, int, int]
    kind: str
    gravity: float = GRAVITY


def _petal_points(p: Particle, scale: float) -> list[tuple[int, int]]:
    r = p.size * scale
    pts = []
    for ax, ay in ((1.0, 0.0), (0.1, 0.62), (-0.95, 0.0), (0.1, -0.62)):
        c, s = math.cos(p.rot), math.sin(p.rot)
        pts.append((int(p.x + (ax * c - ay * s) * r), int(p.y + (ax * s + ay * c) * r)))
    return pts


class MobileFX:
    """試合中の粒。update は dt、draw は画面サーフェスへ直接"""

    def __init__(self) -> None:
        self.particles: list[Particle] = []
        self.goal_text_timer = 0.0
        self.goal_text_player = 0
        self.rng = random.Random(4242)

    def reset(self) -> None:
        self.particles.clear()
        self.goal_text_timer = 0.0

    # --- 発生 ---
    def _add(self, p: Particle) -> None:
        if len(self.particles) < MAX_PARTICLES:
            self.particles.append(p)

    def burst_goal(self, x: float, y: float, player: int) -> None:
        """花びらと葉っぱが舞う"""
        body, _dark = palette(player)
        for i in range(34):
            ang = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(160, 460)
            kind = "petal" if i % 3 else "leaf"
            color = self.rng.choice((PB_PINK, PB_SUN, PB_WHITE)) if kind == "petal" else \
                self.rng.choice((PB_HILL_HI, PB_HILL_LO, body))
            self._add(Particle(
                x=x, y=y,
                vx=math.cos(ang) * speed, vy=math.sin(ang) * speed - 170,
                rot=self.rng.uniform(0, math.tau), vrot=self.rng.uniform(-6, 6),
                size=self.rng.uniform(10, 19), life=self.rng.uniform(0.9, 1.7), age=0.0,
                color=color, kind=kind, gravity=GRAVITY * 0.55,
            ))
        self.goal_text_timer = MOBILE_GOAL_TEXT_DURATION
        self.goal_text_player = player

    def puff_dash(self, x: float, y: float, heading: float, player: int) -> None:
        """ダッシュの土ぼこりと葉の残像"""
        back = heading + math.pi
        for _ in range(2):
            ang = back + self.rng.uniform(-0.5, 0.5)
            speed = self.rng.uniform(40, 130)
            self._add(Particle(
                x=x + math.cos(back) * 24, y=y + math.sin(back) * 24,
                vx=math.cos(ang) * speed, vy=math.sin(ang) * speed,
                rot=0.0, vrot=0.0,
                size=self.rng.uniform(8, 15), life=self.rng.uniform(0.22, 0.4), age=0.0,
                color=PB_CREAM, kind="dust", gravity=0.0,
            ))

    def burst_shards(self, x: float, y: float, player: int) -> None:
        """貫通 — 葉のかけらが飛び散る"""
        body, dark = palette(player)
        for _ in range(12):
            ang = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(170, 380)
            self._add(Particle(
                x=x, y=y, vx=math.cos(ang) * speed, vy=math.sin(ang) * speed,
                rot=self.rng.uniform(0, math.tau), vrot=self.rng.uniform(-9, 9),
                size=self.rng.uniform(7, 13), life=self.rng.uniform(0.35, 0.6), age=0.0,
                color=self.rng.choice((body, dark, PB_HILL_HI)), kind="leaf",
            ))

    # --- 更新・描画 ---
    def update(self, dt: float) -> None:
        if self.goal_text_timer > 0.0:
            self.goal_text_timer = max(0.0, self.goal_text_timer - dt)
        if not self.particles:
            return
        alive: list[Particle] = []
        for p in self.particles:
            p.age += dt
            if p.age >= p.life:
                continue
            p.vy += p.gravity * dt
            if p.kind == "petal":
                p.vx += math.sin(p.age * 7.0 + p.rot) * 60.0 * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.rot += p.vrot * dt
            if -60 < p.x < MOBILE_W + 60 and p.y < MOBILE_H + 60:
                alive.append(p)
        self.particles = alive

    def draw(self, surf: pygame.Surface) -> None:
        for p in self.particles:
            fade = 1.0 - p.age / p.life
            scale = min(1.0, fade * 2.2)
            if scale <= 0.08:
                continue
            if p.kind == "dust":
                pygame.draw.circle(surf, p.color, (int(p.x), int(p.y)), max(2, int(p.size * scale)))
                continue
            pts = _petal_points(p, scale)
            pygame.draw.polygon(surf, PB_INK, pts)
            inner = [(int(p.x + (px - p.x) * 0.72), int(p.y + (py - p.y) * 0.72)) for px, py in pts]
            pygame.draw.polygon(surf, p.color, inner)

    def draw_goal_text(self, surf: pygame.Surface) -> None:
        if self.goal_text_timer <= 0.0:
            return
        t = 1.0 - self.goal_text_timer / MOBILE_GOAL_TEXT_DURATION
        pop = min(1.0, t * 5.0)
        scale = 0.6 + 0.4 * (1.0 - (1.0 - pop) ** 3) + math.sin(t * 9.0) * 0.03
        body, _dark = palette(self.goal_text_player)
        glyph = text_fit("ゴール！", 92, body, max_width=MOBILE_W - 90, outline=PB_INK, outline_px=8)
        scaled = pygame.transform.rotozoom(glyph, math.sin(t * 5.0) * 3.0, scale)
        surf.blit(scaled, scaled.get_rect(center=(MOBILE_W // 2, MOBILE_H // 2)))


class VictoryButterfly:
    """勝った芋虫がサナギになり、蝶になって飛び立つ"""

    PUPA = 1.1
    CRACK = 1.5
    FLY = 3.4

    def __init__(self) -> None:
        self.t = 0.0
        self.player = 0
        self.active = False
        self.x = MOBILE_W / 2
        self.y = MOBILE_H / 2

    def start(self, player: int, x: float, y: float) -> None:
        self.t = 0.0
        self.player = player
        self.x, self.y = x, y
        self.active = True

    def update(self, dt: float) -> None:
        if self.active:
            self.t += dt

    def draw(self, surf: pygame.Surface) -> None:
        if not self.active:
            return
        body, dark = palette(self.player)
        t = self.t
        if t < self.PUPA:
            k = min(1.0, t / self.PUPA)
            w = 44 - 10 * k
            h = 56 + 22 * k
            rect = pygame.Rect(0, 0, int(w * 2), int(h * 2))
            rect.center = (int(self.x), int(self.y))
            pygame.draw.ellipse(surf, PB_INK, rect.inflate(10, 10))
            pygame.draw.ellipse(surf, body if k < 0.5 else PB_SUN, rect)
            for i in range(3):
                y = rect.top + rect.height * (0.3 + i * 0.2)
                pygame.draw.line(surf, dark, (rect.left + 8, y), (rect.right - 8, y), 4)
            return
        if t < self.CRACK:
            k = (t - self.PUPA) / (self.CRACK - self.PUPA)
            rect = pygame.Rect(0, 0, 68, 156)
            rect.center = (int(self.x), int(self.y))
            pygame.draw.ellipse(surf, PB_INK, rect.inflate(10, 10))
            pygame.draw.ellipse(surf, PB_SUN, rect)
            shake = math.sin(k * 40.0) * 7
            pygame.draw.line(surf, PB_INK, (rect.centerx + shake, rect.top + 14),
                             (rect.centerx - shake, rect.bottom - 14), 7)
            return
        k = min(1.0, (t - self.CRACK) / (self.FLY - self.CRACK))
        bx = self.x + math.sin(k * 7.0) * 70
        by = self.y - k * 320
        flap = abs(math.sin(t * 11.0))
        self._butterfly(surf, bx, by, body, dark, flap, 1.0)

    def _butterfly(self, surf, x, y, body, dark, flap, scale) -> None:
        wing_w = (22 + 34 * flap) * scale
        wing_h = 46 * scale
        for side in (-1, 1):
            for dy, h in ((-20 * scale, wing_h), (22 * scale, wing_h * 0.7)):
                rect = pygame.Rect(0, 0, int(wing_w * 2), int(h * 2))
                rect.center = (int(x + side * wing_w), int(y + dy))
                pygame.draw.ellipse(surf, PB_INK, rect.inflate(8, 8))
                pygame.draw.ellipse(surf, body if dy < 0 else PB_SUN, rect)
                pygame.draw.ellipse(surf, dark, rect, 3)
        bodyrect = pygame.Rect(0, 0, int(14 * scale), int(74 * scale))
        bodyrect.center = (int(x), int(y))
        pygame.draw.ellipse(surf, PB_INK, bodyrect.inflate(6, 6))
        pygame.draw.ellipse(surf, dark, bodyrect)
        for side in (-1, 1):
            tip = (x + side * 16 * scale, y - 46 * scale)
            pygame.draw.line(surf, PB_INK, (x, y - 30 * scale), tip, 4)
            pygame.draw.circle(surf, PB_INK, (int(tip[0]), int(tip[1])), 5)
