"""スマホ版エントリ — 縦画面・タッチ操作（Web 版ではビルド時に main.py として配置）"""

import asyncio
import math

import pygame

import tuning

tuning.use_mobile_scale()  # 当たり判定と見た目の寸法をスマホ用に（PC版は変えない）

from ai import CPUAI, CPU_DIFFICULTY_ORDER  # noqa: E402
from audio import SoundManager  # noqa: E402
from constants import (  # noqa: E402
    FPS,
    GAME_TITLE,
    MAX_FRAME_DT,
    MOBILE_H,
    MOBILE_HITSTOP_DURATION,
    MOBILE_SHAKE_AMPLITUDE,
    MOBILE_SHAKE_DURATION,
    MOBILE_STRONG_HIT_GAIN,
    MOBILE_STRONG_HIT_SPEED,
    MOBILE_W,
    SOUND_ENABLED,
)
from game import GameState, Match  # noqa: E402
from mobile_fx import MobileFX, VictoryButterfly  # noqa: E402
from mobile_view import (  # noqa: E402
    draw_countdown,
    draw_help,
    draw_match,
    draw_pause,
    draw_result,
    draw_score,
    draw_title,
    draw_touch_controls,
    goal_screen_pos,
    help_buttons,
    hit_button,
    logic_heading_to_screen,
    logic_to_screen,
    pause_button_rect,
    pause_buttons,
    result_buttons,
    screen_dir_to_logic,
    title_buttons,
)
from result_flow import ResultPhase  # noqa: E402
from settings import load_settings, save_settings  # noqa: E402
from sprites import init_sprites  # noqa: E402
from touch_input import TouchControls, dash_button_center, keyboard_output, pad_home  # noqa: E402
from visuals import make_window_icon  # noqa: E402

MOUSE_FINGER = -1
DASH_PUFF_INTERVAL = 0.045


class MobileGame:
    """入力と進行。描画先を持たないのでヘッドレスでも動かせる"""

    def __init__(self, audio: SoundManager | None) -> None:
        self.audio = audio
        self.settings = load_settings()
        self.match = Match(audio=audio, cpu_diff_index=self.settings.cpu_diff_index)
        self.cpu_ai = CPUAI(self.settings.cpu_difficulty)
        self.controls = TouchControls(MOBILE_H)
        self.fx = MobileFX()
        self.butterfly = VictoryButterfly()
        self.bgm_muted = False
        self.bgm_paused = False
        self.game_time = 0.0
        self.running = True
        self.pressed_action: str | None = None
        self.pressed_at = -10.0
        self.pause_pop_at = -10.0
        self.shake_timer = 0.0
        self.hitstop_timer = 0.0
        self._puck_speeds: list[float] = []
        self._breach_marks: list[float] = []
        self._prev_scores = (0, 0)
        self._next_puff = 0.0
        if audio is not None and self.settings.bgm_muted:
            self.bgm_muted = audio.toggle_bgm_mute()

    # --- UI ---
    def visible_buttons(self) -> list:
        state = self.match.state
        if state == GameState.TITLE:
            return title_buttons(self.bgm_muted, self.match.cpu_diff_index)
        if state == GameState.HELP:
            return help_buttons()
        if state == GameState.PAUSE:
            return pause_buttons(self.bgm_muted)
        if state == GameState.RESULT and self.match.result_phase == ResultPhase.HOLD:
            return result_buttons()
        return []

    def start_match(self, *, vs_cpu: bool) -> None:
        match = self.match
        match._reset_for_new_match()
        match.vs_cpu = vs_cpu
        match.enter_countdown()
        self.controls.reset()
        self.fx.reset()
        self.butterfly.active = False
        self._prev_scores = (0, 0)
        if vs_cpu:
            self.cpu_ai.set_difficulty(CPU_DIFFICULTY_ORDER[match.cpu_diff_index])
            self.cpu_ai.reset()

    def perform(self, action: str) -> None:
        match = self.match
        if self.audio is not None:
            self.audio.play_menu_move()
        if action.startswith("cpu_diff:"):
            match.cpu_diff_index = int(action.split(":")[1])
            self.settings.cpu_difficulty = CPU_DIFFICULTY_ORDER[match.cpu_diff_index]
            save_settings(self.settings)
        elif action.startswith("cpu:"):
            match.cpu_diff_index = int(action.split(":")[1])
            self.settings.cpu_difficulty = CPU_DIFFICULTY_ORDER[match.cpu_diff_index]
            save_settings(self.settings)
            self.start_match(vs_cpu=True)
        elif action == "two_player":
            self.start_match(vs_cpu=False)
        elif action == "help":
            match.open_help()
        elif action == "close_help":
            match.close_help()
        elif action == "bgm":
            if self.audio is not None:
                self.bgm_muted = self.audio.toggle_bgm_mute()
                self.settings.bgm_muted = self.bgm_muted
                save_settings(self.settings)
        elif action == "resume":
            self.controls.reset()
            match.toggle_pause()
        elif action == "rematch":
            self.start_match(vs_cpu=match.vs_cpu)
        elif action == "to_title":
            self.controls.reset()
            self.fx.reset()
            self.butterfly.active = False
            match.back_to_title()

    # --- 入力 ---
    def on_press(self, finger: int, x: float, y: float) -> None:
        match = self.match
        if match.state in (GameState.PLAYING, GameState.COUNTDOWN):
            if pause_button_rect().collidepoint(x, y):
                self.pause_pop_at = self.game_time
                match.toggle_pause()
                self.controls.reset()
                return
            self.controls.visible = True
            self.controls.press(finger, x, y, self.game_time, two_player=not match.vs_cpu)
            return
        action = hit_button(self.visible_buttons(), x, y)
        if action is not None:
            self.pressed_action = action
            self.pressed_at = self.game_time
            self.perform(action)

    def on_move(self, finger: int, x: float, y: float) -> None:
        self.controls.move(finger, x, y, self.game_time)

    def on_release(self, finger: int, x: float, y: float) -> None:
        self.controls.release(finger, x, y, self.game_time)

    def on_focus_lost(self) -> None:
        if self.match.state in (GameState.PLAYING, GameState.COUNTDOWN):
            self.match.toggle_pause()
        self.controls.reset()

    def external_moves(self) -> dict[int, tuple[float, float, bool]]:
        moves: dict[int, tuple[float, float, bool]] = {}
        for player, stick in enumerate(self.controls.sticks):
            dx, dy, dash = stick.output(self.game_time)
            if not (dx or dy):
                dx, dy, dash = keyboard_output(pygame.key.get_pressed(), player, two_player=not self.match.vs_cpu)
            lx, ly = screen_dir_to_logic(dx, dy)
            moves[player] = (lx, ly, dash)
        return moves

    # --- 進行 ---
    def shake_offset(self) -> tuple[float, float]:
        if self.shake_timer <= 0.0:
            return 0.0, 0.0
        k = self.shake_timer / MOBILE_SHAKE_DURATION
        amp = MOBILE_SHAKE_AMPLITUDE * k * k
        t = self.game_time
        return math.sin(t * 61.0) * amp, math.sin(t * 47.0) * amp * 0.8

    def _spawn_dash_puffs(self) -> None:
        if self.game_time < self._next_puff:
            return
        for paddle in self.match.paddles:
            if not paddle.is_dashing:
                continue
            sx, sy = logic_to_screen(paddle.x, paddle.y)
            self.fx.puff_dash(sx, sy, logic_heading_to_screen(paddle.face_heading), paddle.player)
        self._next_puff = self.game_time + DASH_PUFF_INTERVAL

    def _watch_match_events(self) -> None:
        match = self.match
        scores = tuple(match.scores)
        if scores != self._prev_scores:
            scorer = 0 if scores[0] != self._prev_scores[0] else 1
            x, y = goal_screen_pos(match)
            self.fx.burst_goal(x, y, scorer)
            self.shake_timer = MOBILE_SHAKE_DURATION
            self._prev_scores = scores

        speeds = []
        marks = []
        for i, puck in enumerate(match.pucks):
            speed = math.hypot(puck.vx, puck.vy)
            prev = self._puck_speeds[i] if i < len(self._puck_speeds) else speed
            if speed >= MOBILE_STRONG_HIT_SPEED and speed - prev >= MOBILE_STRONG_HIT_GAIN:
                self.shake_timer = MOBILE_SHAKE_DURATION
                self.hitstop_timer = MOBILE_HITSTOP_DURATION
            speeds.append(speed)
            prev_mark = self._breach_marks[i] if i < len(self._breach_marks) else 0.0
            if puck.breach_flash_until > prev_mark + 1e-6:
                sx, sy = logic_to_screen(puck.x, puck.y)
                self.fx.burst_shards(sx, sy, 1 - int(puck.vx > 0))
            marks.append(puck.breach_flash_until)
        self._puck_speeds = speeds
        self._breach_marks = marks

        if match.state == GameState.RESULT and match.winner is not None and not self.butterfly.active:
            self.butterfly.start(match.winner, MOBILE_W / 2, 500)

    def step(self, dt: float) -> None:
        match = self.match
        if self.hitstop_timer > 0.0:
            # 強打の一瞬の停止（入力は受け続ける）
            self.hitstop_timer -= dt
            return
        if match.state != GameState.PAUSE:
            self.game_time += dt
        if match.state in (GameState.COUNTDOWN, GameState.PLAYING):
            ai = self.cpu_ai if match.vs_cpu else None
            match.handle_input(None, dt, self.game_time, cpu_ai=ai, external_moves=self.external_moves())
        if match.state not in (GameState.PAUSE, GameState.TITLE, GameState.HELP):
            match.update(dt, self.game_time)
        if match.state != GameState.PAUSE:
            self._watch_match_events()
            self._spawn_dash_puffs()
            self.fx.update(dt)
            self.butterfly.update(dt)
            self.shake_timer = max(0.0, self.shake_timer - dt)
        if self.audio is not None:
            if match.state == GameState.PAUSE and not self.bgm_paused:
                self.audio.pause_bgm()
                self.bgm_paused = True
            elif match.state != GameState.PAUSE and self.bgm_paused:
                self.audio.resume_bgm()
                self.bgm_paused = False
            else:
                self.audio.set_bgm_for_state(match.state.name)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.WINDOWFOCUSLOST:
            self.on_focus_lost()
        elif event.type == pygame.KEYDOWN:
            self.controls.visible = False
            if event.key == pygame.K_ESCAPE and self.match.state in (
                GameState.PLAYING, GameState.COUNTDOWN, GameState.PAUSE,
            ):
                self.controls.reset()
                self.match.toggle_pause()
        elif event.type == pygame.FINGERDOWN:
            self.on_press(event.finger_id, event.x * MOBILE_W, event.y * MOBILE_H)
        elif event.type == pygame.FINGERMOTION:
            self.on_move(event.finger_id, event.x * MOBILE_W, event.y * MOBILE_H)
        elif event.type == pygame.FINGERUP:
            self.on_release(event.finger_id, event.x * MOBILE_W, event.y * MOBILE_H)
        # タッチから合成されたマウスイベントは二重に処理しない（PC ブラウザ確認用）
        elif event.type == pygame.MOUSEBUTTONDOWN and not getattr(event, "touch", False):
            self.on_press(MOUSE_FINGER, *event.pos)
        elif event.type == pygame.MOUSEMOTION and not getattr(event, "touch", False):
            self.on_move(MOUSE_FINGER, *event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and not getattr(event, "touch", False):
            self.on_release(MOUSE_FINGER, *event.pos)


def draw_frame(screen: pygame.Surface, game: MobileGame, now: float) -> None:
    """描画の時計は game.game_time と同じものを使う（体節の寿命判定とずれると消える）"""
    match = game.match
    buttons = game.visible_buttons()
    pressed = (game.pressed_action, game.pressed_at)

    if match.state == GameState.TITLE:
        draw_title(
            screen, now, cpu_diff_index=match.cpu_diff_index, buttons=buttons,
            pressed_action=pressed[0], pressed_at=pressed[1],
        )
        return
    if match.state == GameState.HELP:
        draw_help(screen, now, buttons, pressed_action=pressed[0], pressed_at=pressed[1])
        return

    draw_match(screen, match, now, fx=game.fx, shake=game.shake_offset())
    pause_pop = max(0.0, 1.0 - (now - game.pause_pop_at) / 0.25)
    if game.controls.visible and match.state in (GameState.PLAYING, GameState.COUNTDOWN):
        for player in (0,) if match.vs_cpu else (0, 1):
            stick = game.controls.sticks[player]
            draw_touch_controls(
                screen,
                player=player,
                anchor=(stick.anchor_x, stick.anchor_y) if stick.finger is not None else pad_home(player),
                knob=stick.knob_offset(),
                dash_center=dash_button_center(player),
                dash_active=stick.is_dash_active(now),
            )
    draw_score(screen, match, pause_pop=min(1.0, pause_pop))
    draw_countdown(screen, match, now)
    game.fx.draw_goal_text(screen)

    if match.state == GameState.PAUSE:
        draw_pause(screen, buttons, now, pressed_action=pressed[0], pressed_at=pressed[1])
    elif match.state == GameState.RESULT:
        draw_result(
            screen, match, buttons, butterfly=game.butterfly, now=now,
            pressed_action=pressed[0], pressed_at=pressed[1],
        )


def run_frame(screen: pygame.Surface, game: MobileGame, dt: float) -> None:
    """main ループの1フレーム分。描画も game.game_time で行う（壁時計を混ぜない）"""
    for event in pygame.event.get():
        game.handle_event(event)
    game.step(dt)
    draw_frame(screen, game, game.game_time)


async def main() -> None:
    pygame.init()
    pygame.display.set_icon(make_window_icon())
    pygame.display.set_caption(GAME_TITLE)
    screen = pygame.display.set_mode((MOBILE_W, MOBILE_H))
    init_sprites()
    clock = pygame.time.Clock()

    audio: SoundManager | None = None
    if SOUND_ENABLED:
        try:
            audio = SoundManager()
        except pygame.error:
            audio = None
    game = MobileGame(audio)
    if audio is not None:
        audio.play_title_bgm()

    while game.running:
        dt = min(clock.tick(FPS) / 1000.0, MAX_FRAME_DT)
        run_frame(screen, game, dt)
        pygame.display.flip()
        await asyncio.sleep(0)

    if audio is not None:
        audio.stop_bgm()
    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
