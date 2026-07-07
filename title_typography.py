"""タイトル画面用タイポグラフィ（木目ベージュ・焦げ茶アウトライン・ホタルグロー）"""



from __future__ import annotations



import math

import sys

from dataclasses import dataclass

from pathlib import Path



import pygame



from constants import (

    HUD_TEXT_OUTLINE,

    LOGO_FILL,

    LOGO_GLOW,

    LOGO_OUTLINE,

    TITLE_CATCH_COPY,

    TITLE_CATCH_GAP,

    TITLE_HOCKEY_SCALE,

    TITLE_LOGO_CENTER,

    TITLE_LOGO_TILT_DEG,

)



_ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

_FONT_CANDIDATES = (
    "ZenMaruGothic-Bold.ttf",
    "ZenMaruGothic-Medium.ttf",
)

_SYS_FONT_CANDIDATES = (
    "Zen Maru Gothic",
    "Rounded Mplus 1c",
    "M PLUS Rounded 1c",
    "BIZ UDGothic",
    "Yu Gothic UI",
    "Meiryo UI",
    "Meiryo",
)





def _asset_root() -> Path:

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):

        return Path(sys._MEIPASS) / "assets" / "fonts"

    return _ASSETS_DIR





def _find_font_file() -> Path | None:

    root = _asset_root()

    for name in _FONT_CANDIDATES:

        path = root / name

        if path.is_file():

            return path

    return None





def _load_font(size: int, *, bold: bool = False, medium: bool = False) -> pygame.font.Font:

    root = _asset_root()

    if medium:

        path = root / "ZenMaruGothic-Medium.ttf"

        if path.is_file():

            return pygame.font.Font(str(path), size)

    path = _find_font_file()

    if path is not None:

        return pygame.font.Font(str(path), size)

    return pygame.font.SysFont(_SYS_FONT_CANDIDATES, size, bold=bold)





@dataclass(frozen=True)

class TitleFonts:

    logo_line1: pygame.font.Font

    logo_line2: pygame.font.Font

    catch_copy: pygame.font.Font

    menu: pygame.font.Font

    menu_preview: pygame.font.Font

    screen_title: pygame.font.Font

    screen_body: pygame.font.Font

    screen_small: pygame.font.Font

    hud_score: pygame.font.Font

    hud_label: pygame.font.Font

    hud_meta: pygame.font.Font





def load_title_fonts() -> TitleFonts:

    return TitleFonts(

        logo_line1=_load_font(52),

        logo_line2=_load_font(int(52 * TITLE_HOCKEY_SCALE)),

        catch_copy=_load_font(13, medium=True),

        menu=_load_font(20),

        menu_preview=_load_font(17),

        screen_title=_load_font(52, bold=True),

        screen_body=_load_font(20),

        screen_small=_load_font(16),

        hud_score=_load_font(30),

        hud_label=_load_font(21, medium=True),

        hud_meta=_load_font(13, medium=True),

    )





def render_wood_text(

    text: str,

    font: pygame.font.Font,

    *,

    fill: tuple[int, int, int] = LOGO_FILL,

    outline: tuple[int, int, int] = LOGO_OUTLINE,

    outline_px: int = 4,

) -> pygame.Surface:

    base = font.render(text, True, fill)

    w, h = base.get_size()

    pad = outline_px + 3

    surf = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)

    ox, oy = pad, pad

    for dx in range(-outline_px, outline_px + 1):

        for dy in range(-outline_px, outline_px + 1):

            if dx * dx + dy * dy > outline_px * outline_px + outline_px:

                continue

            layer = font.render(text, True, outline)

            surf.blit(layer, (ox + dx, oy + dy))

    surf.blit(base, (ox, oy))

    return surf





def render_ui_outlined(

    text: str,

    font: pygame.font.Font,

    fill: tuple[int, int, int],

    *,

    outline: tuple[int, int, int] = HUD_TEXT_OUTLINE,

    outline_px: int = 2,

) -> pygame.Surface:

    """HUD 用 — 細めのアウトライン付きテキスト"""

    return render_wood_text(text, font, fill=fill, outline=outline, outline_px=outline_px)





def _tint_for_glow(src: pygame.Surface, color: tuple[int, int, int], alpha: int) -> pygame.Surface:

    """文字のアルファ形状だけを保ち、ホタル色に着色する"""

    tinted = src.copy()

    tinted.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)

    tinted.set_alpha(alpha)

    return tinted





def render_firefly_glow(src: pygame.Surface, color: tuple[int, int, int] = LOGO_GLOW) -> pygame.Surface:

    w, h = src.get_size()

    pad = 18

    glow = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)

    for dist, alpha in ((7, 18), (5, 30), (3, 44)):

        for dx in range(-dist, dist + 1, 2):

            for dy in range(-dist, dist + 1, 2):

                if dx * dx + dy * dy > dist * dist:

                    continue

                layer = _tint_for_glow(src, color, alpha)

                glow.blit(layer, (pad + dx, pad + dy), special_flags=pygame.BLEND_RGBA_ADD)

    glow.blit(src, (pad, pad))

    return glow





def _block_to_screen_anchor(

    block_size: tuple[int, int],

    block_point: tuple[float, float],

    tilt_deg: float,

) -> tuple[float, float]:

    """回転前ブロック座標の点を、中央配置 blit 後のスクリーン座標へ変換"""

    cx, cy = block_size[0] / 2, block_size[1] / 2

    vec = pygame.math.Vector2(block_point) - pygame.math.Vector2(cx, cy)

    vec = vec.rotate(-tilt_deg)

    return (

        TITLE_LOGO_CENTER[0] + vec.x,

        TITLE_LOGO_CENTER[1] + vec.y,

    )





def render_tilted_logo(

    line1: str,

    line2: str,

    fonts: TitleFonts,

    *,

    now: float = 0.0,

) -> tuple[pygame.Surface, tuple[float, float]]:

    """2行ロゴを重ねて傾斜させた Surface と、1行目上端中央のスクリーン座標を返す"""

    pulse = 0.88 + 0.12 * math.sin(now * 1.4)

    glow_color = tuple(int(c * pulse) for c in LOGO_GLOW)



    t1 = render_wood_text(line1, fonts.logo_line1)

    t2 = render_wood_text(line2, fonts.logo_line2)



    gap = -14

    width = max(t1.get_width(), t2.get_width()) + 24

    height = t1.get_height() + t2.get_height() + gap + 24

    block = pygame.Surface((width, height), pygame.SRCALPHA)



    x1 = (width - t1.get_width()) // 2

    x2 = (width - t2.get_width()) // 2 + 10

    y1 = 8

    y2 = y1 + t1.get_height() + gap



    g1 = render_firefly_glow(t1, glow_color)

    g2 = render_firefly_glow(t2, glow_color)

    block.blit(g1, (x1 - 18, y1 - 18))

    block.blit(t1, (x1, y1))

    block.blit(g2, (x2 - 18, y2 - 18))

    block.blit(t2, (x2, y2))



    line1_top_center = (x1 + t1.get_width() / 2, y1)

    rotated = pygame.transform.rotate(block, -TITLE_LOGO_TILT_DEG)

    screen_anchor = _block_to_screen_anchor((width, height), line1_top_center, TITLE_LOGO_TILT_DEG)

    return rotated, screen_anchor





def render_catch_copy(fonts: TitleFonts) -> pygame.Surface:

    return render_wood_text(
        TITLE_CATCH_COPY,
        fonts.catch_copy,
        fill=LOGO_FILL,
        outline=LOGO_OUTLINE,
        outline_px=2,
    )





def blit_logo_center(surf: pygame.Surface, logo: pygame.Surface) -> pygame.Rect:

    rect = logo.get_rect(center=TITLE_LOGO_CENTER)

    surf.blit(logo, rect)

    return rect





def blit_catch_copy(

    surf: pygame.Surface,

    catch: pygame.Surface,

    line1_top_center: tuple[float, float],

) -> None:

    rect = catch.get_rect()

    rect.midbottom = (

        int(line1_top_center[0]),

        int(line1_top_center[1] - TITLE_CATCH_GAP),

    )

    surf.blit(catch, rect)


