"""芋虫ホッケー用ビジュアル — イメージ図準拠（細長スタンプ連打＋デカ目）"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import pygame

from constants import CATERPILLAR_BODY_RADIUS
from visuals import draw_neon_disc

P1_BODY = (52, 185, 102)
P1_BELLY = (130, 235, 155)
P1_OUTLINE = (22, 105, 62)

P2_BODY = (215, 72, 165)
P2_BELLY = (248, 155, 210)
P2_OUTLINE = (135, 32, 100)

LEAF_BODY = (72, 200, 88)
LEAF_EDGE = (40, 150, 58)
LEAF_VEIN = (120, 230, 120)

# スタンプ間隔（半径に対する比率）— 小さいほどなめらか
STAMP_SPACING_RATIO = 0.11
STAMP_MIN_SPACING_PX = 1.5
CORNER_TRIM_RATIO = 0.72
FACE_TURN_SPEED = 14.0


def _palette(player: int) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    if player == 0:
        return P1_BODY, P1_BELLY, P1_OUTLINE
    return P2_BODY, P2_BELLY, P2_OUTLINE


def _tint(color: tuple[int, int, int], fade: float) -> tuple[int, int, int]:
    f = max(0.0, min(1.0, fade))
    return tuple(int(c * f) for c in color)


def _angle_diff(from_angle: float, to_angle: float) -> float:
    return (to_angle - from_angle + math.pi) % (2.0 * math.pi) - math.pi


def lerp_angle(from_angle: float, to_angle: float, t: float) -> float:
    return from_angle + _angle_diff(from_angle, to_angle) * max(0.0, min(1.0, t))


def _circle_stamp(
    surf: pygame.Surface,
    cx: float,
    cy: float,
    radius: float,
    body: tuple[int, int, int],
) -> None:
    r = max(3, int(radius))
    pygame.draw.circle(surf, body, (int(cx), int(cy)), r)


def _elongated_stamp(
    surf: pygame.Surface,
    cx: float,
    cy: float,
    angle: float,
    radius: float,
    body: tuple[int, int, int],
) -> None:
    """細長カプセル1個 — 枠線なし・単色"""
    r = max(3, int(radius))
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    ix, iy = int(cx), int(cy)
    pygame.draw.circle(surf, body, (ix, iy), r)
    for t in (-0.48, 0.48):
        ox = cos_a * r * t
        oy = sin_a * r * t
        pygame.draw.circle(surf, body, (int(cx + ox), int(cy + oy)), max(2, int(r * 0.9)))


def _append_line_samples(
    samples: list[tuple[float, float, float]],
    x1: float,
    y1: float,
    f1: float,
    x2: float,
    y2: float,
    f2: float,
    spacing: float,
) -> None:
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 0.25:
        return
    steps = max(1, int(length / spacing))
    for i in range(steps + 1):
        t = i / steps
        samples.append((x1 + dx * t, y1 + dy * t, f1 + (f2 - f1) * t))


def _append_arc_samples(
    samples: list[tuple[float, float, float]],
    cx: float,
    cy: float,
    radius: float,
    a_start: float,
    a_end: float,
    fade: float,
    spacing: float,
) -> None:
    da = _angle_diff(a_start, a_end)
    arc_len = abs(da) * radius
    steps = max(2, int(arc_len / spacing))
    for i in range(steps + 1):
        t = i / steps
        ang = a_start + da * t
        samples.append((cx + math.cos(ang) * radius, cy + math.sin(ang) * radius, fade))


def _rounded_path_samples(
    points: list[tuple[float, float, float]],
    radius: float,
    spacing: float,
) -> list[tuple[float, float, float]]:
    """折れ線の角を丸めた等間隔サンプル点（直角でもなめらか）"""
    if len(points) < 2:
        return []

    samples: list[tuple[float, float, float]] = []
    trim = max(3.0, radius * CORNER_TRIM_RATIO)
    n = len(points)

    for seg_i in range(n - 1):
        x1, y1, f1 = points[seg_i]
        x2, y2, f2 = points[seg_i + 1]
        dx, dy = x2 - x1, y2 - y1
        seg_len = math.hypot(dx, dy)
        if seg_len < 0.5:
            continue
        ux, uy = dx / seg_len, dy / seg_len

        trim_in = 0.0 if seg_i == 0 else min(trim, seg_len * 0.45)
        trim_out = 0.0 if seg_i == n - 2 else min(trim, seg_len * 0.45)

        sx = x1 + ux * trim_in
        sy = y1 + uy * trim_in
        ex = x2 - ux * trim_out
        ey = y2 - uy * trim_out
        _append_line_samples(samples, sx, sy, f1, ex, ey, f2, spacing)

        if seg_i >= n - 2:
            continue

        x3, y3, f3 = points[seg_i + 2]
        dx2, dy2 = x3 - x2, y3 - y2
        out_len = math.hypot(dx2, dy2)
        if out_len < 0.5:
            continue
        ux2, uy2 = dx2 / out_len, dy2 / out_len

        t_in = min(trim, seg_len * 0.45)
        t_out = min(trim, out_len * 0.45)
        p_in = (x2 - ux * t_in, y2 - uy * t_in)
        p_out = (x2 + ux2 * t_out, y2 + uy2 * t_out)

        in_ang = math.atan2(uy, ux)
        out_ang = math.atan2(uy2, ux2)
        turn = abs(_angle_diff(in_ang, out_ang))
        if turn < 0.12:
            _append_line_samples(samples, p_in[0], p_in[1], f2, p_out[0], p_out[1], f2, spacing)
            continue

        half = turn * 0.5
        arc_r = t_in / max(0.15, math.tan(half))
        bis_x = ux2 - ux
        bis_y = uy2 - uy
        bis_len = math.hypot(bis_x, bis_y)
        if bis_len < 1e-5:
            mid_x = (p_in[0] + p_out[0]) * 0.5
            mid_y = (p_in[1] + p_out[1]) * 0.5
            _append_line_samples(samples, p_in[0], p_in[1], f2, mid_x, mid_y, f2, spacing)
            _append_line_samples(samples, mid_x, mid_y, f2, p_out[0], p_out[1], f2, spacing)
            continue
        bis_x /= bis_len
        bis_y /= bis_len
        dist_c = arc_r / max(0.15, math.sin(half))
        ccx = x2 + bis_x * dist_c
        ccy = y2 + bis_y * dist_c
        a_start = math.atan2(p_in[1] - ccy, p_in[0] - ccx)
        a_end = math.atan2(p_out[1] - ccy, p_out[0] - ccx)
        _append_arc_samples(samples, ccx, ccy, arc_r, a_start, a_end, f2, spacing)

    return samples


def draw_stamp_path(
    surf: pygame.Surface,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    player: int,
    fade: float = 1.0,
) -> None:
    """1区間を細長スタンプで埋める（スリザリオの連打）"""
    body, _belly, _outline = _palette(player)
    spacing = max(STAMP_MIN_SPACING_PX, radius * STAMP_SPACING_RATIO)
    points = [(x1, y1, fade), (x2, y2, fade)]
    for px, py, f in _rounded_path_samples(points, radius, spacing):
        _circle_stamp(surf, px, py, radius, _tint(body, f))


def draw_smooth_tube(
    surf: pygame.Surface,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    player: int,
    fade: float = 1.0,
) -> None:
    draw_stamp_path(surf, x1, y1, x2, y2, radius, player, fade=fade)


def fence_fade(fence: Fence, now: float, age_rank: float) -> float:
    from constants import TRAIL_FADE_START_RATIO, TRAIL_WALL_MIN_BRIGHTNESS

    remaining = max(0.0, fence.until - now)
    total = max(0.001, fence.until - fence.created_at)
    life_ratio = remaining / total
    if life_ratio <= TRAIL_FADE_START_RATIO:
        expire_fade = life_ratio / TRAIL_FADE_START_RATIO
    else:
        expire_fade = 1.0
    age_rank = max(0.0, min(1.0, age_rank))
    age_brightness = TRAIL_WALL_MIN_BRIGHTNESS + (1.0 - TRAIL_WALL_MIN_BRIGHTNESS) * age_rank
    return expire_fade * age_brightness


def draw_player_fences(
    surf: pygame.Surface,
    fences: list[Fence],
    now: float,
    body_radius: float,
) -> None:
    """体節は1区間ずつ描画（誤接続・フェード分割の浮き節を防ぐ）"""
    if not fences:
        return
    ordered = sorted(fences, key=lambda f: f.created_at)
    n = len(ordered)
    for i, fence in enumerate(ordered):
        rank = i / max(1, n - 1) if n > 1 else 1.0
        fade = fence_fade(fence, now, rank)
        if fade <= 0.04:
            continue
        draw_smooth_tube(
            surf, fence.x1, fence.y1, fence.x2, fence.y2,
            body_radius, fence.owner, fade=fade,
        )


def draw_head_circle(
    surf: pygame.Surface,
    x: float,
    y: float,
    radius: float,
    player: int,
    fade: float = 1.0,
) -> None:
    """頭＝体と同じ太さの丸（単色）"""
    body, _belly, _outline = _palette(player)
    c_body = _tint(body, fade)
    r = max(3, int(radius))
    ix, iy = int(x), int(y)
    pygame.draw.circle(surf, c_body, (ix, iy), r + 1)
    pygame.draw.circle(surf, c_body, (ix, iy), r)


def draw_sketch_face(
    surf: pygame.Surface,
    x: float,
    y: float,
    radius: float,
    heading: float,
    player: int,
    fade: float = 1.0,
) -> None:
    """イメージ図 — 大きな白目（非重複）＋丸い黒目＋先端のω口"""
    _body, _belly, outline = _palette(player)
    f = max(0.0, min(1.0, fade))
    r = float(radius)
    cx, cy = float(x), float(y)
    fwd_x, fwd_y = math.cos(heading), math.sin(heading)
    perp_x, perp_y = -fwd_y, fwd_x
    c_outline = _tint(outline, f)
    c_ink = _tint((14, 12, 18), f)

    # 白目は大きめ・左右で接する（中心間 = 2*eye_r、重なりなし）
    face_fwd = r * 0.12
    face_cx = cx + fwd_x * face_fwd
    face_cy = cy + fwd_y * face_fwd

    eye_r = max(5.0, r * 0.54)
    eye_sep = 2.0 * eye_r
    eye_fwd = r * 0.20

    for side in (-1, 1):
        ex = face_cx + fwd_x * eye_fwd + perp_x * eye_sep * side * 0.5
        ey = face_cy + fwd_y * eye_fwd + perp_y * eye_sep * side * 0.5
        er = int(eye_r)
        pygame.draw.circle(surf, (255, 255, 255), (int(ex), int(ey)), er)
        pr = max(2, int(er * 0.58))
        pygame.draw.circle(surf, c_ink, (int(ex), int(ey)), pr)

    tip_x = face_cx + fwd_x * r * 0.52
    tip_y = face_cy + fwd_y * r * 0.58
    w = r * 0.13
    dip = r * 0.09
    left = (int(tip_x - perp_x * w), int(tip_y - perp_y * w))
    mid = (int(tip_x + fwd_x * dip), int(tip_y + fwd_y * dip))
    right = (int(tip_x + perp_x * w), int(tip_y + perp_y * w))
    lw = max(2, int(r // 7))
    pygame.draw.lines(surf, c_outline, False, [left, mid, right], lw)
    pygame.draw.lines(surf, c_ink, False, [left, mid, right], max(1, lw - 1))


def draw_body_stamp(
    surf: pygame.Surface,
    x: float,
    y: float,
    angle: float,
    radius: float,
    player: int,
    fade: float = 1.0,
    shade: float = 1.0,
) -> None:
    _ = shade
    body, _belly, _outline = _palette(player)
    _elongated_stamp(surf, x, y, angle, radius, _tint(body, fade))


def draw_caterpillar_head(
    surf: pygame.Surface,
    x: float,
    y: float,
    radius: float,
    player: int,
    heading: float,
    now: float,
    neon: tuple[int, int, int],
    *,
    dashing: bool = False,
    knocked: bool = False,
) -> None:
    cx, cy = int(x), int(y)
    r = int(radius)
    pulse = 0.5 + 0.5 * math.sin(now * 13)

    if dashing:
        draw_neon_disc(surf, cx, cy, r + 8, neon, fade=0.45, pulse=pulse * 0.35)
    if knocked:
        ring = int(r * (1.12 + 0.08 * math.sin(now * 24)))
        pygame.draw.circle(surf, (255, 230, 150), (cx, cy), ring, 2)

    draw_head_circle(surf, x, y, radius, player)
    draw_sketch_face(surf, x, y, radius, heading, player)


# --- タイトル画面デモ走行 ---
TITLE_DEMO_SPAWN_MIN = 3.0
TITLE_DEMO_SPAWN_MAX = 5.0
TITLE_DEMO_SPEED_MIN = 115.0
TITLE_DEMO_SPEED_MAX = 175.0
TITLE_DEMO_SPAWN_MARGIN = 48.0
TITLE_DEMO_OFFSCREEN_MARGIN = 56.0


def _title_scene_radii() -> tuple[float, float, float]:
    from constants import (
        CATERPILLAR_BODY_RADIUS,
        TITLE_SCENE_BODY_SCALE,
        TITLE_SCENE_HEAD_RADIUS_SCALE,
        TITLE_SCENE_LEAF_RADIUS,
    )

    body_r = CATERPILLAR_BODY_RADIUS * TITLE_SCENE_BODY_SCALE * 0.92
    head_r = CATERPILLAR_BODY_RADIUS * TITLE_SCENE_BODY_SCALE * TITLE_SCENE_HEAD_RADIUS_SCALE
    return body_r, head_r, TITLE_SCENE_LEAF_RADIUS


def _draw_title_trail_chain(
    surf: pygame.Surface,
    segments: list,
    now: float,
    body_radius: float,
) -> None:
    """タイトル用 — 1本の折れ線として連続スタンプ（区間ごとの輪郭リング重複を避ける）"""
    if not segments:
        return
    ordered = sorted(segments, key=lambda fence: fence.created_at)
    count = len(ordered)
    player = ordered[0].owner
    body, _, _ = _palette(player)
    moss_blend = (58, 98, 64)
    spacing = max(STAMP_MIN_SPACING_PX, body_radius * STAMP_SPACING_RATIO)

    points: list[tuple[float, float, float]] = []
    for index, fence in enumerate(ordered):
        rank = index / max(1, count - 1) if count > 1 else 1.0
        fade = fence_fade(fence, now, rank)
        if fade <= 0.04:
            continue
        if not points:
            points.append((fence.x1, fence.y1, fade))
        points.append((fence.x2, fence.y2, fade))

    if len(points) < 2:
        return

    for px, py, fade in _rounded_path_samples(points, body_radius, spacing):
        blended = tuple(int(body[i] * 0.88 + moss_blend[i] * 0.12) for i in range(3))
        _circle_stamp(surf, px, py, body_radius, _tint(blended, fade))


@dataclass
class _DemoWorm:
    player: int
    x: float
    y: float
    vx: float
    vy: float
    trail_x: float
    trail_y: float
    trail_spawn_until: float
    segments: list = field(default_factory=list)

    @property
    def heading(self) -> float:
        return math.atan2(self.vy, self.vx)


def sample_demo_worm_spawn(
    rng: random.Random | None = None,
) -> tuple[float, float, float, float, int]:
    """デモ芋虫の出現パラメータ（x, y, vx, vy, player）"""
    from constants import SCREEN_H, SCREEN_W

    source = rng if rng is not None else random
    body_r, _, _ = _title_scene_radii()
    margin = TITLE_DEMO_SPAWN_MARGIN + body_r
    edge = source.randint(0, 3)

    if edge == 0:
        x = -margin
        y = source.uniform(margin, SCREEN_H - margin)
    elif edge == 1:
        x = SCREEN_W + margin
        y = source.uniform(margin, SCREEN_H - margin)
    elif edge == 2:
        x = source.uniform(margin, SCREEN_W - margin)
        y = -margin
    else:
        x = source.uniform(margin, SCREEN_W - margin)
        y = SCREEN_H + margin

    target_x = source.uniform(margin, SCREEN_W - margin)
    target_y = source.uniform(margin, SCREEN_H - margin)
    angle = math.atan2(target_y - y, target_x - x)
    speed = source.uniform(TITLE_DEMO_SPEED_MIN, TITLE_DEMO_SPEED_MAX)
    vx = math.cos(angle) * speed
    vy = math.sin(angle) * speed
    player = source.randint(0, 1)
    return x, y, vx, vy, player


def demo_path_crosses_screen(
    x: float,
    y: float,
    vx: float,
    vy: float,
    *,
    margin: float = 0.0,
) -> bool:
    """移動経路が画面内領域を横断するか（画面外に逃げる角度を除外する検証用）"""
    from constants import SCREEN_H, SCREEN_W

    left, top = margin, margin
    right, bottom = SCREEN_W - margin, SCREEN_H - margin
    if left <= x <= right and top <= y <= bottom:
        return True

    speed = math.hypot(vx, vy)
    if speed < 1e-6:
        return False

    max_t = (max(SCREEN_W, SCREEN_H) + TITLE_DEMO_SPAWN_MARGIN * 4.0) / speed
    steps = 96
    prev_inside = left <= x <= right and top <= y <= bottom
    for i in range(1, steps + 1):
        t = max_t * i / steps
        px = x + vx * t
        py = y + vy * t
        inside = left <= px <= right and top <= py <= bottom
        if inside and not prev_inside:
            return True
        if inside:
            return True
        prev_inside = inside
    return False


class TitleDemoSystem:
    """タイトル背景 — バトル同形式の短命軌跡（尻尾からフェード）"""

    def __init__(self) -> None:
        self.worms: list[_DemoWorm] = []
        self.fading_trails: list[list] = []
        self.spawn_timer = 0.0
        self.next_spawn_delay = self._random_spawn_delay()
        self._spawn_counts = [0, 0]
        self._spawn_worm()

    def reset(self) -> None:
        self.worms.clear()
        self.fading_trails.clear()
        self.spawn_timer = 0.0
        self.next_spawn_delay = self._random_spawn_delay()
        self._spawn_counts = [0, 0]
        self._spawn_worm()

    @staticmethod
    def _random_spawn_delay() -> float:
        return random.uniform(TITLE_DEMO_SPAWN_MIN, TITLE_DEMO_SPAWN_MAX)

    def _pick_balanced_player(self) -> int:
        if self._spawn_counts[0] < self._spawn_counts[1]:
            return 0
        if self._spawn_counts[1] < self._spawn_counts[0]:
            return 1
        return random.choice((0, 1))

    def _spawn_worm(self) -> None:
        x, y, vx, vy, _ = sample_demo_worm_spawn()
        player = self._pick_balanced_player()
        self._spawn_counts[player] += 1
        self.worms.append(_DemoWorm(player, x, y, vx, vy, x, y, 0.0))

    def _add_trail_segment(
        self,
        worm: _DemoWorm,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        now: float,
    ) -> None:
        from constants import (
            FENCE_HALF_WIDTH,
            FENCE_MIN_LENGTH,
            TITLE_DEMO_TRAIL_LIFETIME,
            TITLE_DEMO_TRAIL_MAX_SEGMENTS,
            TRAIL_SPAWN_COOLDOWN,
        )
        from entities import Fence

        seg_len = math.hypot(x2 - x1, y2 - y1)
        if seg_len < FENCE_MIN_LENGTH:
            return
        if now < worm.trail_spawn_until:
            return
        while len(worm.segments) >= TITLE_DEMO_TRAIL_MAX_SEGMENTS:
            worm.segments.pop(0)
        worm.segments.append(Fence(
            owner=worm.player,
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            until=now + TITLE_DEMO_TRAIL_LIFETIME,
            created_at=now,
            half_width=FENCE_HALF_WIDTH,
        ))
        worm.trail_spawn_until = now + TRAIL_SPAWN_COOLDOWN

    def _update_worm_trail(self, worm: _DemoWorm, now: float) -> None:
        from constants import TRAIL_SEGMENT_INTERVAL

        dx = worm.x - worm.trail_x
        dy = worm.y - worm.trail_y
        dist = math.hypot(dx, dy)
        if dist < TRAIL_SEGMENT_INTERVAL:
            return
        self._add_trail_segment(worm, worm.trail_x, worm.trail_y, worm.x, worm.y, now)
        worm.trail_x = worm.x
        worm.trail_y = worm.y

    @staticmethod
    def _prune_segments(segments: list, now: float) -> list:
        return [segment for segment in segments if segment.until > now]

    @staticmethod
    def _is_off_screen(worm: _DemoWorm, margin: float) -> bool:
        from constants import SCREEN_H, SCREEN_W

        return (
            worm.x < -margin
            or worm.x > SCREEN_W + margin
            or worm.y < -margin
            or worm.y > SCREEN_H + margin
        )

    def update(self, dt: float, now: float) -> None:
        if dt <= 0.0:
            return

        self.spawn_timer += dt
        if self.spawn_timer >= self.next_spawn_delay:
            self.spawn_timer = 0.0
            self.next_spawn_delay = self._random_spawn_delay()
            self._spawn_worm()

        body_r, _, _ = _title_scene_radii()
        off_margin = TITLE_DEMO_OFFSCREEN_MARGIN + body_r
        survivors: list[_DemoWorm] = []
        for worm in self.worms:
            worm.x += worm.vx * dt
            worm.y += worm.vy * dt
            self._update_worm_trail(worm, now)
            worm.segments = self._prune_segments(worm.segments, now)
            if self._is_off_screen(worm, off_margin):
                if worm.segments:
                    self.fading_trails.append(worm.segments)
            else:
                survivors.append(worm)
        self.worms = survivors

        self.fading_trails = [
            chain for chain in (
                self._prune_segments(trail, now) for trail in self.fading_trails
            )
            if chain
        ]

    def draw(self, surf: pygame.Surface, now: float = 0.0) -> None:
        from constants import FENCE_HALF_WIDTH

        _, head_r, _ = _title_scene_radii()
        trail_r = FENCE_HALF_WIDTH

        for trail in self.fading_trails:
            _draw_title_trail_chain(surf, trail, now, trail_r)
        for worm in self.worms:
            _draw_title_trail_chain(surf, worm.segments, now, trail_r)
            draw_head_circle(surf, worm.x, worm.y, head_r, worm.player)
            draw_sketch_face(surf, worm.x, worm.y, head_r, worm.heading, worm.player)


_title_demo_system: TitleDemoSystem | None = None


def get_title_demo_system() -> TitleDemoSystem:
    global _title_demo_system
    if _title_demo_system is None:
        _title_demo_system = TitleDemoSystem()
    return _title_demo_system


def reset_title_demo() -> None:
    global _title_demo_system
    if _title_demo_system is not None:
        _title_demo_system.reset()
    else:
        _title_demo_system = TitleDemoSystem()


def update_title_demo(dt: float, now: float) -> None:
    get_title_demo_system().update(dt, now)


def title_scene_bbox() -> tuple[float, float, float, float]:
    """中央葉っぱのおおよその bbox（レイアウト検証用）"""
    from constants import TITLE_LEAF_X, TITLE_LEAF_Y, TITLE_SCENE_LEAF_RADIUS

    pad = 8.0
    r = TITLE_SCENE_LEAF_RADIUS
    return (
        TITLE_LEAF_X - r - pad,
        TITLE_LEAF_Y - r - pad,
        TITLE_LEAF_X + r + pad,
        TITLE_LEAF_Y + r + pad,
    )


def draw_title_leaf_scene(surf: pygame.Surface, now: float = 0.0) -> None:
    """タイトル背景 — デモ走行の軌跡＋中央の葉っぱ＋走行中の芋虫"""
    get_title_demo_system().draw(surf, now)


def draw_leaf_puck(
    surf: pygame.Surface,
    x: float,
    y: float,
    radius: float,
    now: float,
) -> None:
    r = int(radius)
    cx, cy = int(x), int(y)
    spin = now * 2.4
    cos_a, sin_a = math.cos(spin), math.sin(spin)

    def rot(px: float, py: float) -> tuple[int, int]:
        return (
            int(cx + px * cos_a - py * sin_a),
            int(cy + px * sin_a + py * cos_a),
        )

    tip = rot(r * 1.15, 0)
    left = rot(-r * 0.55, -r * 0.75)
    right = rot(-r * 0.55, r * 0.75)
    stem = rot(-r * 0.95, 0)

    pygame.draw.polygon(surf, LEAF_BODY, [tip, left, stem, right])
    pygame.draw.polygon(surf, LEAF_EDGE, [tip, left, stem, right], max(1, r // 6))
    vein_end = rot(r * 0.35, 0)
    pygame.draw.line(surf, LEAF_VEIN, stem, vein_end, max(1, r // 7))
    pygame.draw.line(surf, LEAF_VEIN, rot(0, 0), left, max(1, r // 9))
    pygame.draw.line(surf, LEAF_VEIN, rot(0, 0), right, max(1, r // 9))
