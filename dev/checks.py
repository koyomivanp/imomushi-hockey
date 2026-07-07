"""タイトル画面の自動検証（デモ芋虫の横断）"""

from __future__ import annotations

import random

from caterpillar_art import demo_path_crosses_screen, sample_demo_worm_spawn


def demo_spawn_always_crosses_screen(trials: int = 500) -> bool:
    """出現角度が画面を横断しないケースがないか"""
    rng = random.Random(0)
    for _ in range(trials):
        x, y, vx, vy, _ = sample_demo_worm_spawn(rng)
        if not demo_path_crosses_screen(x, y, vx, vy):
            return False
    return True


def run_title_checks() -> list[str]:
    errors: list[str] = []
    if not demo_spawn_always_crosses_screen():
        errors.append("デモ芋虫の出現角度が画面を横断しないケースがあります")
    return errors
