"""スマホ版エントリ — 縦画面・タッチ操作（Web 版ではビルド時に main.py として配置）"""

import asyncio
import time

import pygame

from ai import CPUAI, CPU_DIFFICULTY_ORDER
from arena_assets import init_arena_assets
from audio import SoundManager
from constants import (
    FPS,
    GAME_TITLE,
    MAX_FRAME_DT,
    MOBILE_H,
    MOBILE_UI_BUTTON_SIZE,
    MOBILE_UI_RESULT_SIZE,
    MOBILE_W,
    SCREEN_H,
    SCREEN_W,
    SOUND_ENABLED,
)
from game import GameState, Match
from mobile_view import (
    blit_cached_screen,
    draw_arena,
    draw_countdown,
    draw_help,
    draw_hud,
    draw_pause,
    draw_result,
    draw_title,
    help_buttons,
    hit_button,
    pause_button_rect,
    pause_buttons,
    result_buttons,
    screen_dir_to_logic,
    title_buttons,
)
from result_flow import ResultPhase
from settings import load_settings, save_settings
from sprites import init_sprites
from title_typography import _load_font, load_title_fonts
from touch_input import TouchControls
from visuals import make_window_icon

MOUSE_FINGER = -1


class UIFonts:
    def __init__(self) -> None:
        self.button = _load_font(MOBILE_UI_BUTTON_SIZE)
        self.result = _load_font(MOBILE_UI_RESULT_SIZE)
        self.body = _load_font(24)
        self.small = _load_font(21, medium=True)


class MobileGame:
    """入力と進行。描画先を持たないのでヘッドレスでも動かせる"""

    def __init__(self, audio: SoundManager | None) -> None:
        self.audio = audio
        self.settings = load_settings()
        self.match = Match(audio=audio, cpu_diff_index=self.settings.cpu_diff_index)
        self.cpu_ai = CPUAI(self.settings.cpu_difficulty)
        self.controls = TouchControls(MOBILE_H)
        self.bgm_muted = False
        self.bgm_paused = False
        self.game_time = 0.0
        self.running = True
        if audio is not None and self.settings.bgm_muted:
            self.bgm_muted = audio.toggle_bgm_mute()

    def visible_buttons(self) -> list:
        state = self.match.state
        if state == GameState.TITLE:
            return title_buttons(self.bgm_muted)
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
        if vs_cpu:
            self.cpu_ai.set_difficulty(CPU_DIFFICULTY_ORDER[match.cpu_diff_index])
            self.cpu_ai.reset()

    def perform(self, action: str) -> None:
        match = self.match
        if self.audio is not None:
            self.audio.play_menu_move()
        if action.startswith("cpu:"):
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
            match.back_to_title()

    def on_press(self, finger: int, x: float, y: float) -> None:
        match = self.match
        if match.state in (GameState.PLAYING, GameState.COUNTDOWN):
            if pause_button_rect().collidepoint(x, y):
                match.toggle_pause()
                self.controls.reset()
                return
            self.controls.press(finger, x, y, self.game_time, two_player=not match.vs_cpu)
            return
        action = hit_button(self.visible_buttons(), x, y)
        if action is not None:
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
            lx, ly = screen_dir_to_logic(dx, dy)
            moves[player] = (lx, ly, dash)
        return moves

    def step(self, dt: float) -> None:
        match = self.match
        if match.state != GameState.PAUSE:
            self.game_time += dt
        if match.state in (GameState.COUNTDOWN, GameState.PLAYING):
            ai = self.cpu_ai if match.vs_cpu else None
            match.handle_input(None, dt, self.game_time, cpu_ai=ai, external_moves=self.external_moves())
        if match.state not in (GameState.PAUSE, GameState.TITLE, GameState.HELP):
            match.update(dt, self.game_time)
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


def draw_frame(screen, scratch, arena, game: MobileGame, title_fonts, ui_fonts, big_font, now: float) -> None:
    match = game.match
    buttons = game.visible_buttons()

    def draw_match(surf: pygame.Surface) -> None:
        draw_arena(surf, arena, match, now)
        draw_hud(surf, match, ui_fonts, now)
        draw_countdown(surf, match, big_font)

    if match.state == GameState.TITLE:
        blit_cached_screen(
            screen, ("title", match.cpu_diff_index, game.bgm_muted),
            lambda surf: draw_title(
                surf, title_fonts, ui_fonts, now, scratch, cpu_diff_index=match.cpu_diff_index, buttons=buttons,
            ),
        )
    elif match.state == GameState.HELP:
        blit_cached_screen(
            screen, "help", lambda surf: draw_help(surf, title_fonts, ui_fonts, now, scratch, buttons),
        )
    elif match.state == GameState.PAUSE:
        def build_pause(surf: pygame.Surface) -> None:
            draw_match(surf)
            draw_pause(surf, title_fonts, ui_fonts, buttons)

        blit_cached_screen(screen, ("pause", game.game_time, game.bgm_muted), build_pause)
    elif match.state == GameState.RESULT and match.result_phase == ResultPhase.HOLD:
        def build_result(surf: pygame.Surface) -> None:
            draw_match(surf)
            draw_result(surf, match, title_fonts, ui_fonts, buttons)

        blit_cached_screen(screen, ("result", tuple(match.scores), match.match_time), build_result)
    else:
        draw_match(screen)
        if match.state == GameState.RESULT:
            draw_result(screen, match, title_fonts, ui_fonts, [])


async def main() -> None:
    pygame.init()
    pygame.display.set_icon(make_window_icon())
    pygame.display.set_caption(GAME_TITLE)
    screen = pygame.display.set_mode((MOBILE_W, MOBILE_H))
    init_sprites()
    init_arena_assets()
    arena = pygame.Surface((SCREEN_W, SCREEN_H)).convert()
    scratch = pygame.Surface((SCREEN_W, SCREEN_H)).convert()
    clock = pygame.time.Clock()
    title_fonts = load_title_fonts()
    ui_fonts = UIFonts()
    big_font = _load_font(120)

    audio: SoundManager | None = None
    if SOUND_ENABLED:
        try:
            audio = SoundManager()
        except pygame.error:
            audio = None
    game = MobileGame(audio)
    if audio is not None:
        audio.play_title_bgm()
    start_time = time.perf_counter()

    while game.running:
        dt = min(clock.tick(FPS) / 1000.0, MAX_FRAME_DT)
        for event in pygame.event.get():
            game.handle_event(event)
        game.step(dt)
        draw_frame(screen, scratch, arena, game, title_fonts, ui_fonts, big_font, time.perf_counter() - start_time)
        pygame.display.flip()
        await asyncio.sleep(0)

    if audio is not None:
        audio.stop_bgm()
    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
