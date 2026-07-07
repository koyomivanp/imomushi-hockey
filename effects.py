"""ゴール演出などのビジュアルエフェクト"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import pygame

from caterpillar_art import LEAF_BODY, LEAF_EDGE, draw_leaf_puck
from constants import (
    GOAL_SCORE_DEPTH,
    PUCK_NEON_HEAT,
    PUCK_RADIUS,
    PUCK_RESET_ANIM_DURATION,
)
from entities import arena_frame_rect, goal_bounds, playable_rect
from visuals import draw_neon_line


@dataclass
class LeafParticle:
    x: float
    y: float
    vx: float
    vy: float
    angle: float
    spin: float
    size: float
    life: float
    max_life: float


@dataclass
class GoalCelebration:
    particles: list[LeafParticle] = field(default_factory=list)
    timer: float = 0.0
    duration: float = 1.35
    scorer: int = 0
    conceded_side: int = 0
    x: float = 0.0
    y: float = 0.0
    points: int = 1


def goal_mouth_anchor(conceded_side: int) -> tuple[float, float]:
    """ゴール口の固定アンカー（左/右 frame 外縁 × ゴール中央 Y）"""
    frame = arena_frame_rect()
    goal_top, goal_bottom = goal_bounds()
    cy = (goal_top + goal_bottom) * 0.5
    if conceded_side == 0:
        x = frame.left - GOAL_SCORE_DEPTH * 0.35
    else:
        x = frame.right + GOAL_SCORE_DEPTH * 0.35
    return x, cy


def spawn_goal_celebration(conceded_side: int, scorer: int, points: int = 1) -> GoalCelebration:
    """ゴール口から葉っぱが舞い散る演出"""
    x, y = goal_mouth_anchor(conceded_side)
    fx = GoalCelebration(
        scorer=scorer,
        conceded_side=conceded_side,
        x=x,
        y=y,
        points=points,
        timer=1.35,
        duration=1.35,
    )
    burst_dir = 1.0 if scorer == 0 else -1.0
    for _ in range(20):
        spread = random.uniform(-0.9, 0.9)
        speed = random.uniform(55, 165)
        fx.particles.append(LeafParticle(
            x=x + random.uniform(-6, 6),
            y=y + random.uniform(-24, 24),
            vx=burst_dir * speed * math.cos(spread) + random.uniform(-25, 25),
            vy=math.sin(spread) * speed * 0.85,
            angle=random.uniform(0.0, math.tau),
            spin=random.uniform(-10.0, 10.0),
            size=random.uniform(4.0, 10.0),
            life=random.uniform(0.7, 1.25),
            max_life=1.25,
        ))
    return fx


def update_goal_celebration(fx: GoalCelebration | None, dt: float) -> GoalCelebration | None:
    if fx is None or fx.timer <= 0.0:
        return None
    fx.timer -= dt
    play = playable_rect()
    cx, cy = play.centerx, play.centery
    converge = max(0.0, 1.0 - fx.timer / fx.duration)
    for p in fx.particles:
        p.life -= dt
        p.x += p.vx * dt
        p.y += p.vy * dt
        p.vy += 95.0 * dt
        p.angle += p.spin * dt
        p.vx *= 0.985
        if converge > 0.55:
            pull = (converge - 0.55) * 2.2
            p.vx += (cx - p.x) * pull * dt * 3.5
            p.vy += (cy - p.y) * pull * dt * 3.5
    fx.particles = [p for p in fx.particles if p.life > 0.0]
    if fx.timer > 0.0 or fx.particles:
        return fx
    return None


def _leaf_polygon(cx: float, cy: float, size: float, angle: float) -> list[tuple[int, int]]:
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    def rot(px: float, py: float) -> tuple[int, int]:
        return (
            int(cx + px * cos_a - py * sin_a),
            int(cy + px * sin_a + py * cos_a),
        )

    return [rot(size * 1.1, 0), rot(-size * 0.5, -size * 0.7), rot(-size * 0.85, 0), rot(-size * 0.5, size * 0.7)]


def draw_goal_celebration(surf: pygame.Surface, fx: GoalCelebration) -> None:
    for p in fx.particles:
        fade = max(0.0, min(1.0, p.life / p.max_life))
        if fade <= 0.02:
            continue
        body = tuple(int(c * fade) for c in LEAF_BODY)
        edge = tuple(int(c * fade) for c in LEAF_EDGE)
        poly = _leaf_polygon(p.x, p.y, p.size, p.angle)
        pygame.draw.polygon(surf, body, poly)
        pygame.draw.polygon(surf, edge, poly, 1)


def _ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _ease_out_back(t: float) -> float:
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


@dataclass
class PuckResetAnim:
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    timer: float = 0.0
    duration: float = PUCK_RESET_ANIM_DURATION
    rotation: float = 0.0

    @property
    def active(self) -> bool:
        return self.timer < self.duration

    def update(self, dt: float) -> bool:
        self.timer = min(self.duration, self.timer + dt)
        return self.timer >= self.duration

    @property
    def progress(self) -> float:
        if self.duration <= 0.0:
            return 1.0
        return max(0.0, min(1.0, self.timer / self.duration))

    @property
    def x(self) -> float:
        t = _ease_out_cubic(self.progress)
        return self.start_x + (self.end_x - self.start_x) * t

    @property
    def y(self) -> float:
        t = _ease_out_cubic(self.progress)
        return self.start_y + (self.end_y - self.start_y) * t

    @property
    def scale(self) -> float:
        t = _ease_out_back(self.progress)
        return 0.6 + 0.4 * t

    def draw(self, surf: pygame.Surface, now: float) -> None:
        fade_in = min(1.0, self.progress * 2.5)
        radius = PUCK_RADIUS * self.scale
        self.rotation += 0.08
        if fade_in < 0.98:
            glow_r = int(radius * 1.5)
            glow_a = int(80 * fade_in * (1.0 - self.progress * 0.5))
            if glow_a > 4:
                glow_surf = pygame.Surface((glow_r * 2 + 4, glow_r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(
                    glow_surf,
                    (*PUCK_NEON_HEAT, glow_a),
                    (glow_r + 2, glow_r + 2),
                    glow_r,
                )
                surf.blit(glow_surf, (int(self.x) - glow_r - 2, int(self.y) - glow_r - 2))
        draw_leaf_puck(surf, self.x, self.y, radius, now * 2.4 + self.rotation)


def score_pop_scale(timer: float, duration: float) -> float:
    if timer <= 0.0 or duration <= 0.0:
        return 1.0
    t = 1.0 - timer / duration
    return 1.0 + 0.4 * _ease_out_back(t) * max(0.0, 1.0 - t * 1.2)


def score_segment_light_progress(timer: float, duration: float) -> float:
    """得点セグメントの点灯進行（0=消灯, 1=点灯完了）"""
    if timer <= 0.0 or duration <= 0.0:
        return 1.0
    t = max(0.0, min(1.0, 1.0 - timer / duration))
    return _ease_out_cubic(t)


def score_segment_glow_strength(timer: float, duration: float) -> float:
    """点灯直後のにじむグロー（0〜1、中盤でピーク）"""
    if timer <= 0.0 or duration <= 0.0:
        return 0.0
    t = max(0.0, min(1.0, 1.0 - timer / duration))
    if t < 0.35:
        return t / 0.35
    return max(0.0, 1.0 - (t - 0.35) / 0.65)


@dataclass
class BreachSpark:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float


def spawn_breach_sparks(x: float, y: float, vx: float, vy: float) -> list[BreachSpark]:
    """体節貫通時の火花"""
    speed = math.hypot(vx, vy)
    if speed > 1e-6:
        ux, uy = vx / speed, vy / speed
    else:
        ux, uy = 1.0, 0.0
    px, py = -uy, ux
    sparks: list[BreachSpark] = []
    for _ in range(7):
        spread = random.uniform(-0.55, 0.55)
        spd = random.uniform(120.0, 280.0)
        sparks.append(BreachSpark(
            x=x + random.uniform(-4.0, 4.0),
            y=y + random.uniform(-4.0, 4.0),
            vx=ux * spd + px * spd * spread,
            vy=uy * spd + py * spd * spread,
            life=random.uniform(0.12, 0.22),
            max_life=0.22,
        ))
    return sparks


def update_breach_sparks(sparks: list[BreachSpark], dt: float) -> list[BreachSpark]:
    alive: list[BreachSpark] = []
    for s in sparks:
        s.life -= dt
        if s.life <= 0.0:
            continue
        s.x += s.vx * dt
        s.y += s.vy * dt
        s.vx *= 0.92
        s.vy *= 0.92
        alive.append(s)
    return alive


def draw_breach_sparks(surf: pygame.Surface, sparks: list[BreachSpark]) -> None:
    for s in sparks:
        fade = max(0.0, min(1.0, s.life / s.max_life))
        if fade <= 0.02:
            continue
        ex = int(s.x - s.vx * 0.04)
        ey = int(s.y - s.vy * 0.04)
        color = tuple(int(c * fade) for c in PUCK_NEON_HEAT)
        draw_neon_line(surf, (int(s.x), int(s.y)), (ex, ey), color, fade=fade)
