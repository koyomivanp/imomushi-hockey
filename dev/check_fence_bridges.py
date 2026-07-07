"""フェンスチェーン描画の誤接続を検証"""

from __future__ import annotations

import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from caterpillar_art import fence_fade
from constants import CATERPILLAR_BODY_RADIUS
from entities import Fence

CHAIN_JOIN_TOLERANCE_RATIO = 0.55


def _group_fence_chains(fences: list[Fence], body_radius: float) -> list[list[Fence]]:
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


def _build_points_like_battle(ordered: list[Fence], now: float) -> tuple[list[tuple[float, float, float]], list[int]]:
    count = len(ordered)
    points: list[tuple[float, float, float]] = []
    skipped_indices: list[int] = []
    for index, fence in enumerate(ordered):
        rank = index / max(1, count - 1) if count > 1 else 1.0
        fade = fence_fade(fence, now, rank)
        if fade <= 0.04:
            skipped_indices.append(index)
            continue
        if not points:
            points.append((fence.x1, fence.y1, fade))
        points.append((fence.x2, fence.y2, fade))
    return points, skipped_indices


def _max_span_jump(points: list[tuple[float, float, float]]) -> float:
    best = 0.0
    for i in range(1, len(points)):
        x1, y1, _ = points[i - 1]
        x2, y2, _ = points[i]
        best = max(best, math.hypot(x2 - x1, y2 - y1))
    return best


def main() -> None:
    now = 100.0
    fences: list[Fence] = []
    x, y = 100.0, 200.0
    for i in range(8):
        nx = x + 30.0
        ny = y + (15.0 if i % 2 == 0 else -12.0)
        fences.append(
            Fence(
                owner=0,
                x1=x,
                y1=y,
                x2=nx,
                y2=ny,
                until=now + 2.6 - i * 0.15,
                created_at=now - (8 - i) * 0.2,
            )
        )
        x, y = nx, ny

    chains = _group_fence_chains(fences, CATERPILLAR_BODY_RADIUS)
    for chain in chains:
        ordered = sorted(chain, key=lambda f: f.created_at)
        points, skipped = _build_points_like_battle(ordered, now)
        max_seg = 35.0
        max_jump = _max_span_jump(points)
        print(f"skipped={skipped} maxJump={max_jump:.1f} suspicious={max_jump > max_seg * 1.25}")


if __name__ == "__main__":
    main()
