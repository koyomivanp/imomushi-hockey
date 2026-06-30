"""芋虫ホッケー用ビジュアル — イメージ図準拠（細長スタンプ連打＋デカ目）"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from constants import CATERPILLAR_BODY_RADIUS
from visuals import draw_neon_disc

if TYPE_CHECKING:
    from entities import Fence

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


def caterpillar_radius() -> float:
    return CATERPILLAR_BODY_RADIUS


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
    c_body = _tint(body, fade)
    spacing = max(STAMP_MIN_SPACING_PX, radius * STAMP_SPACING_RATIO)
    points = [(x1, y1, fade), (x2, y2, fade)]
    for px, py, f in _rounded_path_samples(points, radius, spacing):
        _circle_stamp(surf, px, py, radius, _tint(body, f))


def _stamp_along_polyline(
    surf: pygame.Surface,
    points: list[tuple[float, float, float]],
    radius: float,
    player: int,
) -> None:
    """折れ線を丸角化して円スタンプで高密度に埋める"""
    if len(points) < 2:
        return

    body, _belly, _outline = _palette(player)
    spacing = max(STAMP_MIN_SPACING_PX, radius * STAMP_SPACING_RATIO)
    for px, py, fade in _rounded_path_samples(points, radius, spacing):
        _circle_stamp(surf, px, py, radius, _tint(body, fade))


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


def draw_connected_trail(
    surf: pygame.Surface,
    segments: list[tuple[float, float, float, float, float]],
    radius: float,
    player: int,
) -> None:
    """複数区間を1本の折れ線として高密度スタンプで描く"""
    if not segments:
        return
    points: list[tuple[float, float, float]] = [
        (segments[0][0], segments[0][1], segments[0][4]),
    ]
    for x1, y1, x2, y2, fade in segments:
        points.append((x2, y2, fade))
    _stamp_along_polyline(surf, points, radius, player)


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


CHAIN_JOIN_TOLERANCE_RATIO = 0.55


def _group_fence_chains(fences: list[Fence], body_radius: float) -> list[list[Fence]]:
    """つながっている軌跡だけを1チェーンにまとめる（離れた区間を誤接続しない）"""
    ordered = sorted(fences, key=lambda f: f.created_at)
    tol = max(4.0, body_radius * CHAIN_JOIN_TOLERANCE_RATIO)
    chains: list[list[Fence]] = []
    current: list[Fence] = []
    for fence in ordered:
        if not current:
            current.append(fence)
            continue
        prev = current[-1]
        gap = math.hypot(fence.x1 - prev.x2, fence.y1 - prev.y2)
        if gap <= tol:
            current.append(fence)
        else:
            chains.append(current)
            current = [fence]
    if current:
        chains.append(current)
    return chains


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


draw_simple_face = draw_sketch_face
draw_topdown_face = draw_sketch_face


def draw_worm_chain(
    surf: pygame.Surface,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    player: int,
    fade: float,
    body_radius: float,
    *,
    shade: float = 1.0,
) -> None:
    _ = shade
    draw_stamp_path(surf, x1, y1, x2, y2, body_radius, player, fade=fade)


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


def draw_caterpillar_segment(
    surf: pygame.Surface,
    x: float,
    y: float,
    radius: float,
    player: int,
    fade: float = 1.0,
    pulse: float = 0.0,
    segment_index: int = 0,
    angle: float = 0.0,
) -> None:
    _ = pulse
    _ = segment_index
    draw_body_stamp(surf, x, y, angle, radius, player, fade=fade)


def draw_segment_chain(
    surf: pygame.Surface,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    player: int,
    fade: float,
    now: float,
    created_at: float,
    body_radius: float,
) -> None:
    _ = now
    _ = created_at
    draw_stamp_path(surf, x1, y1, x2, y2, body_radius, player, fade=fade)


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
