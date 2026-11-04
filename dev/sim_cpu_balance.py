"""CPU 芋虫の挙動をヘッドレスで計測する（固定 dt）

使い方: python dev/sim_cpu_balance.py [試合数]
難易度ごとの勝率・自殺点・試合時間・膠着・ダッシュの持続を表示する。
基準 bot は人間の代わりではなく、難易度間の相対比較のための相手。
"""

from __future__ import annotations

import math
import os
import random
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from ai import CPU_DIFFICULTY_ORDER, CPUAI
from entities import playable_rect
from game import GameState, Match

DT = 1.0 / 60.0
MATCH_LIMIT = 180.0


class ReferenceBot:
    """基準プレイヤー（反応遅れありで葉っぱの背後へ回って押す）"""

    def __init__(self, *, idle: bool = False, reaction: float = 0.18, dash_rate: float = 0.0) -> None:
        self.idle = idle
        self.reaction = reaction
        self.dash_rate = dash_rate
        self.next_update = 0.0
        self.target = (0.0, 0.0)
        self.dash = False

    def keys(self, match: Match, now: float):
        state = defaultdict(bool)
        if self.idle or not match.pucks or match.pucks_frozen:
            return state
        paddle = match.paddles[0]
        puck = match.pucks[0]
        if now >= self.next_update:
            self.next_update = now + self.reaction
            jitter = random.uniform(-14.0, 14.0)
            if puck.x < paddle.x:
                # 葉っぱが自ゴール側にある — 背後へ戻る
                self.target = (puck.x - 60.0, puck.y + jitter)
            else:
                self.target = (puck.x - 20.0, puck.y + jitter)
            self.dash = random.random() < self.dash_rate
        dx = self.target[0] - paddle.x
        dy = self.target[1] - paddle.y
        if abs(dx) > 8.0:
            state[pygame.K_d if dx > 0 else pygame.K_a] = True
        if abs(dy) > 8.0:
            state[pygame.K_s if dy > 0 else pygame.K_w] = True
        if self.dash:
            state[pygame.K_LSHIFT] = True
        return state


def play_match(difficulty: str, bot: ReferenceBot) -> dict:
    match = Match(audio=None)
    match.begin_from_menu(vs_cpu=True)
    ai = CPUAI(difficulty)
    ai.reset()
    match.enter_countdown()
    now = 0.0
    stats = {
        "own_goals": 0, "dash_frames": 0, "dash_runs": [], "stall": 0.0,
        "max_speed": 0.0, "dash_hits": 0, "goals": 0, "conceded": 0, "bot_own_goals": 0,
    }
    current_run = 0
    last_toucher = -1
    last_touch_times = {0: 0.0, 1: 0.0}
    last_cross = 0.0
    last_side = 0
    while now < MATCH_LIMIT and match.state != GameState.RESULT:
        keys = bot.keys(match, now)
        before = list(match.scores)
        match.handle_input(keys, DT, now, cpu_ai=ai)
        match.update(DT, now)
        now += DT
        cpu = match.paddles[1]
        if cpu.is_dashing:
            current_run += 1
            stats["dash_frames"] += 1
        elif current_run:
            stats["dash_runs"].append(current_run)
            current_run = 0
        if match.pucks:
            puck = match.pucks[0]
            for player in (0, 1):
                touched_at = puck.paddle_ignore_until.get(player, 0.0)
                if touched_at != last_touch_times[player]:
                    last_touch_times[player] = touched_at
                    last_toucher = player
                    if player == 1 and cpu.is_dashing:
                        stats["dash_hits"] += 1
            stats["max_speed"] = max(stats["max_speed"], math.hypot(puck.vx, puck.vy))
            side = 0 if puck.x < playable_rect().centerx else 1
            if side != last_side or match.pucks_frozen:
                last_side = side
                last_cross = now
            stats["stall"] = max(stats["stall"], now - last_cross)
        if match.scores != before:
            stats["goals"] += 1
            if match.scores[0] > before[0]:
                stats["conceded"] += 1
                if last_toucher == 1:
                    stats["own_goals"] += 1
            if match.scores[1] > before[1] and last_toucher == 0:
                stats["bot_own_goals"] += 1
            last_toucher = -1
            last_touch_times = {0: 0.0, 1: 0.0}
            last_cross = now
    stats["winner"] = match.winner
    stats["time"] = now
    stats["finished"] = match.state == GameState.RESULT
    return stats


def summarize(rows: list[dict]) -> str:
    n = len(rows)
    finished = sum(r["finished"] for r in rows)
    cpu_wins = sum(r["winner"] == 1 for r in rows)
    conceded = sum(r["conceded"] for r in rows)
    own = sum(r["own_goals"] for r in rows)
    bot_own = sum(r["bot_own_goals"] for r in rows)
    scored = sum(r["goals"] for r in rows) - conceded
    runs = [x for r in rows for x in r["dash_runs"]]
    avg_run = sum(runs) / len(runs) if runs else 0.0
    time_total = max(1.0, sum(r["time"] for r in rows))
    dash_hits = sum(r["dash_hits"] for r in rows)
    return (
        f"CPU勝率 {cpu_wins / n:5.1%} 完走 {finished}/{n} 平均 {time_total / n:5.1f}s "
        f"失点中CPU自殺点 {own}/{conceded} 得点中bot自殺点 {bot_own}/{scored} 最長膠着 {max(r['stall'] for r in rows):5.1f}s "
        f"最大速度 {max(r['max_speed'] for r in rows):4.0f} "
        f"ダッシュ {avg_run:4.1f}f/回 {len(runs) / time_total * 60:4.1f}回/分 "
        f"ダッシュ打 {dash_hits / time_total * 60:4.1f}回/分"
    )


def main() -> int:
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    pygame.init()
    pygame.display.set_mode((1, 1))
    opponents = (
        ("基準bot", lambda: ReferenceBot()),
        ("基準bot+ダッシュ", lambda: ReferenceBot(dash_rate=0.2)),
        ("放置", lambda: ReferenceBot(idle=True)),
    )
    for label, factory in opponents:
        print(f"--- 対戦相手: {label} ({games}試合) ---", flush=True)
        for key in CPU_DIFFICULTY_ORDER:
            random.seed(1234)
            rows = [play_match(key, factory()) for _ in range(games)]
            print(f"{key:7s} {summarize(rows)}", flush=True)
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
