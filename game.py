"""試合状態・スコア"""

import math
from enum import Enum, auto

import pygame

from constants import (
    COUNTDOWN_START,
    FENCE_HALF_WIDTH,
    FENCE_MIN_LENGTH,
    GOAL_RESET_DELAY,
    TRAIL_CENTER_BONUS,
    TRAIL_CENTER_ZONE_RATIO,
    TRAIL_GOAL_LIFETIME,
    TRAIL_GOAL_ZONE_RATIO,
    TRAIL_MAX_GAP,
    TRAIL_MIN_SPEED,
    TRAIL_SEGMENT_INTERVAL,
    TRAIL_SPAWN_COOLDOWN,
    TRAIL_WALL_LIFETIME,
    TRAIL_WALL_MAX_PER_PLAYER,
    WIN_SCORE,
)
from entities import Fence, Paddle, Puck, spawn_center_puck, table_rect
from effects import GoalCelebration, spawn_goal_celebration, update_goal_celebration
from physics import (
    clamp_paddle_to_table,
    resolve_paddle_paddle,
    resolve_puck_fence,
    resolve_puck_paddle,
    resolve_puck_puck,
    resolve_puck_wall,
)


class GameState(Enum):
    TITLE = auto()
    COUNTDOWN = auto()
    PLAYING = auto()
    RESULT = auto()
    PAUSE = auto()


class Match:
    def __init__(self, audio: "SoundManager | None" = None) -> None:
        self.audio = audio
        self.reset_match()

    def reset_match(self) -> None:
        rect = table_rect()
        self.paddles = [
            Paddle(player=0, x=rect.left + rect.width * 0.2, y=rect.centery, last_dir=(1.0, 0.0), face_heading=0.0, face_heading_ready=True),
            Paddle(player=1, x=rect.right - rect.width * 0.2, y=rect.centery, last_dir=(-1.0, 0.0), face_heading=math.pi, face_heading_ready=True),
        ]
        for paddle in self.paddles:
            paddle.trail_x = paddle.x
            paddle.trail_y = paddle.y
        self.pucks: list[Puck] = []
        self.fences: list[Fence] = []
        self.scores = [0, 0]
        self.state = GameState.TITLE
        self.countdown = COUNTDOWN_START
        self.countdown_timer = 0.0
        self.match_time = 0.0
        self.winner: int | None = None
        self.announce = ""
        self.announce_timer = 0.0
        self.pucks_frozen = True
        self.goal_reset_timer = 0.0
        self.vs_cpu = False
        self._pre_pause_state: GameState | None = None
        self.goal_fx: GoalCelebration | None = None

    def start_from_title(self, vs_cpu: bool = False) -> None:
        self.reset_match()
        self.vs_cpu = vs_cpu
        self.state = GameState.COUNTDOWN
        self.countdown = COUNTDOWN_START
        self.countdown_timer = 1.0
        self.pucks = [spawn_center_puck()]
        self.pucks_frozen = True

    def handle_input(
        self,
        keys: pygame.key.ScancodeWrapper,
        dt: float,
        now: float,
        cpu_ai: "CPUAI | None" = None,
    ) -> None:
        if self.state == GameState.TITLE:
            return
        if self.state == GameState.RESULT:
            return

        controls = [
            {pygame.K_a: (-1, 0), pygame.K_d: (1, 0), pygame.K_w: (0, -1), pygame.K_s: (0, 1)},
            {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)},
        ]
        dash_keys = [pygame.K_LSHIFT, pygame.K_RSHIFT]
        for i, paddle in enumerate(self.paddles):
            dx = dy = 0.0
            if self.vs_cpu and i == 1 and cpu_ai is not None:
                dx, dy, dash = cpu_ai.decide(
                    paddle, self.paddles[0], self.pucks, self.fences, now, self.pucks_frozen,
                )
                paddle.is_dashing = dash and bool(dx or dy)
            else:
                for key, (kx, ky) in controls[i].items():
                    if keys[key]:
                        dx += kx
                        dy += ky
                if dx or dy:
                    length = math.hypot(dx, dy)
                    dx /= length
                    dy /= length
                paddle.is_dashing = bool(dx or dy) and keys[dash_keys[i]]

            speed = paddle.speed(now, paddle.is_dashing)
            if dx or dy:
                paddle.last_dir = (dx, dy)
            paddle.vx = dx * speed
            paddle.vy = dy * speed
            paddle.x += paddle.vx * dt
            paddle.y += paddle.vy * dt
            paddle.update_face_heading(dt)
            clamp_paddle_to_table(paddle, now)

        resolve_paddle_paddle(self.paddles[0], self.paddles[1], now)
        if self.state == GameState.COUNTDOWN or self.pucks_frozen:
            self._sync_paddle_trail_anchors()
        self._update_trail_walls(now)

    def _goal_zone_depth(self, paddle: Paddle, x: float) -> float:
        """自ゴールに近いほど 1.0（ゴールライン=最深）"""
        rect = table_rect()
        margin = rect.width * TRAIL_GOAL_ZONE_RATIO
        if margin < 1.0:
            return 0.0
        if paddle.player == 0:
            if x >= rect.left + margin:
                return 0.0
            return min(1.0, (rect.left + margin - x) / margin)
        if x <= rect.right - margin:
            return 0.0
        return min(1.0, (x - (rect.right - margin)) / margin)

    def _center_line_depth(self, x: float) -> float:
        rect = table_rect()
        margin = rect.width * TRAIL_CENTER_ZONE_RATIO
        if margin < 1.0:
            return 0.0
        dist = abs(x - rect.centerx)
        if dist >= margin:
            return 0.0
        return 1.0 - dist / margin

    def _center_lifetime_bonus(self, x1: float, y1: float, x2: float, y2: float) -> float:
        depth = max(
            self._center_line_depth(x1),
            self._center_line_depth(x2),
            self._center_line_depth((x1 + x2) * 0.5),
        )
        return TRAIL_CENTER_BONUS * depth

    def _trail_lifetime(self, paddle: Paddle, x1: float, y1: float, x2: float, y2: float) -> float:
        depth = max(
            self._goal_zone_depth(paddle, x1),
            self._goal_zone_depth(paddle, x2),
            self._goal_zone_depth(paddle, (x1 + x2) * 0.5),
        )
        if depth <= 0.0:
            base = TRAIL_WALL_LIFETIME
        else:
            base = TRAIL_WALL_LIFETIME + (TRAIL_GOAL_LIFETIME - TRAIL_WALL_LIFETIME) * depth
        return base + self._center_lifetime_bonus(x1, y1, x2, y2)

    def _sync_paddle_trail_anchors(self) -> None:
        """軌跡の始点を現在位置に合わせる（カウントダウン移動後の誤スポーン防止）"""
        for paddle in self.paddles:
            paddle.trail_x = paddle.x
            paddle.trail_y = paddle.y

    def _spawn_trail_segment(
        self,
        paddle: Paddle,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        now: float,
    ) -> bool:
        if math.hypot(x2 - x1, y2 - y1) < FENCE_MIN_LENGTH:
            return False
        if now < paddle.trail_spawn_until:
            return False
        lifetime = self._trail_lifetime(paddle, x1, y1, x2, y2)
        owner_fences = [f for f in self.fences if f.owner == paddle.player]
        while len(owner_fences) >= TRAIL_WALL_MAX_PER_PLAYER:
            oldest = min(owner_fences, key=lambda f: f.created_at)
            self.fences.remove(oldest)
            owner_fences.remove(oldest)
        self.fences.append(Fence(
            owner=paddle.player,
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            until=now + lifetime,
            created_at=now,
            half_width=FENCE_HALF_WIDTH,
        ))
        paddle.trail_spawn_until = now + TRAIL_SPAWN_COOLDOWN
        if self.audio is not None:
            self.audio.play_trail_crawl(now)
        return True

    def _update_trail_walls(self, now: float) -> None:
        if self.state != GameState.PLAYING or self.pucks_frozen:
            return

        for paddle in self.paddles:
            if paddle.is_dashing:
                paddle.trail_x = paddle.x
                paddle.trail_y = paddle.y
                continue

            speed = math.hypot(paddle.vx, paddle.vy)
            if speed < TRAIL_MIN_SPEED:
                paddle.trail_x = paddle.x
                paddle.trail_y = paddle.y
                continue

            dx = paddle.x - paddle.trail_x
            dy = paddle.y - paddle.trail_y
            dist = math.hypot(dx, dy)

            if dist >= TRAIL_MAX_GAP:
                paddle.trail_x = paddle.x
                paddle.trail_y = paddle.y
                continue

            if dist >= TRAIL_SEGMENT_INTERVAL and now >= paddle.trail_spawn_until:
                if self._spawn_trail_segment(
                    paddle, paddle.trail_x, paddle.trail_y, paddle.x, paddle.y, now,
                ):
                    paddle.trail_x = paddle.x
                    paddle.trail_y = paddle.y

    def update(self, dt: float, now: float) -> None:
        if self.state == GameState.TITLE:
            return
        if self.state == GameState.PAUSE:
            return
        if self.state == GameState.RESULT:
            return

        if self.state == GameState.COUNTDOWN:
            self.countdown_timer -= dt
            if self.countdown_timer <= 0:
                self.countdown -= 1
                if self.countdown <= 0:
                    self.state = GameState.PLAYING
                    self.pucks_frozen = False
                    self.match_time = 0.0
                    self._sync_paddle_trail_anchors()
                    if self.audio is not None:
                        self.audio.play_start()
                else:
                    self.countdown_timer = 1.0
                    if self.audio is not None:
                        self.audio.play_countdown()
            return

        # PLAYING
        self.match_time += dt
        self.goal_fx = update_goal_celebration(self.goal_fx, dt)
        if self.announce_timer > 0:
            self.announce_timer -= dt

        if self.goal_reset_timer > 0:
            self.goal_reset_timer -= dt
            if self.goal_reset_timer <= 0:
                self.pucks = [spawn_center_puck()]
                self.pucks_frozen = False

        self._update_fences(now)

        if not self.pucks_frozen:
            for puck in self.pucks:
                if puck.carried_by >= 0:
                    continue
                puck.x += puck.vx * dt
                puck.y += puck.vy * dt

            for puck in self.pucks:
                if puck.carried_by >= 0:
                    continue
                for paddle in self.paddles:
                    if resolve_puck_paddle(puck, paddle, now):
                        if self.audio is not None:
                            self.audio.play_wall_bounce(puck.wall_bounces, now)

            fences_to_remove: list[Fence] = []
            for puck in self.pucks:
                if puck.carried_by >= 0:
                    continue
                for fence in self.fences:
                    if resolve_puck_fence(puck, fence, now):
                        fences_to_remove.append(fence)
                        if self.audio is not None:
                            self.audio.play_wall_bounce(puck.wall_bounces, now)
                            self.audio.play_rally_milestone(puck.wall_bounces)
            seen: set[int] = set()
            for fence in fences_to_remove:
                fid = id(fence)
                if fid in seen:
                    continue
                seen.add(fid)
                if fence in self.fences:
                    self.fences.remove(fence)

            for i in range(len(self.pucks)):
                if self.pucks[i].carried_by >= 0:
                    continue
                for j in range(i + 1, len(self.pucks)):
                    if self.pucks[j].carried_by >= 0:
                        continue
                    resolve_puck_puck(self.pucks[i], self.pucks[j])

            scored_events = []
            for puck in list(self.pucks):
                side, bounced = resolve_puck_wall(puck)
                if bounced and self.audio is not None:
                    self.audio.play_wall_bounce(puck.wall_bounces, now)
                    self.audio.play_rally_milestone(puck.wall_bounces)
                if side is not None:
                    scored_events.append((side, puck))

            if scored_events:
                self._register_goals(scored_events)

        self._check_win()

    def _update_fences(self, now: float) -> None:
        for fence in list(self.fences):
            if now >= fence.until:
                self.fences.remove(fence)

    def _register_goals(self, scored_events: list[tuple[int, Puck]]) -> None:
        """同一フレーム・同一ゴールへの入りは1回だけカウント"""
        batches: dict[int, list[Puck]] = {}
        for conceded_side, puck in scored_events:
            batches.setdefault(conceded_side, []).append(puck)

        for conceded_side, pucks in batches.items():
            scorer = 1 - conceded_side
            points = 1

            self.scores[scorer] += points
            self._show_announce(f"葉っぱゲット！ +{points}", 1.5)
            rect = table_rect()
            goal_x = rect.left if conceded_side == 0 else rect.right
            goal_y = pucks[0].y if pucks else rect.centery
            self.goal_fx = spawn_goal_celebration(goal_x, goal_y, scorer, points)
            if self.audio is not None:
                self.audio.play_goal()

            for puck in pucks:
                if puck in self.pucks:
                    self.pucks.remove(puck)

            for puck in self.pucks:
                puck.wall_bounces = 0
                puck.grind_started_at = -1.0
                puck.grind_paddle = -1
                puck.grind_escape_x = 0.0

            self.fences.clear()
            for paddle in self.paddles:
                paddle.trail_x = paddle.x
                paddle.trail_y = paddle.y
                paddle.trail_spawn_until = 0.0

            self.pucks_frozen = True
            self.goal_reset_timer = GOAL_RESET_DELAY

    def _check_win(self) -> None:
        if self.state != GameState.PLAYING:
            return
        for i in range(2):
            if self.scores[i] >= WIN_SCORE:
                self.winner = i
                self.state = GameState.RESULT
                return

    def _show_announce(self, text: str, duration: float) -> None:
        self.announce = text
        self.announce_timer = duration

    def toggle_pause(self) -> None:
        if self.state == GameState.PAUSE:
            self.state = self._pre_pause_state or GameState.PLAYING
            self._pre_pause_state = None
        elif self.state in (GameState.PLAYING, GameState.COUNTDOWN):
            self._pre_pause_state = self.state
            self.state = GameState.PAUSE

    def back_to_title(self) -> None:
        self.reset_match()
