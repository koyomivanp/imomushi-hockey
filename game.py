"""試合状態・スコア"""

import math
from enum import Enum, auto

import pygame

from constants import (
    COUNTDOWN_START,
    PREP_DARKEN_DURATION,
    PREP_REVEAL_DURATION,
    TIPS_DISPLAY_DURATION,
    TIPS_FADE_IN_DURATION,
    TIPS_FADE_OUT_DURATION,
    FENCE_BREACH_FLASH_DURATION,
    FENCE_HALF_WIDTH,
    FENCE_MIN_LENGTH,
    FACEOFF_LIGHT_DURATION,
    GOAL_FIREFLY_DURATION,
    GOAL_RESET_DELAY,
    GOAL_SIDE_FLASH_DURATION,
    GOAL_WALL_PULSE_DURATION,
    RESULT_CARD_IN_DURATION,
    RESULT_CELEBRATE_DURATION,
    RESULT_DIM_DURATION,
    SCORE_POP_DURATION,
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
from match_prep import PrepPhase
from menu_selection import SelectionHighlight
from result_flow import ResultPhase, ease_in_out, normalized_progress
from entities import Fence, Paddle, Puck, arena_frame_rect, playable_rect, spawn_center_puck, table_rect
from arena_assets import ArenaLightingState
from effects import (
    BreachSpark,
    GoalCelebration,
    PuckResetAnim,
    goal_mouth_anchor,
    spawn_breach_sparks,
    spawn_goal_celebration,
    update_breach_sparks,
    update_goal_celebration,
)
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
    CPU_DIFF = auto()
    PREP = auto()
    COUNTDOWN = auto()
    PLAYING = auto()
    RESULT = auto()
    PAUSE = auto()


class Match:
    def __init__(self, audio: "SoundManager | None" = None) -> None:
        self.audio = audio
        self.reset_match()

    def _init_paddles(self) -> None:
        play = playable_rect()
        self.paddles = [
            Paddle(player=0, x=play.left + play.width * 0.2, y=play.centery, last_dir=(1.0, 0.0), face_heading=0.0, face_heading_ready=True, prev_x=play.left + play.width * 0.2, prev_y=play.centery),
            Paddle(player=1, x=play.right - play.width * 0.2, y=play.centery, last_dir=(-1.0, 0.0), face_heading=math.pi, face_heading_ready=True, prev_x=play.right - play.width * 0.2, prev_y=play.centery),
        ]
        for paddle in self.paddles:
            paddle.trail_x = paddle.x
            paddle.trail_y = paddle.y

    def reset_match(self) -> None:
        self._init_paddles()
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
        self.breach_sparks: list[BreachSpark] = []
        self.score_pop_player: int | None = None
        self.score_pop_timer: float = 0.0
        self.puck_reset_anim: PuckResetAnim | None = None
        self.last_goal_conceded_side: int | None = None
        self.arena_lighting = ArenaLightingState.inactive()
        self.title_menu_index = 0
        self.title_menu_sel = SelectionHighlight(0)
        self.cpu_diff_index = 1
        self.cpu_diff_sel = SelectionHighlight(1)
        self.cpu_diff_morph = 0.0
        self.cpu_diff_exiting = False
        self.prep_from_state: GameState | None = None
        self.prep_handoff_morph = 1.0
        self.prep_handoff_menu_index = 0
        self.tips_text = ""
        self.tips_timer = 0.0
        self.fade_progress = 0.0
        self.prep_phase = PrepPhase.DARKEN
        self.prep_phase_progress = 0.0
        self.tips_alpha = 0.0
        self.prep_darkness = 0.0
        self.prep_reveal = 0.0
        self.tips_hold_timer = 0.0
        self.result_phase = ResultPhase.HOLD
        self.result_phase_progress = 0.0
        self.result_dimness = 0.0
        self.result_card_alpha = 0.0

    def begin_from_menu(self, vs_cpu: bool) -> None:
        """タイトルメニューから試合準備へ"""
        self._init_paddles()
        self.pucks = []
        self.fences = []
        self.scores = [0, 0]
        self.vs_cpu = vs_cpu
        self.winner = None
        self.announce = ""
        self.announce_timer = 0.0
        self.pucks_frozen = True
        self.goal_reset_timer = 0.0
        self.goal_fx = None
        self.breach_sparks = []
        self.score_pop_player = None
        self.score_pop_timer = 0.0
        self.puck_reset_anim = None
        self.last_goal_conceded_side = None
        self.arena_lighting = ArenaLightingState.inactive()
        self.tips_text = ""
        self.tips_timer = 0.0
        self.fade_progress = 0.0
        self.prep_phase = PrepPhase.DARKEN
        self.prep_phase_progress = 0.0
        self.tips_alpha = 0.0
        self.prep_darkness = 0.0
        self.prep_reveal = 0.0
        self.tips_hold_timer = 0.0
        self.result_phase = ResultPhase.HOLD
        self.result_phase_progress = 0.0
        self.result_dimness = 0.0
        self.result_card_alpha = 0.0
        if vs_cpu:
            self.cpu_diff_morph = 0.0
            self.cpu_diff_sel.snap_to(self.cpu_diff_index)
            self.state = GameState.CPU_DIFF
        else:
            self._begin_match_prep_from(GameState.TITLE, menu_index=1)

    def _begin_match_prep_from(self, from_state: GameState, *, menu_index: int = 0) -> None:
        self.prep_from_state = from_state
        self.prep_handoff_morph = self.cpu_diff_morph if from_state == GameState.CPU_DIFF else 1.0
        self.prep_handoff_menu_index = menu_index
        self.start_match_prep()

    def title_menu_sel_strengths(self) -> tuple[float, float, float]:
        return tuple(self.title_menu_sel.strength(i) for i in range(3))

    def cpu_diff_sel_strengths(self) -> tuple[float, float, float]:
        return tuple(self.cpu_diff_sel.strength(i) for i in range(3))

    def start_match_prep(self) -> None:
        from screens import pick_random_tip

        self.tips_text = pick_random_tip(self.vs_cpu)
        self.prep_phase = PrepPhase.DARKEN
        self.prep_phase_progress = 0.0
        self.tips_alpha = 0.0
        self.prep_darkness = 0.0
        self.prep_reveal = 0.0
        self.tips_hold_timer = 0.0
        self.state = GameState.PREP

    def start_fade_to_tips(self) -> None:
        self._begin_match_prep_from(GameState.CPU_DIFF)

    def skip_tips_display(self) -> None:
        """TIPS 表示フェーズのみスキップ → 暗転のままコート明転"""
        if self.state != GameState.PREP:
            return
        if self.prep_phase not in (
            PrepPhase.TIPS_IN,
            PrepPhase.TIPS_HOLD,
            PrepPhase.TIPS_OUT,
        ):
            return
        self._begin_prep_reveal()

    def _prepare_countdown(self) -> None:
        self.countdown = COUNTDOWN_START
        self.countdown_timer = 1.0
        self.pucks = [spawn_center_puck()]
        self.pucks_frozen = True

    def _begin_prep_reveal(self) -> None:
        self._prepare_countdown()
        self.prep_phase = PrepPhase.REVEAL
        self.prep_phase_progress = 0.0
        self.tips_alpha = 0.0
        self.prep_reveal = 0.0
        self.tips_hold_timer = 0.0

    def _finish_match_prep(self) -> None:
        self.prep_reveal = 1.0
        self.prep_darkness = 0.0
        self.prep_from_state = None
        self.state = GameState.COUNTDOWN

    def enter_countdown(self) -> None:
        self._prepare_countdown()
        self.state = GameState.COUNTDOWN

    def _begin_tips(self) -> None:
        self.start_match_prep()

    def start_rematch(self, vs_cpu: bool) -> None:
        self.begin_from_menu(vs_cpu)

    def begin_cpu_diff_exit(self) -> None:
        if self.state != GameState.CPU_DIFF or self.cpu_diff_exiting:
            return
        self.cpu_diff_exiting = True

    def cpu_diff_ready(self) -> bool:
        return self.cpu_diff_morph >= 1.0 and not self.cpu_diff_exiting

    def handle_input(
        self,
        keys: pygame.key.ScancodeWrapper,
        dt: float,
        now: float,
        cpu_ai: "CPUAI | None" = None,
    ) -> None:
        if self.state == GameState.TITLE:
            return
        if self.state in (GameState.CPU_DIFF, GameState.PREP):
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
                if self.vs_cpu and i == 0:
                    paddle.is_dashing = bool(dx or dy) and (
                        keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
                    )
                else:
                    paddle.is_dashing = bool(dx or dy) and keys[dash_keys[i]]

            speed = paddle.speed(now, paddle.is_dashing)
            if dx or dy:
                paddle.last_dir = (dx, dy)
            paddle.prev_x = paddle.x
            paddle.prev_y = paddle.y
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
        play = playable_rect()
        frame = arena_frame_rect()
        margin = play.width * TRAIL_GOAL_ZONE_RATIO
        if margin < 1.0:
            return 0.0
        if paddle.player == 0:
            if x >= frame.left + margin:
                return 0.0
            return min(1.0, (frame.left + margin - x) / margin)
        if x <= frame.right - margin:
            return 0.0
        return min(1.0, (x - (frame.right - margin)) / margin)

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

    def _advance_prep_phase(self, next_phase: PrepPhase) -> None:
        self.prep_phase = next_phase
        self.prep_phase_progress = 0.0

    def _update_prep(self, dt: float) -> None:
        from match_prep import ease_in_out, normalized_progress

        phase = self.prep_phase
        self.prep_phase_progress += dt
        t = normalized_progress(phase, self.prep_phase_progress)

        if phase == PrepPhase.DARKEN:
            self.prep_darkness = ease_in_out(t)
            self.prep_reveal = 0.0
            self.tips_alpha = 0.0
            if self.prep_phase_progress >= PREP_DARKEN_DURATION:
                self._advance_prep_phase(PrepPhase.TIPS_IN)
            return

        if phase == PrepPhase.TIPS_IN:
            self.prep_darkness = 1.0
            self.tips_alpha = ease_in_out(t)
            if self.prep_phase_progress >= TIPS_FADE_IN_DURATION:
                self.tips_alpha = 1.0
                self._advance_prep_phase(PrepPhase.TIPS_HOLD)
                self.tips_hold_timer = TIPS_DISPLAY_DURATION
            return

        if phase == PrepPhase.TIPS_HOLD:
            self.prep_darkness = 1.0
            self.tips_alpha = 1.0
            self.tips_hold_timer -= dt
            if self.tips_hold_timer <= 0.0:
                self._advance_prep_phase(PrepPhase.TIPS_OUT)
            return

        if phase == PrepPhase.TIPS_OUT:
            self.prep_darkness = 1.0
            self.tips_alpha = max(0.0, 1.0 - ease_in_out(t))
            if self.prep_phase_progress >= TIPS_FADE_OUT_DURATION:
                self._begin_prep_reveal()
            return

        if phase == PrepPhase.REVEAL:
            self.prep_darkness = 1.0
            self.tips_alpha = 0.0
            self.prep_reveal = ease_in_out(t)
            if self.prep_phase_progress >= PREP_REVEAL_DURATION:
                self._finish_match_prep()

    def update(self, dt: float, now: float) -> None:
        if self.state == GameState.TITLE:
            self.title_menu_sel.update(dt, self.title_menu_index)
            return
        if self.state == GameState.CPU_DIFF:
            from cpu_diff_morph import MORPH_DURATION, update_morph_progress

            if self.cpu_diff_exiting:
                self.cpu_diff_morph = max(0.0, self.cpu_diff_morph - dt / MORPH_DURATION)
                if self.cpu_diff_morph <= 0.0:
                    self.cpu_diff_exiting = False
                    self.reset_match()
                return
            if self.cpu_diff_morph < 1.0:
                self.cpu_diff_morph = update_morph_progress(self.cpu_diff_morph, dt)
            if self.cpu_diff_ready():
                self.cpu_diff_sel.update(dt, self.cpu_diff_index)
            return
        if self.state == GameState.PREP:
            self._update_prep(dt)
            return
        if self.state == GameState.PAUSE:
            return
        if self.state == GameState.RESULT:
            self._update_result(dt)
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
        self.breach_sparks = update_breach_sparks(self.breach_sparks, dt)
        if self.announce_timer > 0:
            self.announce_timer -= dt
        if self.score_pop_timer > 0:
            self.score_pop_timer -= dt
            if self.score_pop_timer <= 0:
                self.score_pop_player = None
        self._update_arena_lighting(dt)

        if self.puck_reset_anim is not None:
            if self.puck_reset_anim.update(dt):
                play = playable_rect()
                self.pucks = [spawn_center_puck()]
                self.pucks_frozen = False
                self.puck_reset_anim = None
                self.arena_lighting.faceoff_pulse_timer = FACEOFF_LIGHT_DURATION
        elif self.goal_reset_timer > 0:
            self.goal_reset_timer -= dt
            if self.goal_reset_timer <= 0:
                self._begin_puck_reset_anim()

        self._update_fences(now)

        if not self.pucks_frozen:
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
                puck.prev_x = puck.x
                puck.prev_y = puck.y
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
                    hit, breached = resolve_puck_fence(puck, fence, now)
                    if hit:
                        fences_to_remove.append(fence)
                        if breached:
                            puck.breach_flash_until = now + FENCE_BREACH_FLASH_DURATION
                            self.breach_sparks.extend(
                                spawn_breach_sparks(puck.x, puck.y, puck.vx, puck.vy),
                            )
                            if self.audio is not None:
                                self.audio.play_fence_breach(now)
                        elif self.audio is not None:
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

    def _update_arena_lighting(self, dt: float) -> None:
        s0, s1 = self.scores
        self.arena_lighting.near_win = max(s0, s1) >= WIN_SCORE - 1
        if self.arena_lighting.goal_flash_timer > 0:
            self.arena_lighting.goal_flash_timer = max(0.0, self.arena_lighting.goal_flash_timer - dt)
            if self.arena_lighting.goal_flash_timer <= 0:
                self.arena_lighting.goal_flash_side = None
        if self.arena_lighting.faceoff_pulse_timer > 0:
            self.arena_lighting.faceoff_pulse_timer = max(0.0, self.arena_lighting.faceoff_pulse_timer - dt)

    def _begin_puck_reset_anim(self) -> None:
        play = playable_rect()
        if self.last_goal_conceded_side is not None:
            start_x, start_y = goal_mouth_anchor(self.last_goal_conceded_side)
        else:
            start_x, start_y = play.centerx, play.centery
        self.puck_reset_anim = PuckResetAnim(
            start_x=start_x,
            start_y=start_y,
            end_x=play.centerx,
            end_y=play.centery,
        )
        self.last_goal_conceded_side = None

    def _register_goals(self, scored_events: list[tuple[int, Puck]]) -> None:
        """同一フレーム・同一ゴールへの入りは1回だけカウント"""
        batches: dict[int, list[Puck]] = {}
        for conceded_side, puck in scored_events:
            batches.setdefault(conceded_side, []).append(puck)

        for conceded_side, pucks in batches.items():
            scorer = 1 - conceded_side
            points = 1

            self.scores[scorer] += points
            self.score_pop_player = scorer
            self.score_pop_timer = SCORE_POP_DURATION
            self.goal_fx = spawn_goal_celebration(conceded_side, scorer, points)
            self.last_goal_conceded_side = conceded_side
            self.arena_lighting.goal_flash_side = conceded_side
            self.arena_lighting.goal_flash_scorer = scorer
            self.arena_lighting.goal_flash_timer = max(
                GOAL_SIDE_FLASH_DURATION,
                GOAL_FIREFLY_DURATION,
                GOAL_WALL_PULSE_DURATION,
            )
            if self.audio is not None:
                self.audio.play_goal()
                self.audio.play_score_tick()

            for puck in pucks:
                if puck in self.pucks:
                    self.pucks.remove(puck)

            for puck in self.pucks:
                puck.wall_bounces = 0
                puck.grind_started_at = -1.0
                puck.grind_paddle = -1
                puck.grind_escape_x = 0.0
                puck.dash_breach_until = 0.0
                puck.breach_flash_until = 0.0
                puck.prev_x = puck.x
                puck.prev_y = puck.y

            self.fences.clear()
            for paddle in self.paddles:
                paddle.trail_x = paddle.x
                paddle.trail_y = paddle.y
                paddle.trail_spawn_until = 0.0

            self.pucks_frozen = True
            self.goal_reset_timer = GOAL_RESET_DELAY

    def _advance_result_phase(self, next_phase: ResultPhase) -> None:
        self.result_phase = next_phase
        self.result_phase_progress = 0.0

    def _update_result(self, dt: float) -> None:
        self.goal_fx = update_goal_celebration(self.goal_fx, dt)
        self.breach_sparks = update_breach_sparks(self.breach_sparks, dt)
        if self.score_pop_timer > 0:
            self.score_pop_timer -= dt
            if self.score_pop_timer <= 0:
                self.score_pop_player = None
        self._update_arena_lighting(dt)

        phase = self.result_phase
        self.result_phase_progress += dt
        t = normalized_progress(phase, self.result_phase_progress)

        if phase == ResultPhase.CELEBRATE:
            self.result_dimness = 0.0
            self.result_card_alpha = 0.0
            if self.result_phase_progress >= RESULT_CELEBRATE_DURATION:
                self._advance_result_phase(ResultPhase.DIM)
            return

        if phase == ResultPhase.DIM:
            self.result_dimness = ease_in_out(t)
            self.result_card_alpha = 0.0
            if self.result_phase_progress >= RESULT_DIM_DURATION:
                self.result_dimness = 1.0
                self._advance_result_phase(ResultPhase.CARD_IN)
                if self.audio is not None:
                    self.audio.play_result_card()
            return

        if phase == ResultPhase.CARD_IN:
            self.result_dimness = 1.0
            self.result_card_alpha = ease_in_out(t)
            if self.result_phase_progress >= RESULT_CARD_IN_DURATION:
                self.result_card_alpha = 1.0
                self._advance_result_phase(ResultPhase.HOLD)
            return

        self.result_dimness = 1.0
        self.result_card_alpha = 1.0

    def _check_win(self) -> None:
        if self.state != GameState.PLAYING:
            return
        for i in range(2):
            if self.scores[i] >= WIN_SCORE:
                self.winner = i
                self.goal_reset_timer = 0.0
                self.puck_reset_anim = None
                self.result_phase = ResultPhase.CELEBRATE
                self.result_phase_progress = 0.0
                self.result_dimness = 0.0
                self.result_card_alpha = 0.0
                self.state = GameState.RESULT
                if self.audio is not None:
                    if self.vs_cpu and i == 1:
                        self.audio.play_defeat()
                    else:
                        self.audio.play_victory()
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
