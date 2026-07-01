"""タイトル画面の自動検証（スタンプ重なり・ロゴ被り）"""

from __future__ import annotations

import math

from constants import (
    CATERPILLAR_BODY_RADIUS,
    TITLE_CONTENT_W,
    TITLE_LEAF_X,
    TITLE_LEAF_Y,
    TITLE_SCENE_ARC_LIFT,
    TITLE_SCENE_BODY_SCALE,
    TITLE_SCENE_SIDE_GAP,
    TITLE_SCENE_SPAN,
)
from caterpillar_art import STAMP_MIN_SPACING_PX, STAMP_SPACING_RATIO, _rounded_path_samples

# screens.TITLE_LOGO_LEFT と同じ
LOGO_LEFT = 44
LOGO_TOP = 52
LOGO_WIDTH = 200
LOGO_HEIGHT = 130


def title_worm_control_points() -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    lx, ly = TITLE_LEAF_X, TITLE_LEAF_Y
    span = TITLE_SCENE_SPAN
    arc_lift = TITLE_SCENE_ARC_LIFT
    side = TITLE_SCENE_SIDE_GAP
    p1 = [
        (lx - span, ly - side),
        (lx - span * 0.4, ly - arc_lift),
        (lx, ly - arc_lift - 18),
        (lx + span * 0.4, ly - arc_lift),
        (lx + span, ly - side),
    ]
    p2 = [
        (lx + span, ly + side),
        (lx + span * 0.4, ly + arc_lift),
        (lx, ly + arc_lift + 18),
        (lx - span * 0.4, ly + arc_lift),
        (lx - span, ly + side),
    ]
    return p1, p2


def _stamp_centers(points: list[tuple[float, float]], body_r: float) -> list[tuple[float, float]]:
    spacing = max(STAMP_MIN_SPACING_PX, body_r * STAMP_SPACING_RATIO)
    poly = [(x, y, 1.0) for x, y in points]
    return [(x, y) for x, y, _ in _rounded_path_samples(poly, body_r, spacing)]


def count_worm_stamp_overlaps() -> tuple[int, float]:
    """2本の芋虫スタンプ同士の重なり数と最小中心距離を返す"""
    body_r = CATERPILLAR_BODY_RADIUS * TITLE_SCENE_BODY_SCALE
    p1, p2 = title_worm_control_points()
    s1 = _stamp_centers(p1, body_r)
    s2 = _stamp_centers(p2, body_r)
    min_d = min(math.hypot(a[0] - b[0], a[1] - b[1]) for a in s1 for b in s2)
    overlaps = sum(
        1 for a in s1 for b in s2 if math.hypot(a[0] - b[0], a[1] - b[1]) < 2 * body_r
    )
    return overlaps, min_d


def worm_scene_bbox() -> tuple[float, float, float, float]:
    """葉シーン全体のスタンプ＋頭を含むおおよその bbox"""
    body_r = CATERPILLAR_BODY_RADIUS * TITLE_SCENE_BODY_SCALE
    head_r = body_r
    p1, p2 = title_worm_control_points()
    xs: list[float] = []
    ys: list[float] = []
    for pts in (p1, p2):
        for x, y in _stamp_centers(pts, body_r):
            xs.append(x)
            ys.append(y)
        hx, hy = pts[-1][0], pts[-1][1]
        xs.extend((hx - head_r, hx + head_r))
        ys.extend((hy - head_r, hy + head_r))
    pad = 8.0
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def logo_rect() -> tuple[float, float, float, float]:
    return LOGO_LEFT, LOGO_TOP, LOGO_LEFT + LOGO_WIDTH, LOGO_TOP + LOGO_HEIGHT


def _rects_overlap(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def logo_overlaps_worms() -> bool:
    return _rects_overlap(logo_rect(), worm_scene_bbox())


def leaf_scene_extends_into_menu() -> bool:
    """左イラストが右メニュー領域にはみ出していないか"""
    _, _, right, _ = worm_scene_bbox()
    return right > TITLE_CONTENT_W + 12


def run_title_checks() -> list[str]:
    errors: list[str] = []
    overlaps, min_d = count_worm_stamp_overlaps()
    if overlaps > 0:
        errors.append(f"芋虫スタンプが {overlaps} 箇所重なっています（min_dist={min_d:.1f}）")
    if logo_overlaps_worms():
        errors.append("タイトルロゴと芋虫シーンが bbox 上で重なっています")
    if leaf_scene_extends_into_menu():
        errors.append("芋虫シーンが右メニュー領域にはみ出しています")
    return errors
