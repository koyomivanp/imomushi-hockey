"""CPUプレイヤー（P2・右側）の移動判断"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from entities import Fence, Paddle, Puck, arena_frame_rect, goal_bounds, playable_rect

CPU_PLAYER = 1


@dataclass(frozen=True)
class CPUDifficulty:
    key: str
    label: str
    reaction_min: float
    reaction_max: float
    aim_error: float
    threat_score_defend: float
    intercept_lead: float  # 守備・攻撃の先読み倍率（大=強い）


    dash_chance: float
    dash_cooldown: float


DIFFICULTIES: dict[str, CPUDifficulty] = {
    "easy": CPUDifficulty(
        key="easy",
        label="のろのろ",
        reaction_min=0.14,
        reaction_max=0.26,
        aim_error=34.0,
        threat_score_defend=820.0,
        intercept_lead=0.48,
        dash_chance=0.22,
        dash_cooldown=1.15,
    ),
    "normal": CPUDifficulty(
        key="normal",
        label="ふつう",
        reaction_min=0.06,
        reaction_max=0.14,
        aim_error=18.0,
        threat_score_defend=650.0,
        intercept_lead=0.65,
        dash_chance=0.34,
        dash_cooldown=1.05,
    ),
    "hard": CPUDifficulty(
        key="hard",
        label="はげしい",
        reaction_min=0.03,
        reaction_max=0.07,
        aim_error=7.0,
        threat_score_defend=480.0,
        intercept_lead=0.82,
        dash_chance=0.48,
        dash_cooldown=0.88,
    ),
}

DEFAULT_CPU_DIFFICULTY = "normal"
CPU_DIFFICULTY_ORDER = ("easy", "normal", "hard")


class CPUAI:
    def __init__(self, difficulty: str = DEFAULT_CPU_DIFFICULTY) -> None:
        self._difficulty_key = difficulty if difficulty in DIFFICULTIES else DEFAULT_CPU_DIFFICULTY
        self._target = (0.0, 0.0)
        self._next_update = 0.0
        self._dash_cooldown_until = 0.0

    @property
    def difficulty(self) -> CPUDifficulty:
        return DIFFICULTIES[self._difficulty_key]

    def set_difficulty(self, key: str) -> None:
        if key in DIFFICULTIES:
            self._difficulty_key = key

    def reset(self) -> None:
        play = playable_rect()
        self._target = (play.right - play.width * 0.2, play.centery)
        self._next_update = 0.0
        self._dash_cooldown_until = 0.0

    def decide(
        self,
        paddle: Paddle,
        opponent: Paddle,
        pucks: list[Puck],
        fences: list[Fence],
        now: float,
        pucks_frozen: bool,
    ) -> tuple[float, float, bool]:
        if pucks_frozen or not pucks:
            return 0.0, 0.0, False

        diff = self.difficulty
        if now >= self._next_update:
            self._target = self._pick_target(paddle, pucks, now)
            self._next_update = now + random.uniform(diff.reaction_min, diff.reaction_max)

        tx, ty = self._target
        dx = tx - paddle.x
        dy = ty - paddle.y
        dist = math.hypot(dx, dy)
        if dist < 8.0:
            return 0.0, 0.0, False
        nx, ny = dx / dist, dy / dist
        dash = self._want_dash(paddle, dist, fences, now)
        if dash:
            self._dash_cooldown_until = now + diff.dash_cooldown
        return nx, ny, dash

    def _want_dash(
        self,
        paddle: Paddle,
        dist: float,
        fences: list[Fence],
        now: float,
    ) -> bool:
        if now < self._dash_cooldown_until or dist < 72.0:
            return False
        diff = self.difficulty
        chance = diff.dash_chance
        if dist > 115.0:
            chance += 0.08

        own_block = self._trail_blocks_path(
            paddle.x, paddle.y, self._target[0], self._target[1], paddle.player, fences,
        )
        opp_walls = self._opponent_walls_between(
            paddle.x, paddle.y, self._target[0], self._target[1], paddle.player, fences,
        )

        if own_block:
            chance += 0.10
        if opp_walls >= 2:
            # 壁貫通コンボは人間でも難しい — CPUも完璧に決めない
            chance *= max(0.35, 1.0 - 0.14 * (opp_walls - 1))
            if random.random() < 0.18 + 0.10 * opp_walls:
                return False

        return random.random() < min(0.82, chance)

    def _opponent_walls_between(
        self,
        x1: float, y1: float,
        x2: float, y2: float,
        player: int,
        fences: list[Fence],
    ) -> int:
        count = 0
        for fence in fences:
            if fence.owner == player:
                continue
            if self._segments_cross(x1, y1, x2, y2, fence.x1, fence.y1, fence.x2, fence.y2):
                count += 1
        return count

    @staticmethod
    def _segments_cross(
        ax: float, ay: float, bx: float, by: float,
        cx: float, cy: float, dx: float, dy: float,
    ) -> bool:
        def orient(px: float, py: float, qx: float, qy: float, rx: float, ry: float) -> float:
            return (qy - py) * (rx - qx) - (qx - px) * (ry - qy)

        o1 = orient(ax, ay, bx, by, cx, cy)
        o2 = orient(ax, ay, bx, by, dx, dy)
        o3 = orient(cx, cy, dx, dy, ax, ay)
        o4 = orient(cx, cy, dx, dy, bx, by)
        return o1 * o2 < 0 and o3 * o4 < 0

    def _trail_blocks_path(
        self,
        x1: float, y1: float,
        x2: float, y2: float,
        owner: int,
        fences: list[Fence],
    ) -> bool:
        for fence in fences:
            if fence.owner != owner:
                continue
            if self._segments_cross(x1, y1, x2, y2, fence.x1, fence.y1, fence.x2, fence.y2):
                return True
        return False

    def _pick_target(
        self,
        paddle: Paddle,
        pucks: list[Puck],
        now: float,
    ) -> tuple[float, float]:
        diff = self.difficulty
        threat, threat_score = self._most_threatening_puck(pucks, paddle.player)
        if threat is not None and threat_score >= diff.threat_score_defend:
            return self._fence_defend_target(paddle, threat, now)

        puck = self._active_puck(pucks, paddle)
        return self._fence_attack_target(paddle, puck, now)

    def _jitter(self, x: float, y: float) -> tuple[float, float]:
        err = self.difficulty.aim_error
        return (
            x + random.uniform(-err, err),
            y + random.uniform(-err, err),
        )

    def _most_threatening_puck(self, pucks: list[Puck], player: int) -> tuple[Puck | None, float]:
        play = playable_rect()
        frame = arena_frame_rect()
        goal_top, goal_bottom = goal_bounds()
        best: Puck | None = None
        best_score = -1e9

        for puck in pucks:
            if player == 1:
                toward_goal = puck.vx
                dist_to_goal = frame.right - puck.x
            else:
                toward_goal = -puck.vx
                dist_to_goal = puck.x - frame.left

            if toward_goal <= 0:
                toward_goal = 5.0

            t_goal = dist_to_goal / toward_goal
            pred_y = puck.y + puck.vy * min(t_goal, 1.8)
            in_lane = goal_top - puck.radius <= pred_y <= goal_bottom + puck.radius

            score = toward_goal * 1.5 + 400.0 / max(dist_to_goal, 20.0)
            if in_lane:
                score += 900.0

            if score > best_score:
                best_score = score
                best = puck

        return best, best_score

    def _fence_defend_target(self, paddle: Paddle, puck: Puck, now: float) -> tuple[float, float]:
        play = playable_rect()
        frame = arena_frame_rect()
        r = paddle.radius(now)
        goal_top, goal_bottom = goal_bounds()
        lead = self.difficulty.intercept_lead

        if abs(puck.vx) > 40:
            t = max(0.0, (frame.right - puck.x) / max(puck.vx, 1.0))
            t = min(t, 1.0)
            intercept_x = puck.x + puck.vx * t * lead
            intercept_y = puck.y + puck.vy * t * lead
        else:
            intercept_x = puck.x + 55.0
            intercept_y = puck.y

        target_x = max(play.centerx, min(intercept_x + 55.0, play.right - r - 8))
        target_y = max(goal_top - 20, min(goal_bottom + 20, intercept_y))
        return self._jitter(target_x, target_y)

    def _fence_attack_target(self, paddle: Paddle, puck: Puck, now: float) -> tuple[float, float]:
        play = playable_rect()
        r = paddle.radius(now)
        goal_top, goal_bottom = goal_bounds()
        lead = self.difficulty.intercept_lead

        ahead_x = puck.x + puck.vx * (0.22 + lead * 0.2)
        ahead_y = puck.y + puck.vy * (0.22 + lead * 0.2)
        target_x = max(play.centerx + 20, min(ahead_x + 35, play.right - r - 6))
        target_y = max(goal_top - 16, min(goal_bottom + 16, ahead_y))
        return self._jitter(target_x, target_y)

    def _active_puck(self, pucks: list[Puck], paddle: Paddle) -> Puck:
        if len(pucks) == 1:
            return pucks[0]
        return min(pucks, key=lambda p: (p.x - paddle.x) ** 2 + (p.y - paddle.y) ** 2)
