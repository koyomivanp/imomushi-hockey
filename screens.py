"""タイトル・難易度・TIPS などメニュー画面の描画"""

from __future__ import annotations

import math
import random
from typing import Literal

import pygame

from constants import (
    CPU_LABEL,
    LOGO_FILL,
    MENU_BG,
    MENU_BORDER,
    MENU_CARD,
    MENU_CARD_BORDER,
    MENU_PRIMARY_GLOW,
    MENU_TEXT,
    MENU_TEXT_DIM,
    MENU_TITLE_GLOW,
    SCREEN_H,
    SCREEN_W,
    TIPS_BG,
    TIPS_COMMON,
    TIPS_CPU_CONTROLS,
    TIPS_TWO_PLAYER_CONTROLS,
    TITLE_MENU_H,
    TITLE_MENU_GAP,
    TITLE_MENU_TOP,
    TITLE_MENU_W,
)
from ai import CPU_DIFFICULTY_ORDER, DIFFICULTIES
from arena_assets import draw_forest_atmosphere, draw_menu_backdrop, has_rich_backdrop
from caterpillar_art import draw_title_leaf_scene, update_title_demo
from title_typography import (
    TitleFonts,
    blit_catch_copy,
    blit_logo_center,
    render_catch_copy,
    render_tilted_logo,
    render_ui_outlined,
)
from result_flow import ResultPhase, draw_result_dim_overlay, ease_out_back

MenuRole = Literal["primary", "normal", "quit"]

TITLE_MENU_X = (SCREEN_W - TITLE_MENU_W) // 2
_MOSS_HI = (72, 118, 78)
_MOSS_LO = (48, 88, 52)
_BARK = (58, 38, 24)


def _lerp_color(
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _clamp01(t: float) -> float:
    return max(0.0, min(1.0, t))


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


def _moss_speckles(surf: pygame.Surface, rect: pygame.Rect, seed: int, count: int = 8) -> None:
    rng = random.Random(seed)
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    for _ in range(count):
        mx = rng.randint(6, max(7, rect.width - 6))
        my = rng.randint(4, max(5, rect.height - 4))
        col = _MOSS_HI if rng.random() > 0.4 else _MOSS_LO
        pygame.draw.circle(layer, (*col, rng.randint(38, 78)), (mx, my), rng.randint(2, 4))
    surf.blit(layer, rect.topleft)


def _draw_organic_menu_card(
    surf: pygame.Surface,
    rect: pygame.Rect,
    *,
    border_color: tuple[int, int, int] | None = None,
    glow: tuple[int, int, int] | None = None,
    glow_alpha: int = 0,
    seed: int = 0,
) -> None:
    """暗い有機パネル（看板 PNG なし — メニュー／リザルト用）"""
    if glow is not None and glow_alpha > 0:
        _draw_glow_rect(surf, rect, glow, glow_alpha)
    _draw_round_rect(surf, rect, MENU_CARD, radius=14)
    inner = rect.inflate(-6, -6)
    pygame.draw.rect(surf, (18, 32, 22), inner, border_radius=12)
    _moss_speckles(surf, inner, seed or rect.x * 17 + rect.y, count=6)
    pygame.draw.rect(surf, border_color or MENU_CARD_BORDER, rect, 2, border_radius=14)


def _draw_selection_glow(
    surf: pygame.Surface,
    rect: pygame.Rect,
    *,
    strength: float,
    now: float,
    color: tuple[int, int, int] = MENU_PRIMARY_GLOW,
) -> None:
    if strength <= 0.03:
        return
    pulse = 0.55 + 0.45 * math.sin(now * 5.2)
    for expand, alpha_mult in ((10, 0.38), (20, 0.22), (32, 0.12)):
        glow = pygame.Surface((rect.width + expand * 2, rect.height + expand * 2), pygame.SRCALPHA)
        inner = pygame.Rect(expand, expand, rect.width, rect.height)
        alpha = int((72 + 48 * pulse) * strength * alpha_mult)
        pygame.draw.rect(glow, (*color, alpha), inner, border_radius=14)
        surf.blit(glow, (rect.x - expand, rect.y - expand))


def _draw_organic_menu_button(
    surf: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    *,
    selected: bool = False,
    sel_strength: float | None = None,
    now: float = 0.0,
) -> None:
    s = _clamp01(sel_strength if sel_strength is not None else (1.0 if selected else 0.0))
    pulse = 0.5 + 0.5 * math.sin(now * 5.0)
    scale = 1.0 + 0.07 * s * (0.82 + 0.18 * pulse)
    draw_rect = rect.copy()
    if s > 0.02:
        grow_w = int(rect.width * (scale - 1.0))
        grow_h = int(rect.height * (scale - 1.0))
        draw_rect.inflate_ip(grow_w, grow_h)
        draw_rect.center = rect.center

    _draw_selection_glow(surf, draw_rect, strength=s, now=now)

    fill = _lerp_color((28, 44, 30), (42, 58, 44), s)
    border_col = _lerp_color(MENU_CARD_BORDER, MENU_BORDER, s)
    border_w = max(1, int(1 + s * 2.5))
    pygame.draw.rect(surf, fill, draw_rect, border_radius=12)
    pygame.draw.rect(surf, border_col, draw_rect, border_w, border_radius=12)

    if s > 0.12:
        bar_w = max(3, int(3 + 3 * s))
        bar_h = max(8, draw_rect.height - 16)
        bar = pygame.Rect(draw_rect.x + 7, draw_rect.centery - bar_h // 2, bar_w, bar_h)
        bar_col = _lerp_color(MENU_BORDER, MENU_TITLE_GLOW, 0.35 + 0.65 * s * pulse)
        pygame.draw.rect(surf, bar_col, bar, border_radius=3)
        shine = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(shine, (255, 255, 255, int(28 * s * pulse)), shine.get_rect(), border_radius=3)
        surf.blit(shine, bar.topleft)

    text_color = _lerp_color(MENU_TEXT_DIM, LOGO_FILL, s)
    if s > 0.55:
        text = render_ui_outlined(label, font, text_color, outline=_BARK, outline_px=2)
    else:
        text = font.render(label, True, text_color)
    if s < 1.0:
        text = text.copy()
        text.set_alpha(int(180 + 75 * s))
    surf.blit(text, text.get_rect(center=draw_rect.center))


def _draw_title_menu_button(
    surf: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    *,
    selected: bool,
    sel_strength: float | None = None,
    role: MenuRole,
    now: float,
) -> None:
    _ = role
    _draw_organic_menu_button(
        surf, rect, label, font,
        selected=selected, sel_strength=sel_strength, now=now,
    )


def _draw_title_logo_center(surf: pygame.Surface, fonts: TitleFonts, now: float) -> pygame.Rect:
    logo, line1_anchor = render_tilted_logo("芋虫", "ホッケー", fonts, now=now)
    logo_rect = blit_logo_center(surf, logo)
    catch = render_catch_copy(fonts)
    blit_catch_copy(surf, catch, line1_anchor)
    return logo_rect


def _draw_title_dapple_light(surf: pygame.Surface, now: float) -> None:
    """タイトル背景 — 木漏れ日の斑点（PNG 未配置時のみ）"""
    if has_rich_backdrop():
        return
    layer = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    spots = (
        (180, 280, 38, 22), (620, 320, 32, 18), (400, 380, 48, 14),
        (260, 420, 28, 16), (540, 400, 36, 12),
    )
    for i, (sx, sy, sr, base_a) in enumerate(spots):
        pulse = 0.7 + 0.3 * math.sin(now * 0.6 + i * 1.4)
        alpha = int(base_a * pulse)
        pygame.draw.circle(layer, (118, 168, 102, alpha), (sx, sy), sr)
    surf.blit(layer, (0, 0))



def tips_for_match(vs_cpu: bool) -> tuple[str, ...]:
    _ = vs_cpu
    return TIPS_COMMON


def pick_random_tip(vs_cpu: bool) -> str:
    return random.choice(tips_for_match(vs_cpu))


def draw_title_screen(
    surf: pygame.Surface,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
    *,
    menu_index: int,
    menu_sel_strengths: tuple[float, float, float] | None = None,
    title_fonts: TitleFonts | None = None,
    cpu_diff_index: int = 1,
    now: float = 0.0,
    dt: float = 0.0,
) -> None:
    fonts = title_fonts
    if fonts is None:
        from title_typography import load_title_fonts
        fonts = load_title_fonts()

    draw_menu_backdrop(surf, now)
    _draw_title_dapple_light(surf, now)
    if dt > 0.0:
        update_title_demo(dt, now)
    draw_title_leaf_scene(surf, now)
    _draw_title_logo_center(surf, fonts, now)

    labels = (f"vs {CPU_LABEL}", "2芋虫対戦", "終了")
    roles: tuple[MenuRole, ...] = ("normal", "normal", "normal")
    for i, (label, role) in enumerate(zip(labels, roles)):
        y = TITLE_MENU_TOP + i * (TITLE_MENU_H + TITLE_MENU_GAP)
        rect = pygame.Rect(TITLE_MENU_X, y, TITLE_MENU_W, TITLE_MENU_H)
        strength = menu_sel_strengths[i] if menu_sel_strengths is not None else None
        _draw_title_menu_button(
            surf, rect, label, fonts.menu,
            selected=(menu_index == i),
            sel_strength=strength,
            role=role,
            now=now,
        )


def _draw_menu_button(
    surf: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    *,
    selected: bool,
    now: float = 0.0,
) -> None:
    _draw_organic_menu_button(
        surf, rect, label, font, selected=selected, now=now,
    )


def draw_cpu_difficulty_screen(
    surf: pygame.Surface,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
    *,
    selected_index: int,
    cpu_sel_strengths: tuple[float, float, float] | None = None,
    now: float = 0.0,
    title_fonts: TitleFonts | None = None,
    morph_progress: float = 1.0,
) -> None:
    from cpu_diff_morph import draw_cpu_diff_morph

    fonts = title_fonts
    if fonts is None:
        from title_typography import load_title_fonts
        fonts = load_title_fonts()

    draw_menu_backdrop(surf, now)
    _draw_title_dapple_light(surf, now)

    fade = max(0.0, 1.0 - morph_progress * 1.6)
    if fade > 0.02:
        _draw_title_logo_center(surf, fonts, now)
        if fade < 1.0:
            veil = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            veil.fill((6, 14, 8, int(200 * (1.0 - fade))))
            surf.blit(veil, (0, 0))

    draw_cpu_diff_morph(
        surf,
        fonts,
        selected_index=selected_index,
        sel_strengths=cpu_sel_strengths,
        progress=morph_progress,
        now=now,
    )


def draw_fade_screen(surf: pygame.Surface, progress: float, now: float = 0.0) -> None:
    if has_rich_backdrop():
        draw_menu_backdrop(surf, now)
        fade_top = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        fade_top.fill((*_lerp_color(MENU_BG, TIPS_BG, min(1.0, progress * 1.2)), int(72 * progress)))
        surf.blit(fade_top, (0, 0))
        return

    color = _lerp_color(MENU_BG, TIPS_BG, progress)
    surf.fill(color)
    draw_forest_atmosphere(surf, now, battle=False)

    veil = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    vignette_a = int(28 + 52 * progress)
    for i in range(4):
        margin = i * 32
        alpha = vignette_a + i * 8
        pygame.draw.rect(
            veil, (4, 10, 6, alpha),
            pygame.Rect(margin, margin, SCREEN_W - margin * 2, SCREEN_H - margin * 2),
            width=18,
        )
    surf.blit(veil, (0, 0))

    firefly_layer = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for i in range(6):
        fx = int(SCREEN_W * (0.15 + 0.7 * ((i * 0.17 + progress * 0.3) % 1.0)))
        fy = int(SCREEN_H * (0.2 + 0.6 * ((i * 0.23 + now * 0.05) % 1.0)))
        glow = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(now * 2.0 + i * 1.7))
        if glow < 0.5:
            continue
        c = (int(168 * glow), int(210 * glow), int(98 * glow), int(90 * (1.0 - progress * 0.5)))
        pygame.draw.circle(firefly_layer, c, (fx, fy), 2)
    surf.blit(firefly_layer, (0, 0))

    fade_top = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    fade_top.fill((*_lerp_color(MENU_BG, TIPS_BG, min(1.0, progress * 1.2)), int(60 * progress)))
    surf.blit(fade_top, (0, 0))


def _tip_category(tip_text: str) -> str:
    if tip_text in (TIPS_CPU_CONTROLS, TIPS_TWO_PLAYER_CONTROLS):
        return "操作"
    if tip_text == TIPS_COMMON[-1]:
        return "テクニック"
    return "ルール"


def _wrap_text(text: str, font: pygame.font.Font, max_w: int) -> list[str]:
    if font.size(text)[0] <= max_w:
        return [text]
    lines: list[str] = []
    chunk = ""
    for ch in text:
        trial = chunk + ch
        if font.size(trial)[0] > max_w:
            if chunk:
                lines.append(chunk)
            chunk = ch
        else:
            chunk = trial
    if chunk:
        lines.append(chunk)
    return lines


def _draw_tips_subtitle_veil(surf: pygame.Surface, now: float) -> None:
    """木漏れ日の字幕用 — 縁を落とし中央に柔らかい光"""
    layer = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for i in range(7):
        margin = 10 + i * 26
        alpha = 12 + i * 14
        pygame.draw.rect(
            layer, (2, 6, 4, alpha),
            pygame.Rect(margin, margin, SCREEN_W - margin * 2, SCREEN_H - margin * 2),
            width=22,
        )

    pulse = 0.82 + 0.18 * math.sin(now * 0.55)
    cx, cy = SCREEN_W // 2, SCREEN_H // 2 - 12
    for r in range(210, 0, -7):
        t = 1.0 - r / 210.0
        alpha = int((14 + 26 * t) * pulse)
        pygame.draw.circle(layer, (92, 142, 82, alpha), (cx, cy), r)

    spots = (
        (280, 198, 52, 16), (520, 228, 44, 12), (360, 268, 64, 10),
    )
    for i, (sx, sy, sr, base_a) in enumerate(spots):
        flicker = 0.65 + 0.35 * math.sin(now * 0.7 + i * 1.3)
        pygame.draw.circle(
            layer, (148, 198, 112, int(base_a * flicker)),
            (sx, sy), sr,
        )
    surf.blit(layer, (0, 0))


def _tips_enter_ease(tips_timer: float | None) -> tuple[float, int]:
    """表示開始からの入場（0=開始直後, 1=完了）と alpha"""
    if tips_timer is None:
        return 1.0, 255
    from constants import TIPS_DISPLAY_DURATION

    elapsed = max(0.0, TIPS_DISPLAY_DURATION - tips_timer)
    t = min(1.0, elapsed / 0.45)
    ease = 1.0 - (1.0 - t) ** 3
    return ease, int(255 * ease)


def draw_tips_overlay(
    surf: pygame.Surface,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
    *,
    tip_text: str,
    tips_alpha: float,
) -> None:
    """蝶の暗幕の上に TIPS テキストだけ重ねる"""
    if tips_alpha <= 0.0:
        return

    alpha = int(255 * max(0.0, min(1.0, tips_alpha)))
    y_shift = int((1.0 - tips_alpha) * 12)

    category = _tip_category(tip_text)
    prefix = small_font.render(f"{category} —", True, MENU_TITLE_GLOW)
    prefix.set_alpha(alpha)

    lines = _wrap_text(tip_text, body_font, 520)
    line_surfs: list[pygame.Surface] = []
    for line in lines:
        outlined = render_ui_outlined(
            line, body_font, LOGO_FILL, outline=_BARK, outline_px=2,
        )
        outlined.set_alpha(alpha)
        line_surfs.append(outlined)

    line_gap = 10
    block_h = prefix.get_height() + 18
    for s in line_surfs:
        block_h += s.get_height() + line_gap
    if line_surfs:
        block_h -= line_gap

    top_y = SCREEN_H // 2 - block_h // 2 + y_shift
    surf.blit(prefix, prefix.get_rect(midtop=(SCREEN_W // 2, top_y)))

    y = top_y + prefix.get_height() + 18
    for s in line_surfs:
        surf.blit(s, s.get_rect(midtop=(SCREEN_W // 2, y)))
        y += s.get_height() + line_gap


def draw_tips_screen(
    surf: pygame.Surface,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
    *,
    tip_text: str,
    now: float = 0.0,
    tip_index: int = 0,
    tip_count: int = 5,
    tips_timer: float | None = None,
) -> None:
    _ = title_font, tip_index, tip_count
    draw_menu_backdrop(surf, now)
    _draw_tips_subtitle_veil(surf, now)

    ease, alpha = _tips_enter_ease(tips_timer)
    y_shift = int((1.0 - ease) * 16)

    category = _tip_category(tip_text)
    prefix = small_font.render(f"{category} —", True, MENU_TITLE_GLOW)
    prefix.set_alpha(alpha)

    lines = _wrap_text(tip_text, body_font, 520)
    line_surfs: list[pygame.Surface] = []
    for line in lines:
        outlined = render_ui_outlined(
            line, body_font, LOGO_FILL, outline=_BARK, outline_px=2,
        )
        outlined.set_alpha(alpha)
        line_surfs.append(outlined)

    line_gap = 10
    block_h = prefix.get_height() + 18
    for s in line_surfs:
        block_h += s.get_height() + line_gap
    if line_surfs:
        block_h -= line_gap

    top_y = SCREEN_H // 2 - block_h // 2 + y_shift
    surf.blit(prefix, prefix.get_rect(midtop=(SCREEN_W // 2, top_y)))

    y = top_y + prefix.get_height() + 18
    for s in line_surfs:
        surf.blit(s, s.get_rect(midtop=(SCREEN_W // 2, y)))
        y += s.get_height() + line_gap


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
    result_phase = getattr(match, "result_phase", ResultPhase.HOLD)
    dimness = getattr(match, "result_dimness", 1.0)
    card_alpha = getattr(match, "result_card_alpha", 1.0)

    if result_phase == ResultPhase.CELEBRATE and dimness <= 0.01 and card_alpha <= 0.01:
        return

    if dimness > 0.01:
        draw_result_dim_overlay(surf, dimness)

    if card_alpha <= 0.01:
        return

    if match.winner is None:
        celebrate = False
    elif match.vs_cpu:
        celebrate = match.winner == 0
    else:
        celebrate = True

    if celebrate and match.winner is not None:
        warm = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        warm.fill((118, 168, 102, int(28 * card_alpha)))
        surf.blit(warm, (0, 0))

    overlay_tint = (22, 40, 18, int(195 * card_alpha)) if celebrate else (6, 12, 8, int(210 * card_alpha))
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill(overlay_tint)
    surf.blit(overlay, (0, 0))
    draw_forest_atmosphere(surf, now, battle=True, include_fireflies=celebrate)

    mins = int(match.match_time) // 60
    secs = int(match.match_time) % 60
    headline = result_headline(match)
    pulse = 0.88 + 0.12 * math.sin(now * 2.0)

    card_w, card_h = 540, 250
    slide = int((1.0 - ease_out_back(card_alpha)) * 28)
    card = pygame.Rect(
        SCREEN_W // 2 - card_w // 2,
        SCREEN_H // 2 - card_h // 2 + slide,
        card_w,
        card_h,
    )
    border_col = MENU_BORDER if celebrate and match.winner is not None else MENU_CARD_BORDER
    glow_a = int((48 + 32 * pulse) * card_alpha) if celebrate and match.winner is not None else 0
    _draw_organic_menu_card(
        surf,
        card,
        border_color=border_col,
        glow=MENU_PRIMARY_GLOW if celebrate and match.winner is not None else None,
        glow_alpha=glow_a,
        seed=card.centerx,
    )

    if match.winner is None:
        title_color = MENU_TEXT_DIM
        title_font_use = title_font
    elif celebrate:
        title_color = tuple(int(c * pulse) for c in MENU_TITLE_GLOW)
        title_font_use = title_font
    else:
        title_color = (88, 108, 82)
        title_font_use = title_font

    title = render_ui_outlined(
        headline, title_font_use, title_color, outline=_BARK,
        outline_px=4 if celebrate else 3,
    )
    title.set_alpha(int(255 * card_alpha))
    title_y = card.centery - 52 if celebrate else card.centery - 48
    surf.blit(title, title.get_rect(center=(SCREEN_W // 2, title_y)))

    s0, s1 = match.scores
    score_line = body_font.render(f"{s0}  -  {s1}", True, MENU_TEXT if celebrate else MENU_TEXT_DIM)
    score_line.set_alpha(int(255 * card_alpha))
    surf.blit(score_line, score_line.get_rect(center=(SCREEN_W // 2, card.centery - 4)))

    time_col = MENU_TEXT if celebrate else MENU_TEXT_DIM
    time_line = small_font.render(f"試合時間 {mins:02d}:{secs:02d}", True, time_col)
    time_line.set_alpha(int(255 * card_alpha))
    surf.blit(time_line, time_line.get_rect(center=(SCREEN_W // 2, card.centery + 28)))

    hint = small_font.render("Space: もう一度    Esc: タイトル", True, MENU_TEXT_DIM)
    hint.set_alpha(int(200 * card_alpha))
    surf.blit(hint, hint.get_rect(center=(SCREEN_W // 2, card.centery + 62)))
