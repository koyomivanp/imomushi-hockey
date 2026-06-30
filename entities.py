"""ゲームエンティティ"""

import math
import random
from dataclasses import dataclass, field

import pygame

from constants import (
    ASSIST_COLOR,
    BAR_CENTER_X_RATIO,
    BAR_COLOR,
    BAR_GROW_TIME,
    BAR_HALF_WIDTH,
    BAR_LEVEL_HEIGHT,
    BAR_RAY_HITS_TO_BREAK,
    CATERPILLAR_BODY_RADIUS,
    BIG_PADDLE_MULT,
    GOAL_WIDTH_RATIO,
    GUARD_COLOR,
    GUARD_HAT_COLOR,
    GUARD_RADIUS,
    ITEM_COLORS,
    ITEM_FALL_SPEED,
    ITEM_RADIUS,
    ITEM_STACK_MAX,
    P1_COLOR,
    P1_NEON,
    P2_COLOR,
    P2_NEON,
    PADDLE_DASH_SPEED,
    PADDLE_KB_DRAG,
    PADDLE_KB_TRAIL_TIME,
    PADDLE_SPEED,
    PADDLE_WIDTH_RATIO,
    PADDLE_SIZE_AXIS,
    PUCK_COLOR,
    PUCK_MAX_SPEED,
    PUCK_MIN_SPEED,
    PUCK_RADIUS,
    RAY_COLOR,
    TABLE_MARGIN_X,
    TABLE_W,
    TABLE_Y,
    TABLE_H,
    TRAIL_FADE_START_RATIO,
    TRAIL_WALL_MIN_BRIGHTNESS,
    WIND_COLOR,
    WIND_DURATION,
)
from caterpillar_art import (
    FACE_TURN_SPEED,
    draw_body_stamp,
    draw_head_circle,
    draw_leaf_puck,
    draw_segment_chain,
    draw_sketch_face,
    draw_smooth_tube,
    lerp_angle,
)
from sprites import (
    draw_leaf_sprite,
    init_sprites,
)


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


ITEM_TYPES = ("fence",)
ITEM_LABELS = {
    "fence": "FENCE!",
}
ITEM_SHORT = {
    "fence": "F",
}
_ITEM_FONT: pygame.font.Font | None = None


def _item_font() -> pygame.font.Font:
    global _ITEM_FONT
    if _ITEM_FONT is None:
        _ITEM_FONT = pygame.font.SysFont("arial", 13, bold=True)
    return _ITEM_FONT


def _heading_from_paddle(paddle: Paddle) -> float:
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
    big_until: float = 0.0
    ray_until: float = 0.0
    ray_next_fire: float = 0.0
    hit_cooldown_until: float = 0.0
    kb_vx: float = 0.0
    kb_vy: float = 0.0
    knockback_trail: list[tuple[float, float, float]] = field(default_factory=list)
    item_stacks: dict[str, int] = field(default_factory=dict)
    trail_x: float = 0.0
    trail_y: float = 0.0
    trail_spawn_until: float = 0.0
    is_dashing: bool = False
    face_heading: float = 0.0
    face_heading_ready: bool = False

    def stack_level(self, kind: str) -> int:
        return self.item_stacks.get(kind, 0)

    def add_stack(self, kind: str) -> int:
        lv = min(ITEM_STACK_MAX, self.item_stacks.get(kind, 0) + 1)
        self.item_stacks[kind] = lv
        return lv

    def big_mult(self, now: float) -> float:
        if now >= self.big_until:
            return 1.0
        lv = max(1, self.stack_level("big_paddle"))
        return BIG_PADDLE_MULT + (lv - 1) * 0.35

    def base_radius(self) -> float:
        axis = TABLE_H if PADDLE_SIZE_AXIS == "height" else TABLE_W
        return axis * PADDLE_WIDTH_RATIO / 2

    def radius(self, now: float) -> float:
        r = self.base_radius()
        if now < self.big_until:
            r *= self.big_mult(now)
        return r

    def speed(self, now: float, dashing: bool = False) -> float:
        if dashing:
            return PADDLE_DASH_SPEED
        return PADDLE_SPEED

    def can_be_hit(self, now: float) -> bool:
        return now >= self.hit_cooldown_until

    def is_knocked_back(self) -> bool:
        return math.hypot(self.kb_vx, self.kb_vy) > 18.0

    def update_knockback(self, dt: float, now: float) -> None:
        speed = math.hypot(self.kb_vx, self.kb_vy)
        if speed > 24.0:
            self.knockback_trail.append((self.x, self.y, now))

        decay = math.exp(-PADDLE_KB_DRAG * dt)
        self.kb_vx *= decay
        self.kb_vy *= decay
        if math.hypot(self.kb_vx, self.kb_vy) < 12.0:
            self.kb_vx = 0.0
            self.kb_vy = 0.0

        cutoff = now - PADDLE_KB_TRAIL_TIME
        self.knockback_trail = [(x, y, t) for x, y, t in self.knockback_trail if t >= cutoff]
        if len(self.knockback_trail) > 12:
            self.knockback_trail = self.knockback_trail[-12:]

    def has_ray(self, now: float) -> bool:
        return now < self.ray_until

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

        trail_count = len(self.knockback_trail)
        for i, (tx, ty, t) in enumerate(self.knockback_trail):
            age = now - t
            fade = max(0.0, 1.0 - age / PADDLE_KB_TRAIL_TIME)
            ghost_r = r * (0.55 + 0.4 * fade)
            draw_body_stamp(surf, tx, ty, heading, ghost_r, self.player, fade=fade * 0.85)

        draw_head_circle(surf, self.x, self.y, float(r), self.player)
        draw_sketch_face(surf, self.x, self.y, float(r), heading, self.player)

        if self.is_knocked_back():
            ring = int(r * (1.12 + 0.08 * math.sin(now * 24)))
            pygame.draw.circle(surf, (255, 230, 150), (int(self.x), int(self.y)), ring, 2)
        if self.is_dashing:
            pulse = 0.5 + 0.5 * math.sin(now * 13)
            dash_r = int(r + 8 + pulse * 5)
            pygame.draw.circle(surf, (255, 210, 100), (int(self.x), int(self.y)), dash_r, 2)
        if self.has_ray(now):
            pulse = 0.5 + 0.5 * math.sin(now * 14)
            ring_r = int(r + 4 + pulse * 3)
            pygame.draw.circle(surf, (100, 255, 255), (int(self.x), int(self.y)), ring_r, 2)
        speed = math.hypot(self.vx, self.vy)
        if not self.is_dashing and speed >= 100:
            pulse = 0.5 + 0.5 * math.sin(now * 14)
            ring_r = int(r + 3 + pulse * 2)
            pygame.draw.circle(surf, neon, (int(self.x), int(self.y)), ring_r, 1)


@dataclass
class FallingItem:
    kind: str
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0

    @property
    def radius(self) -> float:
        return ITEM_RADIUS

    def draw(self, surf: pygame.Surface) -> None:
        c = ITEM_COLORS.get(self.kind, (200, 200, 200))
        pygame.draw.circle(surf, c, (int(self.x), int(self.y)), ITEM_RADIUS)
        pygame.draw.circle(surf, (255, 255, 255), (int(self.x), int(self.y)), ITEM_RADIUS, 2)
        label = ITEM_SHORT.get(self.kind, "?")
        t = _item_font().render(label, True, (30, 30, 40))
        surf.blit(t, t.get_rect(center=(int(self.x), int(self.y))))


FieldItem = FallingItem


def own_half_center_x(owner: int) -> float:
    """自陣の水平中央（バー固定位置）"""
    rect = table_rect()
    if owner == 0:
        return rect.left + rect.width * BAR_CENTER_X_RATIO
    return rect.right - rect.width * BAR_CENTER_X_RATIO


@dataclass
class GuardSoldier:
    """味方兵隊 — 自陣後方から出現し、脅威パックを光線で防衛"""
    owner: int
    x: float
    y: float
    until: float
    level: int = 1
    state: str = "entering"  # entering | guarding
    ray_next_fire: float = 0.0
    size_scale: float = 1.0

    def body_radius(self) -> float:
        return GUARD_RADIUS * (1.0 + 0.08 * (self.level - 1)) * self.size_scale

    def draw(self, surf: pygame.Surface, now: float) -> None:
        bx, by = int(self.x), int(self.y)
        r = self.body_radius()
        direction = 1 if self.owner == 0 else -1
        color = GUARD_COLOR if self.owner == 0 else (200, 90, 70)
        hat = GUARD_HAT_COLOR

        # 体（棒人間）
        leg_h = int(r * 1.1)
        pygame.draw.line(surf, color, (bx, by - int(r * 0.3)), (bx, by + leg_h), 3)
        pygame.draw.line(surf, color, (bx, by), (bx - direction * int(r * 0.7), by + int(r * 0.5)), 3)
        pygame.draw.line(surf, color, (bx, by), (bx + direction * int(r * 0.9), by - int(r * 0.2)), 3)

        # 頭
        head_y = by - int(r * 0.55)
        pygame.draw.circle(surf, (240, 220, 200), (bx, head_y), int(r * 0.38))

        # 帽子
        hat_w = int(r * 0.9)
        hat_h = int(r * 0.28)
        hat_rect = pygame.Rect(bx - hat_w // 2, head_y - int(r * 0.55), hat_w, hat_h)
        pygame.draw.rect(surf, hat, hat_rect, border_radius=2)
        brim = pygame.Rect(bx - int(hat_w * 0.65), head_y - int(r * 0.3), int(hat_w * 1.3), int(r * 0.12))
        pygame.draw.rect(surf, hat, brim, border_radius=1)

        if self.state == "guarding":
            pulse = 0.5 + 0.5 * math.sin(now * 10)
            gun_x = bx + direction * int(r * 1.1)
            gun_y = by - int(r * 0.15)
            pygame.draw.line(surf, (100, 255, 255), (bx + direction * int(r * 0.5), by - int(r * 0.1)), (gun_x, gun_y), 2)
            pygame.draw.circle(surf, (180, 255, 255), (gun_x, gun_y), int(3 + pulse * 2))


StagBeetle = GuardSoldier
Assist = GuardSoldier


@dataclass
class PendingFence:
    """取得直後〜1.5秒後まで、始点を記録"""
    owner: int
    x1: float
    y1: float
    activate_at: float

    def draw(self, surf: pygame.Surface, paddle: Paddle, now: float) -> None:
        sx, sy = int(self.x1), int(self.y1)
        ex, ey = int(paddle.x), int(paddle.y)
        body_r = CATERPILLAR_BODY_RADIUS
        draw_smooth_tube(surf, float(sx), float(sy), float(ex), float(ey), body_r, self.owner, fade=0.55)


@dataclass
class Fence:
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


@dataclass
class WindEffect:
    owner: int
    started: float
    until: float
    level: int = 1

    def draw(self, surf: pygame.Surface, now: float) -> None:
        rect = table_rect()
        remaining = max(0.0, self.until - now)
        alpha = int(55 * remaining / WIND_DURATION)
        if alpha <= 0:
            return
        color = (*WIND_COLOR, alpha)
        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        step = 28
        drift = int((now - self.started) * 90) % step
        direction = 1 if self.owner == 0 else -1
        for y in range(drift, rect.height, step):
            x0 = 0 if direction > 0 else rect.width - 18
            pygame.draw.line(overlay, color, (x0, y), (x0 + direction * 18, y - 4), 2)
        surf.blit(overlay, (rect.left, rect.top))


@dataclass
class Bar:
    """自陣中央に固定される垂直バー（ラケットは通過、パックは反射）"""
    owner: int
    started: float
    until: float
    level: int = 1
    segment_hits: dict[int, int] = field(default_factory=dict)
    broken_segments: set[int] = field(default_factory=set)

    def max_height_ratio(self) -> float:
        idx = min(max(self.level, 1), len(BAR_LEVEL_HEIGHT)) - 1
        return BAR_LEVEL_HEIGHT[idx]

    def grow_ratio(self, now: float) -> float:
        return min(1.0, (now - self.started) / BAR_GROW_TIME)

    def endpoints(self, paddle: Paddle, now: float) -> tuple[float, float, float, float]:
        rect = table_rect()
        x = own_half_center_x(self.owner)
        cy = rect.centery
        g = self.grow_ratio(now) * self.max_height_ratio()
        y_top = cy - (cy - rect.top) * g
        y_bottom = cy + (rect.bottom - cy) * g
        return x, y_top, x, y_bottom

    def segment(self, paddle: Paddle, now: float) -> tuple[float, float, float, float]:
        return self.endpoints(paddle, now)

    def iter_segments(self, paddle: Paddle, now: float):
        """上から順に (idx, x1, y1, x2, y2) を返す"""
        x, y_top, _, y_bottom = self.endpoints(paddle, now)
        y = y_top
        idx = 0
        while y < y_bottom - 1e-6:
            y2 = min(y + BAR_SEGMENT_HEIGHT, y_bottom)
            yield idx, x, y, x, y2
            y = y2
            idx += 1

    def active_segments(self, paddle: Paddle, now: float):
        for idx, x1, y1, x2, y2 in self.iter_segments(paddle, now):
            if idx not in self.broken_segments:
                yield idx, x1, y1, x2, y2

    def register_ray_hit(self, idx: int) -> None:
        if idx in self.broken_segments:
            return
        hits = self.segment_hits.get(idx, 0) + 1
        self.segment_hits[idx] = hits
        if hits >= BAR_RAY_HITS_TO_BREAK:
            self.broken_segments.add(idx)

    def _segment_color(self, idx: int) -> tuple[int, int, int]:
        hits = self.segment_hits.get(idx, 0)
        if hits >= 3:
            return (95, 125, 165)
        if hits >= 2:
            return (115, 155, 205)
        if hits >= 1:
            return (130, 180, 225)
        return BAR_COLOR

    def draw(self, surf: pygame.Surface, paddle: Paddle, now: float) -> None:
        if self.grow_ratio(now) < 0.05:
            return
        px = int(own_half_center_x(self.owner))
        cy = int(table_rect().centery)
        line_w = 7
        inner_w = 2
        for idx, x1, y1, x2, y2 in self.active_segments(paddle, now):
            color = self._segment_color(idx)
            pygame.draw.line(surf, color, (px, int(y1)), (px, int(y2)), line_w)
            pygame.draw.line(surf, (240, 250, 255), (px, int(y1)), (px, int(y2)), inner_w)
        if self.grow_ratio(now) < 1.0:
            pygame.draw.circle(surf, BAR_COLOR, (px, cy), 6)


@dataclass
class RayShot:
    """光線銃の弾 — 発射時の相手位置へ飛び、命中まで表示"""
    x: float
    y: float
    vx: float
    vy: float
    owner: int
    radius: float = 7.0
    knockback: float = 0.0

    def draw(self, surf: pygame.Surface) -> None:
        r = int(self.radius)
        pygame.draw.circle(surf, RAY_COLOR, (int(self.x), int(self.y)), r)
        pygame.draw.circle(surf, (255, 255, 255), (int(self.x), int(self.y)), r, 2)
        pygame.draw.circle(surf, (200, 255, 255), (int(self.x), int(self.y)), max(2, r - 3))


# 旧 Ray（線）の別名は使わない
Ray = RayShot


def spawn_center_puck() -> Puck:
    rect = table_rect()
    return Puck(x=rect.centerx, y=rect.centery, vx=random.uniform(-80, 80), vy=random.uniform(-80, 80))


def spawn_extra_puck() -> Puck:
    """定期増加・再出現用の通常パック（中央）"""
    return spawn_center_puck()


def spawn_puck_burst(count: int) -> list[Puck]:
    """中央付近に通常パックをばらまく"""
    rect = table_rect()
    spread = min(rect.width, rect.height) * 0.28
    pucks: list[Puck] = []
    for _ in range(count):
        angle = random.uniform(0, math.tau)
        dist = random.uniform(0, spread)
        x = rect.centerx + math.cos(angle) * dist
        y = rect.centery + math.sin(angle) * dist
        out_angle = angle + random.uniform(-0.6, 0.6)
        speed = random.uniform(110, 220)
        pucks.append(Puck(
            x=x,
            y=y,
            vx=math.cos(out_angle) * speed,
            vy=math.sin(out_angle) * speed,
        ))
    return pucks


def random_corner_item_motion() -> tuple[float, float, float, float]:
    """左上・右上・右下・左下のいずれかから、コート中央へ向かって出現"""
    rect = table_rect()
    margin = ITEM_RADIUS + 16
    corners = (
        (rect.left + margin, rect.top + margin),      # 左上
        (rect.right - margin, rect.top + margin),     # 右上
        (rect.right - margin, rect.bottom - margin),  # 右下
        (rect.left + margin, rect.bottom - margin),   # 左下
    )
    x, y = random.choice(corners)
    dx = rect.centerx - x
    dy = rect.centery - y
    dist = math.hypot(dx, dy) or 1.0
    speed = ITEM_FALL_SPEED
    return x, y, dx / dist * speed, dy / dist * speed
