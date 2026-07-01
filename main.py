"""エントリ・ゲームループ・描画"""

import sys
import time

import pygame

from constants import (
    BG_COLOR,
    CATERPILLAR_BODY_RADIUS,
    CENTER_LINE_COLOR,
    CPU_LABEL,
    FPS,
    GAME_TITLE,
    HUD_COLOR,
    P1_COLOR,
    P1_LABEL,
    P1_NEON,
    P2_COLOR,
    P2_LABEL,
    P2_NEON,
    SCREEN_H,
    SOUND_ENABLED,
    SCREEN_W,
    TABLE_BORDER,
    TABLE_BORDER_WIDTH,
    TABLE_COLOR,
    TABLE_GRID_COLOR,
    TABLE_H,
    TABLE_MARGIN_X,
    TABLE_W,
    TABLE_Y,
    TRAIL_CENTER_ZONE_RATIO,
    TRAIL_GOAL_ZONE_RATIO,
    VERSION,
    WIN_SCORE,
)
from ai import CPUAI, CPU_DIFFICULTY_ORDER, DEFAULT_CPU_DIFFICULTY
from audio import SoundManager
from entities import table_rect, goal_bounds
from game import GameState, Match
from caterpillar_art import draw_player_fences
from effects import draw_breach_sparks, draw_goal_celebration
from screens import (
    draw_cpu_difficulty_screen,
    draw_fade_screen,
    draw_result_screen,
    draw_title_screen,
    draw_tips_screen,
    tips_for_match,
)
from sprites import init_sprites
from visuals import make_window_icon

ARENA_STATES = frozenset({
    GameState.COUNTDOWN,
    GameState.PLAYING,
    GameState.PAUSE,
    GameState.RESULT,
})


def draw_table(surf: pygame.Surface) -> None:
    rect = table_rect()
    pygame.draw.rect(surf, TABLE_COLOR, rect)
    goal_top, goal_bottom = goal_bounds()
    bw = TABLE_BORDER_WIDTH

    for x in range(rect.left + 20, rect.right, 40):
        pygame.draw.line(surf, (18, 32, 22), (x, rect.top + 4), (x, rect.bottom - 4), 1)
    for y in range(rect.top + 20, rect.bottom, 40):
        pygame.draw.line(surf, (18, 32, 22), (rect.left + 4, y), (rect.right - 4, y), 1)

    # 上下の壁
    pygame.draw.line(surf, TABLE_BORDER, (rect.left, rect.top), (rect.right, rect.top), bw)
    pygame.draw.line(surf, TABLE_BORDER, (rect.left, rect.bottom), (rect.right, rect.bottom), bw)

    # 左右ゴール枠
    pygame.draw.line(surf, TABLE_BORDER, (rect.left, rect.top), (rect.left, goal_top), bw)
    pygame.draw.line(surf, TABLE_BORDER, (rect.left, goal_bottom), (rect.left, rect.bottom), bw)
    pygame.draw.line(surf, TABLE_BORDER, (rect.right, rect.top), (rect.right, goal_top), bw)
    pygame.draw.line(surf, TABLE_BORDER, (rect.right, goal_bottom), (rect.right, rect.bottom), bw)

    # ゴールポスト強調
    for gx, gy in (
        (rect.left, goal_top), (rect.left, goal_bottom),
        (rect.right, goal_top), (rect.right, goal_bottom),
    ):
        pygame.draw.circle(surf, TABLE_BORDER, (gx, gy), 5)
        pygame.draw.circle(surf, (0, 0, 0), (gx, gy), 3)

    # 中央ライン
    cx = rect.centerx
    for y in range(rect.top + 8, rect.bottom - 8, 20):
        pygame.draw.line(surf, CENTER_LINE_COLOR, (cx, y), (cx, y + 10), 2)

    # 中央制圧ボーナスゾーン（薄い表示）
    center_w = int(rect.width * TRAIL_CENTER_ZONE_RATIO)
    center = pygame.Surface((center_w, rect.height), pygame.SRCALPHA)
    center.fill((0, 255, 255, 6))
    surf.blit(center, (rect.centerx - center_w // 2, rect.top))

    # ゴール前クレース（壁が短命になるゾーン）
    crease_w = int(rect.width * TRAIL_GOAL_ZONE_RATIO)
    for side_x in (rect.left, rect.right - crease_w):
        crease = pygame.Surface((crease_w, rect.height), pygame.SRCALPHA)
        crease.fill((255, 255, 255, 10))
        surf.blit(crease, (side_x, rect.top))


def draw_hud(
    surf: pygame.Surface,
    match: Match,
    font: pygame.font.Font,
    small: pygame.font.Font,
    now: float,
    bgm_muted: bool = False,
) -> None:
    mins = int(match.match_time) // 60
    secs = int(match.match_time) % 60

    p1_label = small.render(P1_LABEL, True, P1_COLOR)
    surf.blit(p1_label, (24, 22))
    if match.vs_cpu:
        p2_label = small.render(CPU_LABEL, True, P2_COLOR)
        surf.blit(p2_label, p2_label.get_rect(topright=(SCREEN_W - 24, 22)))
    else:
        p2_label = small.render(P2_LABEL, True, P2_COLOR)
        surf.blit(p2_label, p2_label.get_rect(topright=(SCREEN_W - 24, 22)))

    s0, s1 = match.scores
    near_win = max(s0, s1) >= WIN_SCORE - 1
    score_color = (255, 230, 100) if near_win else HUD_COLOR
    score_text = font.render(f"{s0}  -  {s1}", True, score_color)
    surf.blit(score_text, score_text.get_rect(center=(SCREEN_W // 2, 28)))

    time_text = small.render(f"{mins:02d}:{secs:02d}", True, (120, 120, 130))
    target_text = small.render(f"先取{WIN_SCORE}", True, (100, 100, 110))
    sub_w = time_text.get_width() + target_text.get_width() + 12
    sub_x = SCREEN_W // 2 - sub_w // 2
    surf.blit(target_text, (sub_x, 48))
    surf.blit(time_text, (sub_x + target_text.get_width() + 12, 48))

    if bgm_muted:
        mute_text = small.render("BGM OFF (M)", True, (100, 100, 110))
        surf.blit(mute_text, (SCREEN_W - mute_text.get_width() - 12, 48))


def draw_pause(surf: pygame.Surface, hud_font: pygame.font.Font, small: pygame.font.Font) -> None:
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 120))
    surf.blit(overlay, (0, 0))
    pause_t = hud_font.render("ポーズ", True, (255, 255, 255))
    surf.blit(pause_t, pause_t.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 24)))
    hint = small.render("P: 再開    Esc: タイトルへ", True, (180, 180, 190))
    surf.blit(hint, hint.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 16)))


def toggle_fullscreen(screen: pygame.Surface, fullscreen: bool) -> tuple[pygame.Surface, bool]:
    flags = pygame.FULLSCREEN if not fullscreen else 0
    return pygame.display.set_mode((SCREEN_W, SCREEN_H), flags), not fullscreen


def draw_countdown(surf: pygame.Surface, match: Match, big_font: pygame.font.Font) -> None:
    if match.countdown > 0:
        t = big_font.render(str(match.countdown), True, (255, 255, 255))
        surf.blit(t, t.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2)))


def draw_announce(surf: pygame.Surface, match: Match, font: pygame.font.Font) -> None:
    if match.announce_timer > 0 and match.announce:
        t = font.render(match.announce, True, P1_NEON)
        surf.blit(t, t.get_rect(center=(SCREEN_W // 2, TABLE_Y + 40)))


def apply_cpu_difficulty(match: Match, cpu_ai: CPUAI) -> None:
    key = CPU_DIFFICULTY_ORDER[match.cpu_diff_index]
    cpu_ai.set_difficulty(key)
    cpu_ai.reset()


def main() -> None:
    pygame.init()
    pygame.display.set_icon(make_window_icon())
    pygame.display.set_caption(f"{GAME_TITLE} v{VERSION}")
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    init_sprites()
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("meiryo", 52, bold=True)
    body_font = pygame.font.SysFont("meiryo", 20)
    big_font = pygame.font.SysFont("meiryo", 96, bold=True)
    hud_font = pygame.font.SysFont("meiryo", 32, bold=True)
    small_font = pygame.font.SysFont("meiryo", 16)
    announce_font = pygame.font.SysFont("meiryo", 36, bold=True)

    audio: SoundManager | None = None
    if SOUND_ENABLED:
        try:
            audio = SoundManager()
        except pygame.error:
            audio = None

    match = Match(audio=audio)
    if audio is not None:
        audio.play_title_bgm()
    cpu_ai = CPUAI(DEFAULT_CPU_DIFFICULTY)
    title_show_help = False
    running = True
    start_time = time.perf_counter()
    bgm_paused = False
    bgm_muted = False
    fullscreen = False

    while running:
        dt = clock.tick(FPS) / 1000.0
        now = time.perf_counter() - start_time
        keys = pygame.key.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if match.state == GameState.TITLE:
                        if title_show_help:
                            title_show_help = False
                        else:
                            running = False
                    elif match.state == GameState.CPU_DIFF:
                        match.reset_match()
                        title_show_help = False
                    elif match.state == GameState.TIPS:
                        match.enter_countdown()
                        start_time = time.perf_counter()
                    elif match.state == GameState.PAUSE:
                        match.back_to_title()
                        title_show_help = False
                    elif match.state in (GameState.PLAYING, GameState.COUNTDOWN):
                        match.toggle_pause()
                    else:
                        match.back_to_title()
                        title_show_help = False
                elif event.key in (pygame.K_h, pygame.K_SLASH, pygame.K_QUESTION):
                    if match.state == GameState.TITLE:
                        title_show_help = not title_show_help
                elif event.key == pygame.K_f:
                    screen, fullscreen = toggle_fullscreen(screen, fullscreen)
                elif event.key in (pygame.K_UP, pygame.K_w):
                    if match.state == GameState.TITLE:
                        match.title_menu_index = (match.title_menu_index - 1) % 3
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    if match.state == GameState.TITLE:
                        match.title_menu_index = (match.title_menu_index + 1) % 3
                elif event.key in (pygame.K_a, pygame.K_LEFT):
                    if match.state == GameState.CPU_DIFF:
                        match.cpu_diff_index = (match.cpu_diff_index - 1) % 3
                elif event.key in (pygame.K_d, pygame.K_RIGHT):
                    if match.state == GameState.CPU_DIFF:
                        match.cpu_diff_index = (match.cpu_diff_index + 1) % 3
                elif event.key in (pygame.K_3, pygame.K_KP3):
                    if match.state == GameState.CPU_DIFF:
                        match.cpu_diff_index = 0
                elif event.key in (pygame.K_4, pygame.K_KP4):
                    if match.state == GameState.CPU_DIFF:
                        match.cpu_diff_index = 1
                elif event.key in (pygame.K_5, pygame.K_KP5):
                    if match.state == GameState.CPU_DIFF:
                        match.cpu_diff_index = 2
                elif event.key == pygame.K_m:
                    if audio is not None:
                        bgm_muted = audio.toggle_bgm_mute()
                elif event.key == pygame.K_SPACE:
                    if match.state == GameState.TITLE:
                        if match.title_menu_index == 0:
                            match.begin_from_menu(vs_cpu=True)
                            title_show_help = False
                        elif match.title_menu_index == 1:
                            match.begin_from_menu(vs_cpu=False)
                            title_show_help = False
                        else:
                            running = False
                    elif match.state == GameState.CPU_DIFF:
                        apply_cpu_difficulty(match, cpu_ai)
                        match.start_fade_to_tips()
                    elif match.state == GameState.TIPS:
                        tips = tips_for_match(match.vs_cpu)
                        if match.tips_index + 1 >= len(tips):
                            match.enter_countdown()
                            start_time = time.perf_counter()
                        else:
                            match.tips_index += 1
                    elif match.state == GameState.RESULT:
                        match.start_rematch(match.vs_cpu)
                        start_time = time.perf_counter()
                elif event.key == pygame.K_p:
                    if match.state in (GameState.PLAYING, GameState.COUNTDOWN, GameState.PAUSE):
                        match.toggle_pause()

        if match.state not in (GameState.PAUSE, GameState.TITLE, GameState.CPU_DIFF, GameState.TIPS):
            ai = cpu_ai if match.vs_cpu else None
            match.handle_input(keys, dt, now, cpu_ai=ai)
            match.update(dt, now)

        if audio is not None:
            if match.state == GameState.PAUSE and not bgm_paused:
                audio.pause_bgm()
                bgm_paused = True
            elif match.state != GameState.PAUSE and bgm_paused:
                audio.resume_bgm()
                bgm_paused = False
            else:
                audio.set_bgm_for_state(match.state.name)

        if match.state in ARENA_STATES:
            screen.fill(BG_COLOR)
            draw_table(screen)
            for owner in (0, 1):
                player_fences = [f for f in match.fences if f.owner == owner]
                draw_player_fences(screen, player_fences, now, CATERPILLAR_BODY_RADIUS)
            for puck in match.pucks:
                puck.draw(screen, now)
            draw_breach_sparks(screen, match.breach_sparks)
            for paddle in match.paddles:
                paddle.draw(screen, now)
            draw_hud(screen, match, hud_font, small_font, now, bgm_muted=bgm_muted)
            draw_announce(screen, match, announce_font)
            if match.goal_fx is not None:
                draw_goal_celebration(screen, match.goal_fx, announce_font)

        if match.state == GameState.TITLE:
            draw_title_screen(
                screen,
                title_font,
                body_font,
                small_font,
                menu_index=match.title_menu_index,
                show_help=title_show_help,
                now=now,
            )
        elif match.state == GameState.CPU_DIFF:
            draw_cpu_difficulty_screen(
                screen,
                title_font,
                body_font,
                small_font,
                selected_index=match.cpu_diff_index,
            )
        elif match.state == GameState.FADE:
            draw_fade_screen(screen, match.fade_progress)
        elif match.state == GameState.TIPS:
            tips = tips_for_match(match.vs_cpu)
            draw_tips_screen(
                screen,
                title_font,
                body_font,
                small_font,
                tip_index=match.tips_index,
                tip_count=len(tips),
                tip_text=tips[match.tips_index],
                is_last=(match.tips_index + 1 >= len(tips)),
            )
        elif match.state == GameState.COUNTDOWN:
            draw_countdown(screen, match, big_font)
        elif match.state == GameState.PAUSE:
            draw_pause(screen, hud_font, small_font)
        elif match.state == GameState.RESULT:
            draw_result_screen(screen, match, title_font, body_font, small_font, now=now)

        pygame.display.flip()

    if audio is not None:
        audio.stop_bgm()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
