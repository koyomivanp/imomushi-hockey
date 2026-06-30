"""試合状態・スコア"""

import math
from enum import Enum, auto

import pygame

from constants import (
    COUNTDOWN_START,
    FENCE_HALF_WIDTH,
    FENCE_MIN_LENGTH,
    GOAL_RESET_DELAY,
    ITEM_FIRST_SPAWN,
    ITEMS_ENABLED,
    ITEM_SPAWN_INTERVAL,
    MAX_ITEMS_ON_FIELD,
    MAX_PUCKS,
    PUCK_AUTO_SPAWN_ENABLED,
    PUCK_AUTO_SPAWN_INTERVAL,
    PUCK_AUTO_SPAWN_INTERVAL_MIN,
    PUCK_ESCALATION_TIME,
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
    WIND_ACCEL,
)
from entities import (
    Bar,
    FallingItem,
    Fence,
    GuardSoldier,
    Paddle,
    PendingFence,
    Puck,
    RayShot,
    WindEffect,
    spawn_center_puck,
    spawn_extra_puck,
    table_rect,
    clamp_speed,
)
from effects import GoalCelebration, spawn_goal_celebration, update_goal_celebration
from items import (
    activate_pending_fence,
    apply_item,
    fire_guard_ray,
    guard_fire_interval,
    spawn_falling_item,
    try_collect_item,
    update_ray_shot,
    wind_accel_for,
)
from physics import (
    clamp_paddle_to_table,
    resolve_paddle_paddle,
    resolve_puck_bar,
    resolve_puck_fence,
    resolve_puck_paddle,
    resolve_puck_puck,
    resolve_puck_wall,
    update_guard_soldier,
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
        self.items: list[FallingItem] = []
        self.assists: list[GuardSoldier] = []
        self.pending_fences: list[PendingFence] = []
        self.fences: list[Fence] = []
        self.winds: list[WindEffect] = []
        self.bars: list[Bar] = []
        self.rays: list[RayShot] = []
        self.scores = [0, 0]
        self.state = GameState.TITLE
        self.countdown = COUNTDOWN_START
        self.countdown_timer = 0.0
        self.match_time = 0.0
        self.next_puck_spawn = PUCK_AUTO_SPAWN_INTERVAL
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
                    paddle, self.paddles[0], self.pucks, self.items, self.fences, now, self.pucks_frozen,
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
            paddle.x += paddle.kb_vx * dt
            paddle.y += paddle.kb_vy * dt
            paddle.update_knockback(dt, now)
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

        if ITEMS_ENABLED:
            self._update_items(dt, now)
        self._update_pending_fences(now)
        self._update_fences(now)
        self._update_bars(now)
        self._update_auto_puck_spawn()
        self._update_assists(dt, now)
        self._update_rays(dt, now)

        if not self.pucks_frozen:
            self._apply_wind(dt, now)

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

            for puck in self.pucks:
                if puck.carried_by >= 0:
                    continue
                for bar in self.bars:
                    resolve_puck_bar(puck, bar, self.paddles[bar.owner], now)

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

    def _update_items(self, dt: float, now: float) -> None:
        if self.match_time >= self.next_item_spawn and len(self.items) < MAX_ITEMS_ON_FIELD:
            self.items.append(spawn_falling_item())
            self.next_item_spawn = self.match_time + ITEM_SPAWN_INTERVAL

        rect = table_rect()
        for item in list(self.items):
            item.x += item.vx * dt
            item.y += item.vy * dt
            r = item.radius
            if (
                item.x + r < rect.left
                or item.x - r > rect.right
                or item.y + r < rect.top
                or item.y - r > rect.bottom
            ):
                self.items.remove(item)
                continue
            owner = try_collect_item(item, self.paddles, now)
            if owner is not None:
                label = apply_item(
                    item.kind, owner, self.paddles, self.pucks,
                    self.assists, self.pending_fences, self.fences, self.winds, self.bars,
                    now,
                )
                self._show_announce(label, 1.2)
                self.items.remove(item)

    def _update_pending_fences(self, now: float) -> None:
        for pending in list(self.pending_fences):
            if now < pending.activate_at:
                continue
            paddle = self.paddles[pending.owner]
            lv = self.paddles[pending.owner].stack_level("fence")
            self.fences.append(activate_pending_fence(pending, paddle, now, level=max(1, lv)))
            self.pending_fences.remove(pending)

    def _update_fences(self, now: float) -> None:
        for fence in list(self.fences):
            if now >= fence.until:
                self.fences.remove(fence)

    def _update_bars(self, now: float) -> None:
        for bar in list(self.bars):
            if now >= bar.until:
                self.bars.remove(bar)

    def _apply_wind(self, dt: float, now: float) -> None:
        for wind in list(self.winds):
            if now >= wind.until:
                self.winds.remove(wind)
        if not self.winds:
            return
        ax = 0.0
        for wind in self.winds:
            wa = wind_accel_for(wind)
            ax += wa if wind.owner == 0 else -wa
        for puck in self.pucks:
            puck.vx += ax * dt
            puck.vx, puck.vy = clamp_speed(puck.vx, puck.vy)

    def _puck_spawn_interval(self) -> float:
        t = min(1.0, self.match_time / PUCK_ESCALATION_TIME)
        return (
            PUCK_AUTO_SPAWN_INTERVAL
            + (PUCK_AUTO_SPAWN_INTERVAL_MIN - PUCK_AUTO_SPAWN_INTERVAL) * t
        )

    def _update_auto_puck_spawn(self) -> None:
        if not PUCK_AUTO_SPAWN_ENABLED:
            return
        if self.state != GameState.PLAYING or self.pucks_frozen:
            return
        if self.match_time < self.next_puck_spawn:
            return
        if len(self.pucks) < MAX_PUCKS:
            self.pucks.append(spawn_extra_puck())
            self._show_announce("PUCK +1", 0.9)
        self.next_puck_spawn = self.match_time + self._puck_spawn_interval()

    def _update_assists(self, dt: float, now: float) -> None:
        for guard in list(self.assists):
            if now >= guard.until:
                self.assists.remove(guard)
                continue
            update_guard_soldier(guard, dt, now, self.pucks)
            if guard.state == "guarding" and now >= guard.ray_next_fire:
                shot = fire_guard_ray(guard, self.pucks)
                if shot is not None:
                    self.rays.append(shot)
                guard.ray_next_fire = now + guard_fire_interval(guard.level)

    def _update_rays(self, dt: float, now: float) -> None:
        for shot in list(self.rays):
            if update_ray_shot(shot, dt, self.pucks, self.paddles, self.bars, now):
                self.rays.remove(shot)

    def _goal_points(self, conceded_side: int, puck: Puck) -> tuple[int, int]:
        """返値: (得点者, 点数)"""
        return 1 - conceded_side, 1

    def _register_goals(self, scored_events: list[tuple[int, Puck]]) -> None:
        """同一フレーム・同一ゴールへの入りは1回だけカウント"""
        batches: dict[int, list[Puck]] = {}
        for conceded_side, puck in scored_events:
            batches.setdefault(conceded_side, []).append(puck)

        for conceded_side, pucks in batches.items():
            best_scorer = 1 - conceded_side
            best_points = 0
            for puck in pucks:
                scorer, points = self._goal_points(conceded_side, puck)
                if points > best_points:
                    best_points = points
                    best_scorer = scorer

            if best_points > 0:
                self.scores[best_scorer] += best_points
                self._show_announce(f"葉っぱゲット！ +{best_points}", 1.5)
                rect = table_rect()
                goal_x = rect.left if conceded_side == 0 else rect.right
                goal_y = pucks[0].y if pucks else rect.centery
                self.goal_fx = spawn_goal_celebration(goal_x, goal_y, best_scorer, best_points)
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
