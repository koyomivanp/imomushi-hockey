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


@dataclass
class Impact:
    """貫通の閃光ひとつ分"""

    x: float
    y: float
    angle: float
    age: float = 0.0


IMPACT_LIFE = 0.55
IMPACT_FLASH_TIME = 0.2


def _star_points(x: float, y: float, outer: float, inner: float, turn: float) -> list[tuple[int, int]]:
    pts = []
    for i in range(20):
        r = outer if i % 2 == 0 else inner
        ang = turn + i * math.tau / 20
        pts.append((int(x + math.cos(ang) * r), int(y + math.sin(ang) * r)))
    return pts


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
        self.impacts: list[Impact] = []
        self.goal_text_timer = 0.0
        self.goal_text_player = 0
        self.rng = random.Random(4242)

    def reset(self) -> None:
        self.particles.clear()
        self.impacts.clear()
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

    def burst_shards(self, x: float, y: float, heading: float, player: int, *, count: int = 12) -> None:
        """貫通 — 体節のかけらが、葉っぱの進む方へ飛び散る"""
        body, dark = palette(player)
        for i in range(count):
            spread = self.rng.uniform(-0.9, 0.9) if i % 3 else self.rng.uniform(0, math.tau)
            ang = heading + spread
            speed = self.rng.uniform(220, 620)
            self._add(Particle(
                x=x, y=y, vx=math.cos(ang) * speed, vy=math.sin(ang) * speed,
                rot=self.rng.uniform(0, math.tau), vrot=self.rng.uniform(-11, 11),
                size=self.rng.uniform(8, 17), life=self.rng.uniform(0.4, 0.75), age=0.0,
                color=self.rng.choice((body, body, dark, PB_SUN)), kind="leaf",
            ))

    def burst_breach(self, x: float, y: float, heading: float, player: int) -> None:
        """貫通の見せ場 — 星形の閃光、衝撃の輪、かけら、「バリッ！」"""
        self.impacts.append(Impact(x=x, y=y, angle=self.rng.uniform(-0.2, 0.2)))
        self.burst_shards(x, y, heading, player, count=20)

    def spark_trail(self, x: float, y: float, heading: float) -> None:
        """貫通直後の葉っぱが引く火花"""
        back = heading + math.pi
        for _ in range(2):
            ang = back + self.rng.uniform(-0.45, 0.45)
            speed = self.rng.uniform(120, 300)
            self._add(Particle(
                x=x, y=y, vx=math.cos(ang) * speed, vy=math.sin(ang) * speed,
                rot=0.0, vrot=0.0,
                size=self.rng.uniform(4, 8), life=self.rng.uniform(0.15, 0.3), age=0.0,
                color=self.rng.choice((PB_SUN, PB_WHITE, PB_PINK)), kind="spark", gravity=0.0,
            ))

    # --- 更新・描画 ---
    def update(self, dt: float) -> None:
        if self.goal_text_timer > 0.0:
            self.goal_text_timer = max(0.0, self.goal_text_timer - dt)
        if self.impacts:
            for impact in self.impacts:
                impact.age += dt
            self.impacts = [i for i in self.impacts if i.age < IMPACT_LIFE]
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

    def _draw_impact(self, surf: pygame.Surface, impact: Impact) -> None:
        k = impact.age / IMPACT_LIFE
        x, y = impact.x, impact.y
        ease = 1.0 - (1.0 - k) ** 3
        ring_r = int(30 + 110 * ease)
        ring_w = max(2, int(8 * (1.0 - k)))
        pygame.draw.circle(surf, PB_INK, (int(x), int(y)), ring_r + 3, ring_w + 5)
        pygame.draw.circle(surf, PB_WHITE, (int(x), int(y)), ring_r, ring_w)
        if impact.age < IMPACT_FLASH_TIME:
            f = impact.age / IMPACT_FLASH_TIME
            size = (34 + 44 * min(1.0, f * 3.0)) * (1.0 - f * f)
            turn = impact.angle + f * 0.5
            pygame.draw.polygon(surf, PB_INK, _star_points(x, y, size + 9, size * 0.52 + 7, turn))
            pygame.draw.polygon(surf, PB_SUN, _star_points(x, y, size, size * 0.52, turn))
            pygame.draw.polygon(surf, PB_WHITE, _star_points(x, y, size * 0.56, size * 0.3, turn))
        pop = min(1.0, impact.age / 0.09)
        out = max(0.0, (k - 0.72) / 0.28)
        scale = (0.5 + 0.7 * pop) * (1.0 - out * 0.6) * (1.0 + (1.0 - pop) * 0.5)
        glyph = text_fit("バリッ！", 40, PB_SUN, max_width=MOBILE_W - 120, outline=PB_INK, outline_px=5)
        zoomed = pygame.transform.rotozoom(glyph, math.degrees(impact.angle), scale)
        # 画面の外へはみ出さない位置に出す
        rect = zoomed.get_rect(center=(int(x), int(y) - 62))
        surf.blit(zoomed, rect.clamp(surf.get_rect()))

    def draw(self, surf: pygame.Surface) -> None:
        for impact in self.impacts:
            self._draw_impact(surf, impact)
        for p in self.particles:
            fade = 1.0 - p.age / p.life
            scale = min(1.0, fade * 2.2)
            if scale <= 0.08:
                continue
            if p.kind == "spark":
                tail = (int(p.x - p.vx * 0.05), int(p.y - p.vy * 0.05))
                pygame.draw.line(surf, PB_INK, (int(p.x), int(p.y)), tail, max(3, int(p.size * scale) + 3))
                pygame.draw.line(surf, p.color, (int(p.x), int(p.y)), tail, max(2, int(p.size * scale)))
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
