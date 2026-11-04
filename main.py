"""エントリ・ゲームループ・描画"""

import sys

import pygame

from arena_assets import (
    ArenaLightingState,
    draw_arena_table,
    draw_battle_backdrop,
    draw_menu_backdrop,
    draw_organic_plaque,
    init_arena_assets,
)
from audio import SoundManager
from game import GameState, Match
from match_prep import PrepPhase, draw_cinematic_veil
from result_flow import ResultPhase
from constants import (
    CATERPILLAR_BODY_RADIUS,
    FPS,
    GAME_TITLE,
    GO_DISPLAY_DURATION,
    LOGO_FILL,
    LOGO_OUTLINE,
    FOCUS_PAUSE_DELAY,
    MAX_FRAME_DT,
    MENU_BORDER,
    MENU_TEXT_DIM,
    SCREEN_H,
    SOUND_ENABLED,
    SCREEN_W,
    VERSION,
)
from ai import CPUAI, CPU_DIFFICULTY_ORDER, DEFAULT_CPU_DIFFICULTY
from caterpillar_art import draw_player_fences
from effects import draw_breach_sparks, draw_goal_celebration
from screens import (
    _draw_tips_subtitle_veil,
    draw_cpu_difficulty_screen,
    draw_help_screen,
    draw_result_screen,
    draw_title_screen,
    draw_tips_overlay,
)
from hud_ui import draw_bgm_muted_badge, draw_match_hud
from settings import load_settings, save_settings
from sprites import init_sprites
from title_typography import load_title_fonts, render_ui_outlined
from visuals import make_window_icon

ARENA_STATES = frozenset({
    GameState.COUNTDOWN,
    GameState.PLAYING,
    GameState.PAUSE,
    GameState.RESULT,
})


def draw_pause(surf: pygame.Surface, hud_font: pygame.font.Font, small: pygame.font.Font) -> None:
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((8, 16, 10, 175))
    surf.blit(overlay, (0, 0))

    card_w, card_h = 380, 150
    card = pygame.Rect(SCREEN_W // 2 - card_w // 2, SCREEN_H // 2 - card_h // 2, card_w, card_h)
    draw_organic_plaque(surf, card)
    pygame.draw.rect(surf, MENU_BORDER, card, 2, border_radius=12)

    pause_t = render_ui_outlined("ポーズ", hud_font, LOGO_FILL, outline=LOGO_OUTLINE, outline_px=3)
    surf.blit(pause_t, pause_t.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 22)))
    hint = render_ui_outlined("P: 再開 / Esc: タイトルへ", small, LOGO_FILL, outline=LOGO_OUTLINE, outline_px=2)
    surf.blit(hint, hint.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 40)))


def create_display(fullscreen: bool) -> tuple[pygame.Surface, bool]:
    """SCALED で論理解像度を保ったまま拡大（モニターの解像度は変更しない）"""
    flags = pygame.SCALED | (pygame.FULLSCREEN if fullscreen else 0)
    try:
        return pygame.display.set_mode((SCREEN_W, SCREEN_H), flags), fullscreen
    except pygame.error:
        return pygame.display.set_mode((SCREEN_W, SCREEN_H)), False


def draw_countdown(surf: pygame.Surface, match: Match, big_font: pygame.font.Font) -> None:
    if match.countdown > 0:
        t = render_ui_outlined(
            str(match.countdown), big_font, LOGO_FILL, outline=LOGO_OUTLINE, outline_px=4,
        )
        surf.blit(t, t.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2)))


def draw_go(surf: pygame.Surface, match: Match, big_font: pygame.font.Font) -> None:
    if match.go_timer <= 0.0:
        return
    t = render_ui_outlined("GO!", big_font, LOGO_FILL, outline=LOGO_OUTLINE, outline_px=4)
    t.set_alpha(int(255 * min(1.0, match.go_timer / (GO_DISPLAY_DURATION * 0.5))))
    surf.blit(t, t.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2)))


def draw_battle_scene(
    surf: pygame.Surface,
    match: Match,
    title_fonts,
    now: float,
    *,
    bgm_muted: bool,
) -> None:
    lighting = match.arena_lighting
    draw_battle_backdrop(surf, now, lighting=lighting)
    draw_arena_table(surf, now, lighting=lighting)
    for owner in (0, 1):
        player_fences = [f for f in match.fences if f.owner == owner]
        draw_player_fences(surf, player_fences, now, CATERPILLAR_BODY_RADIUS)
    for puck in match.pucks:
        puck.draw(surf, now)
    if match.puck_reset_anim is not None:
        match.puck_reset_anim.draw(surf, now)
    draw_breach_sparks(surf, match.breach_sparks)
    for paddle in match.paddles:
        paddle.draw(surf, now)
    draw_match_hud(surf, match, title_fonts, now, bgm_muted=bgm_muted)
    if match.goal_fx is not None:
        draw_goal_celebration(surf, match.goal_fx)


def apply_cpu_difficulty(match: Match, cpu_ai: CPUAI) -> None:
    key = CPU_DIFFICULTY_ORDER[match.cpu_diff_index]
    cpu_ai.set_difficulty(key)
    cpu_ai.reset()


def main() -> None:
    pygame.init()
    pygame.display.set_icon(make_window_icon())
    pygame.display.set_caption(f"{GAME_TITLE} v{VERSION}")
    settings = load_settings()
    screen, fullscreen = create_display(settings.fullscreen)
    init_sprites()
    init_arena_assets()
    clock = pygame.time.Clock()

    title_fonts = load_title_fonts()
    title_font = title_fonts.screen_title
    body_font = title_fonts.screen_body
    small_font = title_fonts.screen_small
    big_font = pygame.font.SysFont("meiryo", 96, bold=True)

    audio: SoundManager | None = None
    if SOUND_ENABLED:
        try:
            audio = SoundManager()
        except pygame.error:
            audio = None

    match = Match(audio=audio, cpu_diff_index=settings.cpu_diff_index)
    bgm_muted = False
    if audio is not None:
        bgm_muted = audio.set_bgm_muted(settings.bgm_muted)
        audio.play_title_bgm()
    cpu_ai = CPUAI(DEFAULT_CPU_DIFFICULTY)
    running = True
    now = 0.0  # ゲーム時計 — 単調増加し、ポーズ中は止まる
    bgm_paused = False
    window_focused = True
    unfocused_time = 0.0

    while running:
        dt = min(clock.tick(FPS) / 1000.0, MAX_FRAME_DT)
        keys = pygame.key.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.WINDOWFOCUSLOST:
                window_focused = False
            elif event.type == pygame.WINDOWFOCUSGAINED:
                window_focused = True
                unfocused_time = 0.0
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if match.state == GameState.TITLE:
                        running = False
                    elif match.state == GameState.HELP:
                        match.close_help()
                    elif match.state == GameState.CPU_DIFF:
                        match.begin_cpu_diff_exit()
                    elif match.state == GameState.PREP:
                        match.back_to_title()
                    elif match.state == GameState.PAUSE:
                        match.back_to_title()
                    elif match.state in (GameState.PLAYING, GameState.COUNTDOWN):
                        match.toggle_pause()
                    else:
                        match.back_to_title()
                elif event.key == pygame.K_f:
                    screen, fullscreen = create_display(not fullscreen)
                    settings.fullscreen = fullscreen
                    save_settings(settings)
                elif event.key == pygame.K_h:
                    if match.state == GameState.TITLE:
                        match.open_help()
                    elif match.state == GameState.HELP:
                        match.close_help()
                elif event.key in (pygame.K_UP, pygame.K_w):
                    if match.state == GameState.TITLE:
                        prev = match.title_menu_index
                        match.title_menu_index = (match.title_menu_index - 1) % 3
                        if audio is not None and match.title_menu_index != prev:
                            audio.play_menu_move()
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    if match.state == GameState.TITLE:
                        prev = match.title_menu_index
                        match.title_menu_index = (match.title_menu_index + 1) % 3
                        if audio is not None and match.title_menu_index != prev:
                            audio.play_menu_move()
                elif event.key in (pygame.K_a, pygame.K_LEFT):
                    if match.state == GameState.CPU_DIFF and match.cpu_diff_ready():
                        prev = match.cpu_diff_index
                        match.cpu_diff_index = (match.cpu_diff_index - 1) % 3
                        if audio is not None and match.cpu_diff_index != prev:
                            audio.play_menu_move()
                elif event.key in (pygame.K_d, pygame.K_RIGHT):
                    if match.state == GameState.CPU_DIFF and match.cpu_diff_ready():
                        prev = match.cpu_diff_index
                        match.cpu_diff_index = (match.cpu_diff_index + 1) % 3
                        if audio is not None and match.cpu_diff_index != prev:
                            audio.play_menu_move()
                elif event.key in (pygame.K_3, pygame.K_KP3):
                    if match.state == GameState.CPU_DIFF and match.cpu_diff_ready():
                        prev = match.cpu_diff_index
                        match.cpu_diff_index = 0
                        if audio is not None and match.cpu_diff_index != prev:
                            audio.play_menu_move()
                elif event.key in (pygame.K_4, pygame.K_KP4):
                    if match.state == GameState.CPU_DIFF and match.cpu_diff_ready():
                        prev = match.cpu_diff_index
                        match.cpu_diff_index = 1
                        if audio is not None and match.cpu_diff_index != prev:
                            audio.play_menu_move()
                elif event.key in (pygame.K_5, pygame.K_KP5):
                    if match.state == GameState.CPU_DIFF and match.cpu_diff_ready():
                        prev = match.cpu_diff_index
                        match.cpu_diff_index = 2
                        if audio is not None and match.cpu_diff_index != prev:
                            audio.play_menu_move()
                elif event.key == pygame.K_m:
                    if audio is not None:
                        bgm_muted = audio.toggle_bgm_mute()
                        settings.bgm_muted = bgm_muted
                        save_settings(settings)
                elif event.key == pygame.K_SPACE:
                    if match.state == GameState.HELP:
                        match.close_help()
                    elif match.state == GameState.TITLE:
                        if match.title_menu_index == 0:
                            match.begin_from_menu(vs_cpu=True)
                        elif match.title_menu_index == 1:
                            match.begin_from_menu(vs_cpu=False)
                        else:
                            running = False
                    elif match.state == GameState.CPU_DIFF:
                        if match.cpu_diff_ready():
                            apply_cpu_difficulty(match, cpu_ai)
                            settings.cpu_difficulty = CPU_DIFFICULTY_ORDER[match.cpu_diff_index]
                            save_settings(settings)
                            match.start_fade_to_tips()
                    elif match.state == GameState.PREP:
                        match.skip_tips_display()
                    elif match.state == GameState.RESULT:
                        if match.result_phase == ResultPhase.HOLD:
                            apply_cpu_difficulty(match, cpu_ai)
                            match.start_rematch()
                elif event.key == pygame.K_p:
                    if match.state in (GameState.PLAYING, GameState.COUNTDOWN, GameState.PAUSE):
                        match.toggle_pause()

        # フルスクリーン切替の一瞬のフォーカス喪失では止めない
        if not window_focused:
            unfocused_time += dt
            if unfocused_time >= FOCUS_PAUSE_DELAY and match.state in (GameState.PLAYING, GameState.COUNTDOWN):
                match.toggle_pause()

        if match.state != GameState.PAUSE:
            now += dt

        if match.state not in (GameState.PAUSE, GameState.TITLE, GameState.CPU_DIFF, GameState.PREP, GameState.HELP):
            ai = cpu_ai if match.vs_cpu else None
            match.handle_input(keys, dt, now, cpu_ai=ai)
        if match.state not in (GameState.PAUSE, GameState.TITLE):
            match.update(dt, now)

        if audio is not None:
            if match.state == GameState.PAUSE and not bgm_paused:
                audio.pause_bgm()
                bgm_paused = True
            elif match.state != GameState.PAUSE and bgm_paused:
                audio.resume_bgm()
                bgm_paused = False
            else:
                rematch_prep = match.state == GameState.PREP and match.prep_from_state == GameState.RESULT
                audio.set_bgm_for_state("RESULT" if rematch_prep else match.state.name)

        show_arena = match.state in ARENA_STATES or (
            match.state == GameState.PREP
            and (match.prep_phase == PrepPhase.REVEAL or match.prep_from_state == GameState.RESULT)
        )
        if show_arena:
            draw_battle_scene(
                screen, match, title_fonts, now, bgm_muted=bgm_muted,
            )

        if match.state == GameState.TITLE:
            draw_title_screen(
                screen,
                title_font,
                body_font,
                small_font,
                menu_index=match.title_menu_index,
                menu_sel_strengths=match.title_menu_sel_strengths(),
                title_fonts=title_fonts,
                cpu_diff_index=match.cpu_diff_index,
                now=now,
                dt=dt,
            )
        elif match.state == GameState.HELP:
            draw_help_screen(screen, title_fonts, now=now)
        elif match.state == GameState.CPU_DIFF:
            draw_cpu_difficulty_screen(
                screen,
                title_font,
                body_font,
                small_font,
                selected_index=match.cpu_diff_index,
                cpu_sel_strengths=match.cpu_diff_sel_strengths(),
                now=now,
                title_fonts=title_fonts,
                morph_progress=match.cpu_diff_morph,
            )
        elif match.state == GameState.PREP:
            handoff_active = (
                match.prep_from_state is not None
                and match.prep_phase == PrepPhase.DARKEN
                and match.prep_darkness < 0.92
            )
            if match.prep_from_state == GameState.RESULT:
                if match.prep_phase == PrepPhase.DARKEN:
                    draw_result_screen(screen, match, title_font, body_font, small_font, now=now)
            elif handoff_active:
                if match.prep_from_state == GameState.CPU_DIFF:
                    draw_cpu_difficulty_screen(
                        screen,
                        title_font,
                        body_font,
                        small_font,
                        selected_index=match.cpu_diff_index,
                        cpu_sel_strengths=match.cpu_diff_sel_strengths(),
                        now=now,
                        title_fonts=title_fonts,
                        morph_progress=match.prep_handoff_morph,
                    )
                else:
                    draw_title_screen(
                        screen,
                        title_font,
                        body_font,
                        small_font,
                        menu_index=match.prep_handoff_menu_index,
                        menu_sel_strengths=match.title_menu_sel_strengths(),
                        title_fonts=title_fonts,
                        now=now,
                        dt=0.0,
                    )
            elif match.prep_phase != PrepPhase.REVEAL:
                draw_menu_backdrop(screen, now)
                if match.tips_alpha > 0.0:
                    _draw_tips_subtitle_veil(screen, now)
                    draw_tips_overlay(
                        screen,
                        body_font,
                        small_font,
                        tip_text=match.tips_text,
                        tips_alpha=match.tips_alpha,
                    )
            draw_cinematic_veil(
                screen,
                match.prep_darkness,
                match.prep_reveal,
            )
        elif match.state == GameState.COUNTDOWN:
            draw_countdown(screen, match, big_font)
        elif match.state == GameState.PLAYING:
            draw_go(screen, match, big_font)
        elif match.state == GameState.PAUSE:
            draw_pause(screen, title_font, small_font)
        elif match.state == GameState.RESULT:
            draw_result_screen(screen, match, title_font, body_font, small_font, now=now)

        if bgm_muted and not show_arena:
            draw_bgm_muted_badge(screen, title_fonts.hud_meta)

        pygame.display.flip()

    if audio is not None:
        audio.stop_bgm()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
