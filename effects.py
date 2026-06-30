"""ゴール演出などのビジュアルエフェクト"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import pygame

from caterpillar_art import LEAF_BODY, LEAF_EDGE
from constants import P1_NEON, P2_NEON


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
    x: float = 0.0
    y: float = 0.0
    points: int = 1


def spawn_goal_celebration(x: float, y: float, scorer: int, points: int = 1) -> GoalCelebration:
    """ゴール位置から葉っぱが舞い散る演出"""
    fx = GoalCelebration(scorer=scorer, x=x, y=y, points=points, timer=1.35, duration=1.35)
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
    for p in fx.particles:
        p.life -= dt
        p.x += p.vx * dt
        p.y += p.vy * dt
        p.vy += 95.0 * dt
        p.angle += p.spin * dt
        p.vx *= 0.985
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


def draw_goal_celebration(surf: pygame.Surface, fx: GoalCelebration, font: pygame.font.Font) -> None:
    for p in fx.particles:
        fade = max(0.0, min(1.0, p.life / p.max_life))
        if fade <= 0.02:
            continue
        body = tuple(int(c * fade) for c in LEAF_BODY)
        edge = tuple(int(c * fade) for c in LEAF_EDGE)
        poly = _leaf_polygon(p.x, p.y, p.size, p.angle)
        pygame.draw.polygon(surf, body, poly)
        pygame.draw.polygon(surf, edge, poly, 1)

    progress = 1.0 - max(0.0, fx.timer / fx.duration)
    pulse = 0.88 + 0.12 * math.sin(progress * math.pi * 4.0)
    neon = P1_NEON if fx.scorer == 0 else P2_NEON
    color = tuple(int(c * pulse) for c in neon)
    main = font.render("葉っぱゲット！", True, color)
    shadow = font.render("葉っぱゲット！", True, (0, 0, 0))
    cx, cy = int(fx.x), int(fx.y)
    rect = main.get_rect(center=(cx, cy - 28))
    surf.blit(shadow, rect.move(2, 2))
    surf.blit(main, rect)

    sub = font.render(f"+{fx.points}", True, (255, 255, 255))
    sub_rect = sub.get_rect(center=(cx, cy + 6))
    surf.blit(sub, sub_rect)
