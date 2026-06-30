"""ゲームエンティティ"""

import math
import random
from dataclasses import dataclass, field

import pygame

from constants import (
    CATERPILLAR_BODY_RADIUS,
    GOAL_WIDTH_RATIO,
    P1_NEON,
    P2_NEON,
    PADDLE_DASH_SPEED,
    PADDLE_SPEED,
    PADDLE_WIDTH_RATIO,
    PADDLE_SIZE_AXIS,
    PUCK_COLOR,
    PUCK_MAX_SPEED,
    PUCK_MIN_SPEED,
    PUCK_RADIUS,
    TABLE_MARGIN_X,
    TABLE_W,
    TABLE_Y,
    TABLE_H,
    TRAIL_FADE_START_RATIO,
    TRAIL_WALL_MIN_BRIGHTNESS,
)
from caterpillar_art import (
    FACE_TURN_SPEED,
    draw_head_circle,
    draw_leaf_puck,
    draw_sketch_face,
    draw_smooth_tube,
    lerp_angle,
)
from sprites import draw_leaf_sprite


def clamp_speed(vx: float, vy: float) -> tuple[float, float]:
    speed = math.hypot(vx, vy)
    if speed < 1e-6:
        return 0.0, 0.0
    if speed > PUCK_MAX_SPEED:
        scale = PUCK_MAX_SPEED / speed
        return vx * scale, vy * scale
    if speed < PUCK_MIN_SPEED:
        scale = PUCK_MIN_SPEED / speed
        return vx * scale, vy * scale
    return vx, vy


def table_rect() -> pygame.Rect:
    return pygame.Rect(TABLE_MARGIN_X, TABLE_Y, TABLE_W, TABLE_H)


def goal_bounds() -> tuple[float, float]:
    """ゴール開口（左右壁の中央）。返値は top, bottom"""
    rect = table_rect()
    half = GOAL_WIDTH_RATIO / 2
    top = rect.top + rect.height * (0.5 - half)
    bottom = rect.top + rect.height * (0.5 + half)
    return top, bottom


def _heading_from_paddle(paddle: "Paddle") -> float:
    dx, dy = paddle.last_dir
    if math.hypot(dx, dy) > 0.01:
        return math.atan2(dy, dx)
    if math.hypot(paddle.vx, paddle.vy) > 8.0:
        return math.atan2(paddle.vy, paddle.vx)
    return 0.0 if paddle.player == 0 else math.pi


@dataclass
class Puck:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    paddle_ignore_players: set[int] = field(default_factory=set)
    paddle_ignore_until: dict[int, float] = field(default_factory=dict)
    fence_ignore_until: float = 0.0
    wall_bounces: int = 0
    scored: bool = False
    carried_by: int = -1
    grind_started_at: float = -1.0
    grind_paddle: int = -1
    grind_escape_x: float = 0.0
    dash_breach_until: float = 0.0
    fence_chain_owner: int = -1
    fence_chain_count: int = 0
    fence_chain_until: float = 0.0
    prev_x: float = 0.0
    prev_y: float = 0.0

    @property
    def radius(self) -> float:
        return PUCK_RADIUS

    @property
    def color(self) -> tuple:
        return PUCK_COLOR

    def draw(self, surf: pygame.Surface, now: float = 0.0) -> None:
        if not draw_leaf_sprite(surf, self.x, self.y, self.radius, now * 2.4):
            draw_leaf_puck(surf, self.x, self.y, self.radius, now)


@dataclass
class Paddle:
    player: int
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    last_dir: tuple[float, float] = (1.0, 0.0)
    trail_x: float = 0.0
    trail_y: float = 0.0
    trail_spawn_until: float = 0.0
    is_dashing: bool = False
    face_heading: float = 0.0
    face_heading_ready: bool = False
    prev_x: float = 0.0
    prev_y: float = 0.0

    def base_radius(self) -> float:
        axis = TABLE_H if PADDLE_SIZE_AXIS == "height" else TABLE_W
        return axis * PADDLE_WIDTH_RATIO / 2

    def radius(self, now: float) -> float:
        return self.base_radius()

    def speed(self, now: float, dashing: bool = False) -> float:
        if dashing:
            return PADDLE_DASH_SPEED
        return PADDLE_SPEED

    def update_face_heading(self, dt: float) -> None:
        target = _heading_from_paddle(self)
        if not self.face_heading_ready:
            self.face_heading = target
            self.face_heading_ready = True
            return
        t = min(1.0, dt * FACE_TURN_SPEED)
        self.face_heading = lerp_angle(self.face_heading, target, t)

    def draw(self, surf: pygame.Surface, now: float) -> None:
        r = int(self.radius(now))
        neon = P1_NEON if self.player == 0 else P2_NEON
        heading = self.face_heading

        draw_head_circle(surf, self.x, self.y, float(r), self.player)
        draw_sketch_face(surf, self.x, self.y, float(r), heading, self.player)

        if self.is_dashing:
            pulse = 0.5 + 0.5 * math.sin(now * 13)
            dash_r = int(r + 8 + pulse * 5)
            pygame.draw.circle(surf, (255, 210, 100), (int(self.x), int(self.y)), dash_r, 2)
        speed = math.hypot(self.vx, self.vy)
        if not self.is_dashing and speed >= 100:
            pulse = 0.5 + 0.5 * math.sin(now * 14)
            ring_r = int(r + 3 + pulse * 2)
            pygame.draw.circle(surf, neon, (int(self.x), int(self.y)), ring_r, 1)


@dataclass
class Fence:
    """体節壁（這った軌跡）"""
    owner: int
    x1: float
    y1: float
    x2: float
    y2: float
    until: float
    created_at: float = 0.0
    half_width: float = 5.0

    def draw(self, surf: pygame.Surface, now: float, age_rank: float = 1.0) -> None:
        """age_rank: 0=いちばん古い壁, 1=いちばん新しい壁"""
        remaining = max(0.0, self.until - now)
        total = max(0.001, self.until - self.created_at)
        life_ratio = remaining / total
        if life_ratio <= TRAIL_FADE_START_RATIO:
            expire_fade = life_ratio / TRAIL_FADE_START_RATIO
        else:
            expire_fade = 1.0
        age_rank = max(0.0, min(1.0, age_rank))
        age_brightness = TRAIL_WALL_MIN_BRIGHTNESS + (1.0 - TRAIL_WALL_MIN_BRIGHTNESS) * age_rank
        fade = expire_fade * age_brightness
        if fade <= 0.04:
            return

        body_r = self.half_width if self.half_width > 0 else CATERPILLAR_BODY_RADIUS
        draw_smooth_tube(
            surf, self.x1, self.y1, self.x2, self.y2,
            body_r, self.owner, fade=fade,
        )


def spawn_center_puck() -> Puck:
    rect = table_rect()
    x = rect.centerx
    y = rect.centery
    return Puck(
        x=x,
        y=y,
        prev_x=x,
        prev_y=y,
        vx=random.uniform(-80, 80),
        vy=random.uniform(-80, 80),
    )
