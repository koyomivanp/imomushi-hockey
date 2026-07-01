"""タイトル・難易度・TIPS などメニュー画面の描画"""

from __future__ import annotations

import math
from typing import Literal

import pygame

from constants import (
    CPU_LABEL,
    MENU_BG,
    MENU_BORDER,
    MENU_CARD,
    MENU_CARD_BORDER,
    MENU_PRIMARY,
    MENU_PRIMARY_FILL,
    MENU_PRIMARY_GLOW,
    MENU_SELECT,
    MENU_TEXT,
    MENU_TEXT_DIM,
    MENU_TITLE_GLOW,
    P1_LABEL,
    P2_LABEL,
    SCREEN_H,
    SCREEN_W,
    TIPS_BG,
    TIPS_COMMON,
    TIPS_CPU_CONTROLS,
    TIPS_TWO_PLAYER_CONTROLS,
    TITLE_CONTENT_W,
    TITLE_MENU_MARGIN,
    TITLE_MENU_W,
)
from ai import CPU_DIFFICULTY_ORDER, DIFFICULTIES
from caterpillar_art import draw_title_leaf_scene

MenuRole = Literal["primary", "normal", "quit"]

TITLE_LOGO_LEFT = 44
TITLE_MENU_X = SCREEN_W - TITLE_MENU_W - TITLE_MENU_MARGIN
TITLE_MENU_H = 50
TITLE_MENU_GAP = 14
TITLE_MENU_TOP = (SCREEN_H - (TITLE_MENU_H * 3 + TITLE_MENU_GAP * 2)) // 2


def _lerp_color(
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_round_rect(
    surf: pygame.Surface,
    rect: pygame.Rect,
    color: tuple[int, int, int],
    *,
    radius: int = 12,
    border: int = 0,
    border_color: tuple[int, int, int] | None = None,
) -> None:
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    if border > 0 and border_color is not None:
        pygame.draw.rect(surf, border_color, rect, border, border_radius=radius)


def _draw_glow_rect(surf: pygame.Surface, rect: pygame.Rect, color: tuple[int, int, int], alpha: int) -> None:
    glow = pygame.Surface((rect.width + 16, rect.height + 16), pygame.SRCALPHA)
    inner = pygame.Rect(8, 8, rect.width, rect.height)
    pygame.draw.rect(glow, (*color, alpha), inner, border_radius=12)
    surf.blit(glow, (rect.x - 8, rect.y - 8))


def _draw_title_menu_button(
    surf: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    *,
    selected: bool,
    role: MenuRole,
    now: float,
) -> None:
    if role == "quit":
        if selected:
            pygame.draw.rect(surf, (38, 58, 42), rect, 1, border_radius=8)
            text_color = MENU_TEXT_DIM
        else:
            text_color = (72, 88, 68)
        text = font.render(label, True, text_color)
        surf.blit(text, text.get_rect(center=rect.center))
        return

    if role == "primary":
        pulse = 0.85 + 0.15 * math.sin(now * 2.2)
        fill = MENU_PRIMARY_FILL if not selected else tuple(
            int(MENU_PRIMARY_FILL[i] + (MENU_PRIMARY[i] - MENU_PRIMARY_FILL[i]) * 0.55) for i in range(3)
        )
        border_c = MENU_PRIMARY if selected else MENU_BORDER
        if selected:
            glow_a = int(55 + 35 * pulse)
            _draw_glow_rect(surf, rect, MENU_PRIMARY_GLOW, glow_a)
        _draw_round_rect(surf, rect, fill, radius=10, border=2, border_color=border_c)
        text_color = MENU_TEXT
    else:
        if selected:
            _draw_glow_rect(surf, rect, MENU_BORDER, 28)
            _draw_round_rect(surf, rect, MENU_SELECT, radius=10, border=2, border_color=MENU_BORDER)
            text_color = MENU_TEXT
        else:
            pygame.draw.rect(surf, (42, 62, 46), rect, 1, border_radius=10)
            text_color = MENU_TEXT_DIM

    text = font.render(label, True, text_color)
    surf.blit(text, text.get_rect(center=rect.center))


def _draw_forest_atmosphere(surf: pygame.Surface, now: float) -> None:
    vignette = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for i in range(6):
        alpha = int(28 + i * 10)
        margin = i * 28
        pygame.draw.rect(
            vignette, (4, 10, 6, alpha),
            pygame.Rect(margin, margin, SCREEN_W - margin * 2, SCREEN_H - margin * 2),
            width=24,
        )
    surf.blit(vignette, (0, 0))

    firefly_pts = (
        (200, 260), (320, 300), (360, 400), (180, 420), (300, 460), (240, 340),
    )
    for i, (fx, fy) in enumerate(firefly_pts):
        glow = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(now * 1.8 + i * 1.1))
        if glow < 0.45:
            continue
        c = (int(168 * glow), int(210 * glow), int(98 * glow))
        pygame.draw.circle(surf, c, (fx, fy), 2)


def _draw_title_logo_left(surf: pygame.Surface, font: pygame.font.Font, now: float) -> None:
    """左上 — 2行ロゴ"""
    x = TITLE_LOGO_LEFT
    y0 = 52
    pulse = 0.88 + 0.12 * math.sin(now * 1.4)
    glow_c = tuple(int(c * pulse) for c in MENU_TITLE_GLOW)
    shadow_c = (6, 12, 8)
    line1, line2 = "芋虫", "ホッケー"

    base_px = font.get_height()
    logo_fonts = (
        font,
        pygame.font.SysFont("meiryo", int(base_px * 1.12), bold=True),
    )

    for dy, text, font_idx in ((0, line1, 0), (52, line2, 1)):
        cy = y0 + dy
        big = logo_fonts[font_idx]
        for dx, offy, color in ((2, 3, shadow_c), (0, 0, glow_c), (0, 0, MENU_TEXT)):
            t = big.render(text, True, color)
            surf.blit(t, (x + dx, cy + offy))

    line_y = y0 + 108
    pygame.draw.line(surf, glow_c, (x, line_y), (x + 120, line_y), 2)


def _draw_panel_divider(surf: pygame.Surface) -> None:
    """左イラストと右メニューの境"""
    x = TITLE_CONTENT_W - 8
    fade = pygame.Surface((28, SCREEN_H), pygame.SRCALPHA)
    for i in range(28):
        alpha = int(22 * (1.0 - i / 27))
        pygame.draw.line(fade, (60, 100, 68, alpha), (i, 0), (i, SCREEN_H))
    surf.blit(fade, (x, 0))


def _draw_right_menu_panel(surf: pygame.Surface) -> None:
    """右パネル — ボタンが読みやすいよう薄い暗幕"""
    panel = pygame.Surface((SCREEN_W - TITLE_CONTENT_W, SCREEN_H), pygame.SRCALPHA)
    panel.fill((8, 16, 10, 72))
    surf.blit(panel, (TITLE_CONTENT_W, 0))


def tips_for_match(vs_cpu: bool) -> tuple[str, ...]:
    last = TIPS_CPU_CONTROLS if vs_cpu else TIPS_TWO_PLAYER_CONTROLS
    return TIPS_COMMON + (last,)


def draw_title_screen(
    surf: pygame.Surface,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
    *,
    menu_index: int,
    show_help: bool,
    now: float = 0.0,
) -> None:
    surf.fill(MENU_BG)
    _draw_forest_atmosphere(surf, now)
    draw_title_leaf_scene(surf, now)
    _draw_right_menu_panel(surf)
    _draw_panel_divider(surf)
    _draw_title_logo_left(surf, title_font, now)

    labels = (f"vs {CPU_LABEL}", "2芋虫対戦", "終了")
    roles: tuple[MenuRole, ...] = ("primary", "normal", "quit")
    for i, (label, role) in enumerate(zip(labels, roles)):
        y = TITLE_MENU_TOP + i * (TITLE_MENU_H + TITLE_MENU_GAP)
        rect = pygame.Rect(TITLE_MENU_X, y, TITLE_MENU_W, TITLE_MENU_H)
        _draw_title_menu_button(
            surf, rect, label, body_font,
            selected=(menu_index == i), role=role, now=now,
        )

    if show_help:
        draw_help_overlay(surf, title_font, small_font)


def _draw_menu_button(
    surf: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    *,
    selected: bool,
) -> None:
    if selected:
        _draw_round_rect(surf, rect, MENU_SELECT, radius=10, border=2, border_color=MENU_BORDER)
        text_color = MENU_TEXT
    else:
        pygame.draw.rect(surf, (48, 72, 52), rect, 1, border_radius=10)
        text_color = MENU_TEXT_DIM
    text = font.render(label, True, text_color)
    surf.blit(text, text.get_rect(center=rect.center))


def draw_cpu_difficulty_screen(
    surf: pygame.Surface,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
    *,
    selected_index: int,
) -> None:
    surf.fill(TIPS_BG)
    heading = title_font.render("CPUの強さ", True, MENU_TEXT)
    surf.blit(heading, heading.get_rect(center=(400, 200)))

    btn_w, btn_h, gap = 140, 52, 16
    total_w = btn_w * 3 + gap * 2
    start_x = 400 - total_w // 2
    y = 268
    for i, key in enumerate(CPU_DIFFICULTY_ORDER):
        rect = pygame.Rect(start_x + i * (btn_w + gap), y, btn_w, btn_h)
        _draw_menu_button(
            surf, rect, DIFFICULTIES[key].label, body_font, selected=(i == selected_index),
        )

    hint = small_font.render("A D で選択　Space 決定　Esc で戻る", True, MENU_TEXT_DIM)
    surf.blit(hint, hint.get_rect(center=(400, 380)))


def draw_fade_screen(surf: pygame.Surface, progress: float) -> None:
    color = _lerp_color(MENU_BG, TIPS_BG, progress)
    surf.fill(color)


def draw_tips_screen(
    surf: pygame.Surface,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
    *,
    tip_index: int,
    tip_count: int,
    tip_text: str,
    is_last: bool,
) -> None:
    surf.fill(TIPS_BG)
    label = small_font.render("ヒント", True, MENU_TEXT_DIM)
    surf.blit(label, label.get_rect(center=(400, 200)))

    words = tip_text
    lines: list[str] = []
    max_w = 520
    if body_font.size(words)[0] <= max_w:
        lines = [words]
    else:
        chunk = ""
        for ch in words:
            trial = chunk + ch
            if body_font.size(trial)[0] > max_w:
                if chunk:
                    lines.append(chunk)
                chunk = ch
            else:
                chunk = trial
        if chunk:
            lines.append(chunk)

    y = 248 - (len(lines) * 14)
    for line in lines:
        t = body_font.render(line, True, MENU_TEXT)
        surf.blit(t, t.get_rect(center=(400, y)))
        y += 28

    footer = "Space で開始" if is_last else f"Space で次へ（{tip_index + 1} / {tip_count}）"
    foot = small_font.render(footer, True, MENU_TEXT_DIM)
    surf.blit(foot, foot.get_rect(center=(400, 400)))


def result_headline(match) -> str:
    if match.winner is None:
        return "引き分け"
    if match.vs_cpu and match.winner == 0:
        return "あなたの芋虫の勝ち！"
    if match.vs_cpu and match.winner == 1:
        return f"{CPU_LABEL}の勝ち！"
    return f"P{match.winner + 1}芋虫の勝ち！"


def draw_result_screen(
    surf: pygame.Surface,
    match,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
    *,
    now: float = 0.0,
) -> None:
    """対戦コートの上に森テーマのリザルトカードを重ねる"""
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((8, 16, 10, 175))
    surf.blit(overlay, (0, 0))

    mins = int(match.match_time) // 60
    secs = int(match.match_time) % 60
    headline = result_headline(match)
    if match.winner is None:
        celebrate = False
    elif match.vs_cpu:
        celebrate = match.winner == 0
    else:
        celebrate = True
    pulse = 0.88 + 0.12 * math.sin(now * 2.0)

    card_w, card_h = 520, 236
    card = pygame.Rect(
        SCREEN_W // 2 - card_w // 2,
        SCREEN_H // 2 - card_h // 2,
        card_w,
        card_h,
    )
    if celebrate and match.winner is not None:
        glow_a = int(42 + 28 * pulse)
        _draw_glow_rect(surf, card, MENU_PRIMARY_GLOW, glow_a)
    _draw_round_rect(surf, card, MENU_CARD, radius=14, border=2, border_color=MENU_CARD_BORDER)

    if match.winner is None:
        title_color = MENU_TEXT_DIM
    elif celebrate:
        title_color = tuple(int(c * pulse) for c in MENU_TITLE_GLOW)
    else:
        title_color = MENU_TEXT_DIM

    title = title_font.render(headline, True, title_color)
    surf.blit(title, title.get_rect(center=(SCREEN_W // 2, card.centery - 52)))

    score = body_font.render(f"{match.scores[0]}  -  {match.scores[1]}", True, MENU_TEXT)
    surf.blit(score, score.get_rect(center=(SCREEN_W // 2, card.centery - 8)))

    time_line = small_font.render(f"試合時間 {mins:02d}:{secs:02d}", True, MENU_TEXT_DIM)
    surf.blit(time_line, time_line.get_rect(center=(SCREEN_W // 2, card.centery + 28)))

    hint = small_font.render("Space: もう一度    Esc: タイトルへ", True, MENU_TEXT_DIM)
    surf.blit(hint, hint.get_rect(center=(SCREEN_W // 2, card.centery + 58)))


def draw_help_overlay(surf: pygame.Surface, font: pygame.font.Font, small: pygame.font.Font) -> None:
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 210))
    surf.blit(overlay, (0, 0))

    title = font.render("操作説明", True, MENU_TEXT)
    surf.blit(title, title.get_rect(center=(SCREEN_W // 2, 72)))

    lines = [
        "【ルール】先取3点で勝ち。葉っぱを相手ゴールへ。",
        "【体節】這うと体節が壁になる。古い体節から消える。",
        "【ダッシュ】Shift+移動で高速移動。体節は出ず、壁をすり抜ける。",
        "【貫通】ダッシュで葉っぱを打った直後だけ、体節を勢いよく抜ける。",
        "",
        f"{P1_LABEL}（左）: WASD 移動 / Shift+移動でダッシュ",
        f"{P2_LABEL}（右）: 矢印キー / Shift+移動でダッシュ",
        f"CPU対戦: WASD 移動 / Shift は左右どちらでも",
        "",
        "タイトル: ↑↓ 選択  Space 決定  H 説明",
        "対戦中: P/Esc ポーズ  M BGM  F 全画面",
        "",
        "H または Esc で閉じる",
    ]
    y = 118
    for line in lines:
        color = MENU_TEXT_DIM if line else (0, 0, 0, 0)
        if line.startswith("【貫通】"):
            color = MENU_TITLE_GLOW
        if line:
            t = small.render(line, True, color)
            surf.blit(t, t.get_rect(center=(SCREEN_W // 2, y)))
        y += 22
