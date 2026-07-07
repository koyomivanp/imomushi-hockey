"""Living forest バトルアリーナ — アセット読込・プロシージャル fallback・描画"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

import pygame

from constants import (
    ARENA_CENTER_ZONE_TINT,
    ARENA_FRAME_ASSET_SIZE,
    ARENA_FRAME_CORNER,
    ARENA_GOAL_ZONE_TINT,
    BG_COLOR,
    FACEOFF_LIGHT_DURATION,
    GOAL_FIREFLY_DURATION,
    GOAL_SCORE_DEPTH,
    GOAL_SIDE_FLASH_DURATION,
    GOAL_WALL_PULSE_DURATION,
    CENTER_LINE_COLOR,
    HUD_PLAQUE_H,
    HUD_PLAQUE_W,
    LOGO_OUTLINE,
    MENU_BG,
    MENU_BORDER,
    P1_COLOR,
    P2_COLOR,
    SCREEN_H,
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
)
from entities import arena_frame_rect, goal_bounds, playable_rect, table_rect


@dataclass
class ArenaLightingState:
    goal_flash_side: int | None = None
    goal_flash_timer: float = 0.0
    goal_flash_scorer: int = 0
    faceoff_pulse_timer: float = 0.0
    near_win: bool = False

    @classmethod
    def inactive(cls) -> ArenaLightingState:
        return cls()

_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "arena"
_FILES = (
    "battle_bg.png",
    "court_floor.png",
    "court_frame.png",
    "hud_plaque.png",
)

_cache: dict[str, pygame.Surface | None] = {}
_disk_assets: set[str] = set()
_loaded = False
_rng = random.Random(42)
_scale_cache: dict[tuple[int, int, int], pygame.Surface] = {}
_table_static_cache: dict[str, pygame.Surface] = {}
_frame_composite_cache: pygame.Surface | None = None

# バトル全画面の最下層 — 枠 PNG の明るい余白が漏れてもここだけは暗く保つ
BATTLE_BACKDROP_BASE = (6, 14, 8)


def _ensure_display() -> None:
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1), pygame.HIDDEN)


def _load_png(name: str) -> pygame.Surface | None:
    path = _ASSET_DIR / name
    if not path.is_file():
        return None
    try:
        _ensure_display()
        surf = pygame.image.load(str(path))
        return surf.convert_alpha() if surf.get_flags() & pygame.SRCALPHA else surf.convert()
    except (pygame.error, OSError):
        return None


def _frame_needs_repair(frame: pygame.Surface) -> bool:
    """Summer 生成枠は中心が透明ではなく明るいグレーで塗られることがある。"""
    w, h = frame.get_size()
    samples = (
        (w // 2, h // 2),
        (w // 4, h // 4),
        (3 * w // 4, h // 4),
        (16, 16),
    )
    bright = 0
    for x, y in samples:
        r, g, b, a = frame.get_at((x, y))
        if a > 200 and r + g + b > 360:
            bright += 1
    return bright >= 2


def _is_frame_backdrop_pixel(r: int, g: int, b: int) -> bool:
    lum = (r + g + b) / 3.0
    spread = max(r, g, b) - min(r, g, b)
    if lum > 165 and spread < 48:
        return True
    if lum > 90 and spread < 42:
        return True
    if lum > 55 and spread < 22:
        return True
    if lum > 38 and spread < 32:
        return True
    return False


def _repair_court_frame(frame: pygame.Surface) -> pygame.Surface:
    """9-slice 用に明るい余白を透過し、樹皮を少し暗くする。"""
    if not _frame_needs_repair(frame):
        return frame
    out = frame.copy().convert_alpha()
    w, h = out.get_size()
    for y in range(h):
        for x in range(w):
            r, g, b, a = out.get_at((x, y))
            if a < 48 or _is_frame_backdrop_pixel(r, g, b):
                out.set_at((x, y), (0, 0, 0, 0))
            else:
                lum = (r + g + b) / 3.0
                shade = 0.72 if lum > 80 else 0.88
                out.set_at(
                    (x, y),
                    (
                        max(0, int(r * shade)),
                        max(0, int(g * (shade - 0.04))),
                        max(0, int(b * (shade - 0.08))),
                        a,
                    ),
                )
    return out


def init_arena_assets() -> None:
    global _loaded, _frame_composite_cache
    if _loaded:
        return
    _loaded = True
    _frame_composite_cache = None
    bakers = {
        "battle_bg.png": bake_battle_bg,
        "court_floor.png": bake_court_floor,
        "court_frame.png": bake_court_frame,
        "hud_plaque.png": bake_hud_plaque,
    }
    for name in _FILES:
        loaded = _load_png(name)
        if loaded is not None:
            _disk_assets.add(name)
        baked = loaded if loaded is not None else bakers[name]()
        if name == "court_frame.png" and loaded is not None:
            baked = _repair_court_frame(baked)
        _cache[name] = baked


def get_battle_bg() -> pygame.Surface | None:
    init_arena_assets()
    return _cache.get("battle_bg.png")


def get_court_floor() -> pygame.Surface | None:
    init_arena_assets()
    return _cache.get("court_floor.png")


def get_court_frame() -> pygame.Surface | None:
    init_arena_assets()
    return _cache.get("court_frame.png")


def get_hud_plaque() -> pygame.Surface | None:
    init_arena_assets()
    return _cache.get("hud_plaque.png")


def has_rich_backdrop() -> bool:
    """PNG battle_bg がディスクから読み込まれているか。"""
    init_arena_assets()
    return "battle_bg.png" in _disk_assets


def has_court_floor_asset() -> bool:
    init_arena_assets()
    return "court_floor.png" in _disk_assets


def _moss_color(t: float) -> tuple[int, int, int]:
    a = TABLE_COLOR
    b = (18, 42, 24)
    c = (32, 68, 38)
    if t < 0.5:
        u = t * 2.0
        return tuple(int(a[i] + (b[i] - a[i]) * u) for i in range(3))
    u = (t - 0.5) * 2.0
    return tuple(int(b[i] + (c[i] - b[i]) * u) for i in range(3))


def bake_battle_bg() -> pygame.Surface:
    """Fallback: dark tree silhouettes + starry sky (no ground detail)."""
    surf = pygame.Surface((SCREEN_W, SCREEN_H))
    surf.fill(MENU_BG)

    sky = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for y in range(SCREEN_H // 2):
        t = y / max(1, SCREEN_H // 2 - 1)
        col = (
            int(6 + t * 8),
            int(14 + t * 14),
            int(22 + t * 18),
        )
        pygame.draw.line(sky, (*col, 255), (0, y), (SCREEN_W, y))
    surf.blit(sky, (0, 0))

    for _ in range(28):
        sx = _rng.randint(120, SCREEN_W - 120)
        sy = _rng.randint(40, TABLE_Y - 20)
        br = _rng.randint(140, 220)
        pygame.draw.circle(sky, (br, br, br, _rng.randint(80, 180)), (sx, sy), _rng.randint(1, 2))
    surf.blit(sky, (0, 0))

    trees = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for side, ox in ((0, 0), (1, SCREEN_W)):
        for i in range(5):
            bx = ox + (side * -1) * _rng.randint(0, 80)
            bw = _rng.randint(50, 140)
            bh = _rng.randint(SCREEN_H // 2, SCREEN_H - 40)
            by = SCREEN_H - bh
            if side:
                bx = ox - bw + _rng.randint(-20, 40)
            pygame.draw.rect(trees, (4, 8, 6, 240), (bx, by, bw, bh))
            crown_w = bw + _rng.randint(20, 60)
            crown_h = _rng.randint(80, 160)
            crown_x = bx - (crown_w - bw) // 2
            crown_y = by - crown_h + _rng.randint(20, 50)
            pygame.draw.ellipse(trees, (4, 8, 6, 220), (crown_x, crown_y, crown_w, crown_h))
    surf.blit(trees, (0, 0))

    fireflies = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for _ in range(6):
        fx = _rng.randint(80, SCREEN_W - 80)
        fy = _rng.randint(TABLE_Y - 60, SCREEN_H - 40)
        pygame.draw.circle(fireflies, (168, 210, 98, _rng.randint(60, 120)), (fx, fy), 2)
    surf.blit(fireflies, (0, 0))
    return surf


def bake_court_floor() -> pygame.Surface:
    w, h = TABLE_W, TABLE_H
    surf = pygame.Surface((w, h))
    for y in range(h):
        for x in range(0, w, 2):
            n = (_rng.random() * 0.6 + (math.sin(x * 0.08) + math.cos(y * 0.06)) * 0.2)
            col = _moss_color(0.25 + n * 0.5)
            pygame.draw.line(surf, col, (x, y), (min(x + 1, w - 1), y))
    leaf_layer = pygame.Surface((w, h), pygame.SRCALPHA)
    for _ in range(48):
        lx = _rng.randint(0, w)
        ly = _rng.randint(0, h)
        shade = _rng.randint(28, 55)
        pts = [
            (lx, ly),
            (lx - _rng.randint(4, 9), ly - _rng.randint(2, 5)),
            (lx - _rng.randint(6, 12), ly + _rng.randint(1, 4)),
            (lx - _rng.randint(2, 6), ly + _rng.randint(3, 7)),
        ]
        pygame.draw.polygon(leaf_layer, (32 + shade, 72 + shade // 2, 38, _rng.randint(30, 70)), pts)
    surf.blit(leaf_layer, (0, 0))
    dapple = pygame.Surface((w, h), pygame.SRCALPHA)
    for _ in range(14):
        cx = _rng.randint(0, w)
        cy = _rng.randint(0, h)
        r = _rng.randint(18, 55)
        pygame.draw.circle(dapple, (118, 168, 102, _rng.randint(10, 28)), (cx, cy), r)
    surf.blit(dapple, (0, 0))
    return surf


def _bake_frame_edge(w: int, h: int, *, moss: bool = True) -> pygame.Surface:
    """上下左右共通の根・苔エッジテクスチャ（9-slice 用）。"""
    edge = pygame.Surface((w, h), pygame.SRCALPHA)
    edge.fill((58, 38, 24, 218))
    bark_hi = (72, 52, 34, 150)
    bark_lo = (48, 34, 22, 120)
    moss_hi = (72, 118, 78, 90)
    moss_lo = (48, 88, 52, 70)
    horizontal = w >= h
    if horizontal:
        mid = h // 2
        for i in range(0, w, 8):
            pygame.draw.line(edge, bark_hi, (i, mid), (i + 5, mid + 2), 2)
            pygame.draw.line(edge, bark_lo, (i + 3, mid - 3), (i + 7, mid - 1), 1)
        if moss:
            for i in range(12, w - 8, 24):
                my = _rng.randint(4, max(5, h - 6))
                pygame.draw.circle(edge, moss_hi, (i, my), _rng.randint(2, 4))
                pygame.draw.circle(edge, moss_lo, (i + 6, min(h - 4, my + 3)), _rng.randint(1, 3))
    else:
        mid = w // 2
        for i in range(0, h, 8):
            pygame.draw.line(edge, bark_hi, (mid, i), (mid + 2, i + 5), 2)
            pygame.draw.line(edge, bark_lo, (mid - 3, i + 3), (mid - 1, i + 7), 1)
        if moss:
            for i in range(12, h - 8, 24):
                mx = _rng.randint(4, max(5, w - 6))
                pygame.draw.circle(edge, moss_hi, (mx, i), _rng.randint(2, 4))
                pygame.draw.circle(edge, moss_lo, (min(w - 4, mx + 3), i + 6), _rng.randint(1, 3))
    return edge


def bake_court_frame() -> pygame.Surface:
    size = 256
    corner = 64
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(surf, (0, 0, 0, 0), pygame.Rect(0, 0, size, size))

    def _root_corner(ox: int, oy: int, flip_x: bool, flip_y: bool) -> None:
        pts = []
        for i in range(12):
            t = i / 11.0
            bx = int(corner * (1.0 - t * 0.85))
            by = int(corner * (1.0 - t * 0.15) + math.sin(t * 4.5) * 8)
            if flip_x:
                bx = corner - bx + ox
            else:
                bx = ox + bx
            if flip_y:
                by = corner - by + oy
            else:
                by = oy + by
            pts.append((bx, by))
        pygame.draw.lines(surf, (48, 34, 22), False, pts, 6)
        pygame.draw.lines(surf, (72, 52, 34), False, pts, 2)

    corner_fill = _bake_frame_edge(corner, corner, moss=False)
    surf.blit(corner_fill, (0, 0))
    surf.blit(pygame.transform.flip(corner_fill, True, False), (size - corner, 0))
    surf.blit(pygame.transform.flip(corner_fill, False, True), (0, size - corner))
    surf.blit(pygame.transform.flip(corner_fill, True, True), (size - corner, size - corner))

    _root_corner(0, 0, False, False)
    _root_corner(size - corner, 0, True, False)
    _root_corner(0, size - corner, False, True)
    _root_corner(size - corner, size - corner, True, True)

    top = _bake_frame_edge(size - corner * 2, corner)
    side = _bake_frame_edge(corner, size - corner * 2)
    surf.blit(top, (corner, 0))
    surf.blit(pygame.transform.flip(top, False, True), (corner, size - corner))
    surf.blit(side, (0, corner))
    surf.blit(pygame.transform.flip(side, True, False), (size - corner, corner))
    return surf


def bake_goal_post() -> pygame.Surface:
    size = 64
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2 + 6
    pygame.draw.ellipse(surf, (48, 32, 22), (cx - 18, cy - 8, 36, 28))
    pygame.draw.ellipse(surf, (62, 44, 30), (cx - 14, cy - 4, 28, 20))
    pygame.draw.ellipse(surf, (58, 98, 62), (cx - 20, cy - 14, 22, 14))
    pygame.draw.circle(surf, TABLE_BORDER, (cx, cy - 10), 8)
    pygame.draw.circle(surf, LOGO_OUTLINE, (cx, cy - 10), 5)
    return surf


def bake_hud_plaque() -> pygame.Surface:
    w, h = HUD_PLAQUE_W + 16, HUD_PLAQUE_H + 12
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    body = pygame.Rect(4, 4, w - 8, h - 8)
    pygame.draw.rect(surf, (32, 48, 34), body, border_radius=12)
    inner = body.inflate(-6, -6)
    pygame.draw.rect(surf, (42, 58, 44), inner, border_radius=10)
    pygame.draw.rect(surf, (58, 42, 28), inner, 2, border_radius=10)
    bark = pygame.Surface(inner.size, pygame.SRCALPHA)
    for x in range(6, inner.width, 9):
        pygame.draw.line(bark, (48, 36, 26, 40), (x, 4), (x + 2, inner.height - 4), 1)
    for _ in range(16):
        mx = _rng.randint(4, inner.width - 8)
        my = _rng.randint(4, inner.height - 8)
        pygame.draw.circle(bark, (72, 118, 78, _rng.randint(50, 110)), (mx, my), _rng.randint(2, 5))
    surf.blit(bark, inner.topleft)
    return surf


def draw_forest_atmosphere(
    surf: pygame.Surface,
    now: float,
    *,
    battle: bool = False,
    lighting: ArenaLightingState | None = None,
    include_fireflies: bool = True,
) -> None:
    light = lighting or ArenaLightingState.inactive()
    rich = has_rich_backdrop()
    vignette_strength = 3 if rich else (4 if light.near_win and battle else 5)
    vignette = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    strength = vignette_strength if battle else (2 if rich else 6)
    for i in range(strength):
        base_alpha = 6 if rich else 24
        alpha = int(base_alpha + i * (8 if rich else 10))
        margin = i * (20 if rich else (24 if battle else 28))
        pygame.draw.rect(
            vignette,
            (4, 10, 6, alpha),
            pygame.Rect(margin, margin, SCREEN_W - margin * 2, SCREEN_H - margin * 2),
            width=18 if rich else (22 if battle else 24),
        )
    surf.blit(vignette, (0, 0))

    if rich and not battle:
        return

    if not include_fireflies:
        return

    firefly_boost = 1.15 if light.near_win and battle else 1.0

    if battle:
        rect = table_rect()
        firefly_pts = (
            (48, 28), (SCREEN_W - 48, 28), (48, 72), (SCREEN_W - 48, 72),
            (24, rect.centery), (SCREEN_W - 24, rect.centery),
            (120, SCREEN_H - 24), (680, SCREEN_H - 24),
            (rect.left - 8, rect.top - 6), (rect.right + 8, rect.bottom + 6),
        )
        if light.goal_flash_timer > 0.0 and light.goal_flash_side is not None:
            gx = rect.left - 16 if light.goal_flash_side == 0 else rect.right + 16
            goal_top, goal_bottom = goal_bounds()
            gy = (goal_top + goal_bottom) * 0.5
            extra = (
                (gx, gy - 42), (gx, gy), (gx, gy + 42),
                (gx + (14 if light.goal_flash_side == 1 else -14), gy - 20),
                (gx + (14 if light.goal_flash_side == 1 else -14), gy + 20),
                (gx + (28 if light.goal_flash_side == 1 else -28), gy),
            )
            firefly_pts = firefly_pts + extra
    else:
        from constants import TITLE_MENU_ZONE_Y

        firefly_pts = (
            (120, 220), (280, 180), (520, 240), (640, 320), (560, 180),
        )
        scene_x0, scene_x1 = 96, SCREEN_W - 96
        scene_y0, scene_y1 = 248, TITLE_MENU_ZONE_Y - 8

    goal_flash_t = 0.0
    if light.goal_flash_timer > 0.0 and GOAL_FIREFLY_DURATION > 0.0:
        goal_flash_t = light.goal_flash_timer / GOAL_FIREFLY_DURATION

    for i, pt in enumerate(firefly_pts):
        fx, fy = pt
        if not battle:
            if scene_x0 <= fx <= scene_x1 and scene_y0 <= fy <= scene_y1:
                continue
        glow = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(now * 1.8 + i * 1.1))
        if goal_flash_t > 0.0 and i >= len(firefly_pts) - 6:
            glow = min(1.0, glow + goal_flash_t * 0.55)
        glow *= firefly_boost
        if glow < 0.45:
            continue
        c = (int(168 * glow), int(210 * glow), int(98 * glow))
        pygame.draw.circle(surf, c, (fx, fy), 2)
        if glow > 0.75:
            pygame.draw.circle(surf, (int(168 * glow * 0.4), int(210 * glow * 0.4), int(98 * glow * 0.4)), (fx, fy), 5)


def _scale_to(surf: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
    if surf.get_size() == size:
        return surf
    key = (id(surf), size[0], size[1])
    cached = _scale_cache.get(key)
    if cached is not None:
        return cached
    scaled = pygame.transform.smoothscale(surf, size)
    _scale_cache[key] = scaled
    return scaled


def _draw_nine_slice(
    dest: pygame.Surface,
    rect: pygame.Rect,
    frame: pygame.Surface,
    corner: int,
) -> None:
    fw, fh = frame.get_size()
    c = min(corner, fw // 2, fh // 2, rect.width // 2, rect.height // 2)
    if c < 2:
        return
    x, y, w, h = rect.x, rect.y, rect.width, rect.height
    mid_w = max(1, w - c * 2)
    mid_h = max(1, h - c * 2)

    def patch(sx: int, sy: int, sw: int, sh: int, dx: int, dy: int, dw: int, dh: int) -> None:
        part = frame.subsurface(pygame.Rect(sx, sy, sw, sh))
        if (sw, sh) != (dw, dh):
            part = pygame.transform.smoothscale(part, (max(1, dw), max(1, dh)))
        dest.blit(part, (dx, dy))

    patch(0, 0, c, c, x, y, c, c)
    patch(fw - c, 0, c, c, x + w - c, y, c, c)
    patch(0, fh - c, c, c, x, y + h - c, c, c)
    patch(fw - c, fh - c, c, c, x + w - c, y + h - c, c, c)
    patch(c, 0, fw - c * 2, c, x + c, y, mid_w, c)
    patch(c, fh - c, fw - c * 2, c, x + c, y + h - c, mid_w, c)
    patch(0, c, c, fh - c * 2, x, y + c, c, mid_h)
    patch(fw - c, c, c, fh - c * 2, x + w - c, y + c, c, mid_h)


def _effective_frame_corner(frame: pygame.Surface) -> int:
    fw, fh = frame.get_size()
    if fw <= ARENA_FRAME_ASSET_SIZE and fh <= ARENA_FRAME_ASSET_SIZE:
        return ARENA_FRAME_CORNER
    scale = min(fw, fh) / ARENA_FRAME_ASSET_SIZE
    return max(ARENA_FRAME_CORNER, int(round(ARENA_FRAME_CORNER * scale)))


def _frame_strip_width(frame: pygame.Surface, corner: int, frame_rect: pygame.Rect) -> int:
    fw, fh = frame.get_size()
    return min(corner, fw // 2, fh // 2, frame_rect.width // 2, frame_rect.height // 2)


def _blit_floor_patch(
    surf: pygame.Surface,
    floor: pygame.Surface,
    table: pygame.Rect,
    dest: pygame.Rect,
) -> None:
    """ゴール開口などコート外縁へ、床テクスチャを連続して貼る。"""
    if dest.width <= 0 or dest.height <= 0:
        return
    scaled = _scale_to(floor, (table.width, table.height))

    blit_top = max(dest.top, table.top)
    blit_bottom = min(dest.bottom, table.bottom)
    src_y = blit_top - table.top
    src_h = blit_bottom - blit_top
    if src_h <= 0:
        pygame.draw.rect(surf, TABLE_COLOR, dest)
        return

    x = dest.left
    while x < dest.right:
        if x < table.left:
            seg_end = min(dest.right, table.left)
            w = seg_end - x
            col = scaled.subsurface(pygame.Rect(0, src_y, 1, src_h))
            surf.blit(pygame.transform.smoothscale(col, (w, src_h)), (x, blit_top))
        elif x < table.right:
            seg_end = min(dest.right, table.right)
            w = seg_end - x
            sx = x - table.left
            surf.blit(scaled, (x, blit_top), pygame.Rect(sx, src_y, w, src_h))
        else:
            w = dest.right - x
            col = scaled.subsurface(pygame.Rect(table.width - 1, src_y, 1, src_h))
            surf.blit(pygame.transform.smoothscale(col, (w, src_h)), (x, blit_top))
            break
        x = seg_end


def _get_frame_composite(
    surf_size: tuple[int, int],
    frame_rect: pygame.Rect,
    frame: pygame.Surface,
    corner: int,
    goal_top: float,
    goal_bottom: float,
) -> pygame.Surface:
    global _frame_composite_cache
    if _frame_composite_cache is not None:
        return _frame_composite_cache

    layer = pygame.Surface(surf_size, pygame.SRCALPHA)
    _draw_nine_slice(layer, frame_rect, frame, corner)

    strip_w = _frame_strip_width(frame, corner, frame_rect)
    goal_h = int(goal_bottom) - int(goal_top)
    if strip_w >= 2 and goal_h > 0:
        left_gap = pygame.Rect(
            frame_rect.left - GOAL_SCORE_DEPTH,
            int(goal_top),
            strip_w + GOAL_SCORE_DEPTH,
            goal_h,
        )
        right_gap = pygame.Rect(
            frame_rect.right - strip_w,
            int(goal_top),
            strip_w + GOAL_SCORE_DEPTH,
            goal_h,
        )
        layer.fill((0, 0, 0, 0), left_gap)
        layer.fill((0, 0, 0, 0), right_gap)

    _frame_composite_cache = layer
    return layer


def _draw_frame_night_blend(surf: pygame.Surface, frame_rect: pygame.Rect) -> None:
    """枠周辺を夜の森トーンへ軽く落として、PNG フリンジと床の境目を馴染ませる。"""
    blend = pygame.Surface(frame_rect.size, pygame.SRCALPHA)
    blend.fill((4, 10, 6, 36))
    surf.blit(blend, frame_rect.topleft)


def _draw_court_frame_with_goal_gaps(
    surf: pygame.Surface,
    frame_rect: pygame.Rect,
    frame: pygame.Surface,
    corner: int,
    goal_top: float,
    goal_bottom: float,
    floor: pygame.Surface | None,
    table: pygame.Rect,
) -> None:
    """左右ゴール開口部だけ枠を欠けさせ、通行可能エリアを緑床でつなぐ。"""
    strip_w = _frame_strip_width(frame, corner, frame_rect)
    if strip_w < 2:
        return

    goal_h = int(goal_bottom) - int(goal_top)
    if goal_h <= 0:
        return

    goal_top_i = int(goal_top)
    goal_bottom_i = int(goal_bottom)
    left_gap = pygame.Rect(
        frame_rect.left - GOAL_SCORE_DEPTH,
        goal_top_i,
        strip_w + GOAL_SCORE_DEPTH,
        goal_h,
    )
    right_gap = pygame.Rect(
        frame_rect.right - strip_w,
        goal_top_i,
        strip_w + GOAL_SCORE_DEPTH,
        goal_h,
    )

    for gap in (left_gap, right_gap):
        if floor is not None:
            _blit_floor_patch(surf, floor, table, gap)
        else:
            pygame.draw.rect(surf, TABLE_COLOR, gap)


def _restore_playable_floor(
    surf: pygame.Surface,
    floor: pygame.Surface | None,
    table: pygame.Rect,
    play: pygame.Rect,
) -> None:
    """枠描画で茶色がかぶった通行可能エリアを緑床で上書きする。"""
    if floor is not None:
        _blit_floor_patch(surf, floor, table, play)
    else:
        pygame.draw.rect(surf, TABLE_COLOR, play)


def draw_menu_backdrop(surf: pygame.Surface, now: float) -> None:
    """タイトル・メニュー・TIPS 共通 — 森 PNG + ホタル・ビネット。"""
    bg = get_battle_bg()
    if bg is not None:
        scaled = _scale_to(bg, (SCREEN_W, SCREEN_H))
        surf.blit(scaled, (0, 0))
    else:
        surf.fill(MENU_BG)
    draw_forest_atmosphere(surf, now, battle=False)


def _draw_battle_edge_vignette(surf: pygame.Surface) -> None:
    """画面外縁を少し落として HUD・枠余白の浮き感を抑える。"""
    vignette = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for i in range(5):
        alpha = 16 + i * 12
        margin = 8 + i * 16
        pygame.draw.rect(
            vignette,
            (2, 6, 4, alpha),
            pygame.Rect(margin, margin, SCREEN_W - margin * 2, SCREEN_H - margin * 2),
            width=14,
        )
    surf.blit(vignette, (0, 0))


def _mask_outside_court_black(surf: pygame.Surface) -> None:
    """通行可能エリアとゴール通路以外を真っ黒で塗りつぶす。"""
    play = playable_rect()
    frame = arena_frame_rect()
    goal_top, goal_bottom = goal_bounds()
    gt, gb = int(goal_top), int(goal_bottom)

    if frame.top > 0:
        pygame.draw.rect(surf, MENU_BG, pygame.Rect(0, 0, SCREEN_W, frame.top))
    if frame.bottom < SCREEN_H:
        pygame.draw.rect(surf, BG_COLOR, pygame.Rect(0, frame.bottom, SCREEN_W, SCREEN_H - frame.bottom))
    if frame.left > 0:
        pygame.draw.rect(surf, BG_COLOR, pygame.Rect(0, 0, frame.left, gt))
        pygame.draw.rect(surf, BG_COLOR, pygame.Rect(0, gb, frame.left, SCREEN_H - gb))
    if frame.right < SCREEN_W:
        pygame.draw.rect(surf, BG_COLOR, pygame.Rect(frame.right, 0, SCREEN_W - frame.right, gt))
        pygame.draw.rect(surf, BG_COLOR, pygame.Rect(frame.right, gb, SCREEN_W - frame.right, SCREEN_H - gb))

    # 枠 PNG（根・苔の帯）— playable の外側
    if play.top > frame.top:
        pygame.draw.rect(surf, BG_COLOR, pygame.Rect(frame.left, frame.top, frame.width, play.top - frame.top))
    if play.bottom < frame.bottom:
        pygame.draw.rect(surf, BG_COLOR, pygame.Rect(frame.left, play.bottom, frame.width, frame.bottom - play.bottom))
    if play.left > frame.left:
        lw = play.left - frame.left
        if gt > frame.top:
            pygame.draw.rect(surf, BG_COLOR, pygame.Rect(frame.left, frame.top, lw, gt - frame.top))
        if frame.bottom > gb:
            pygame.draw.rect(surf, BG_COLOR, pygame.Rect(frame.left, gb, lw, frame.bottom - gb))
    if play.right < frame.right:
        rw = frame.right - play.right
        if gt > frame.top:
            pygame.draw.rect(surf, BG_COLOR, pygame.Rect(play.right, frame.top, rw, gt - frame.top))
        if frame.bottom > gb:
            pygame.draw.rect(surf, BG_COLOR, pygame.Rect(play.right, gb, rw, frame.bottom - gb))


def draw_battle_backdrop(
    surf: pygame.Surface,
    now: float,
    lighting: ArenaLightingState | None = None,
) -> None:
    _ = now, lighting
    surf.fill(BG_COLOR)


def _get_center_line_overlay(rect: pygame.Rect) -> pygame.Surface:
    key = f"center_line_{rect.width}x{rect.height}"
    cached = _table_static_cache.get(key)
    if cached is not None:
        return cached
    center_line = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    cx = rect.centerx - rect.left
    y = 8
    while y < rect.height - 8:
        pygame.draw.line(center_line, (*CENTER_LINE_COLOR, 38), (cx, y), (cx, y + 8), 1)
        y += 16
    _table_static_cache[key] = center_line
    return center_line


def _get_zone_tint_overlay(width: int, height: int, color: tuple[int, int, int, int], key: str) -> pygame.Surface:
    cache_key = f"{key}_{width}x{height}"
    cached = _table_static_cache.get(cache_key)
    if cached is not None:
        return cached
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill(color)
    _table_static_cache[cache_key] = overlay
    return overlay


def _draw_table_fallback_floor(surf: pygame.Surface, rect: pygame.Rect) -> None:
    pygame.draw.rect(surf, TABLE_COLOR, rect)
    for x in range(rect.left + 20, rect.right, 40):
        pygame.draw.line(surf, TABLE_GRID_COLOR, (x, rect.top + 4), (x, rect.bottom - 4), 1)
    for y in range(rect.top + 20, rect.bottom, 40):
        pygame.draw.line(surf, TABLE_GRID_COLOR, (rect.left + 4, y), (rect.right - 4, y), 1)


def _draw_table_overlays(
    surf: pygame.Surface,
    rect: pygame.Rect,
    *,
    organic_frame: bool,
    now: float = 0.0,
    lighting: ArenaLightingState | None = None,
) -> None:
    light = lighting or ArenaLightingState.inactive()

    center_line = _get_center_line_overlay(rect)
    surf.blit(center_line, rect.topleft)

    center_w = int(rect.width * TRAIL_CENTER_ZONE_RATIO)
    center = _get_zone_tint_overlay(center_w, rect.height, ARENA_CENTER_ZONE_TINT, "center_zone").copy()
    if light.faceoff_pulse_timer > 0.0 and FACEOFF_LIGHT_DURATION > 0.0:
        fp = light.faceoff_pulse_timer / FACEOFF_LIGHT_DURATION
        sweep_x = rect.centerx - center_w // 2 + int(center_w * (1.0 - fp))
        dapple = pygame.Surface((48, rect.height), pygame.SRCALPHA)
        alpha = int(22 * fp)
        pygame.draw.circle(dapple, (118, 168, 102, alpha), (24, rect.height // 2), 22)
        surf.blit(dapple, (sweep_x, rect.top))
        center_alpha = int(10 + 18 * fp)
        center.fill((88, 168, 102, center_alpha))
    surf.blit(center, (rect.centerx - center_w // 2, rect.top))

    crease_w = int(rect.width * TRAIL_GOAL_ZONE_RATIO)
    scorer_color = P1_COLOR if light.goal_flash_scorer == 0 else P2_COLOR
    flash_t = 0.0
    if light.goal_flash_timer > 0.0 and GOAL_SIDE_FLASH_DURATION > 0.0:
        flash_t = light.goal_flash_timer / GOAL_SIDE_FLASH_DURATION

    for side_idx, side_x in enumerate((rect.left, rect.right - crease_w)):
        crease = _get_zone_tint_overlay(crease_w, rect.height, ARENA_GOAL_ZONE_TINT, f"goal_zone_{side_idx}").copy()
        if flash_t > 0.0 and light.goal_flash_side == side_idx:
            pulse = 0.5 + 0.5 * math.sin(flash_t * math.pi * 3.0)
            alpha = int(28 + 42 * flash_t * pulse)
            crease.fill((*scorer_color, alpha))
        surf.blit(crease, (side_x, rect.top))

    if organic_frame:
        return

    bw = TABLE_BORDER_WIDTH
    pygame.draw.line(surf, TABLE_BORDER, (rect.left, rect.top), (rect.right, rect.top), bw)
    pygame.draw.line(surf, TABLE_BORDER, (rect.left, rect.bottom), (rect.right, rect.bottom), bw)
    pygame.draw.line(surf, TABLE_BORDER, (rect.left, rect.top), (rect.left, goal_top), bw)
    pygame.draw.line(surf, TABLE_BORDER, (rect.left, goal_bottom), (rect.left, rect.bottom), bw)
    pygame.draw.line(surf, TABLE_BORDER, (rect.right, rect.top), (rect.right, goal_top), bw)
    pygame.draw.line(surf, TABLE_BORDER, (rect.right, goal_bottom), (rect.right, rect.bottom), bw)


def _draw_goal_wall_pulse(
    surf: pygame.Surface,
    rect: pygame.Rect,
    *,
    lighting: ArenaLightingState | None = None,
) -> None:
    """得点時 — ゴール側の壁沿いに光が相手側へ流れ、だんだん薄れて消える"""
    light = lighting or ArenaLightingState.inactive()
    if light.goal_flash_timer <= 0.0 or light.goal_flash_side is None:
        return
    if GOAL_WALL_PULSE_DURATION <= 0.0:
        return

    progress = 1.0 - (light.goal_flash_timer / GOAL_WALL_PULSE_DURATION)
    progress = max(0.0, min(1.0, progress))
    fade_out = max(0.0, 1.0 - progress * 0.85)
    conceded = light.goal_flash_side
    scorer_color = P1_COLOR if light.goal_flash_scorer == 0 else P2_COLOR
    goal_top, goal_bottom = goal_bounds()
    frame = arena_frame_rect()

    head_span = 36
    trail_len = 140
    edge_inset = 3

    if conceded == 0:
        head_x = frame.left + frame.width * progress
        trail_dir = -1
    else:
        head_x = frame.right - frame.width * progress
        trail_dir = 1

    edges = (frame.top + edge_inset, frame.bottom - edge_inset)
    for edge_y in edges:
        for i in range(trail_len):
            x = head_x + trail_dir * i
            if x < frame.left - 4 or x > frame.right + 4:
                continue
            t = i / trail_len
            alpha = int(200 * (1.0 - t) * fade_out)
            if alpha < 5:
                continue
            size = max(2, 5 - i // 28)
            glow = pygame.Surface((size * 2 + 2, size * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*scorer_color, alpha), (size + 1, size + 1), size)
            surf.blit(glow, (int(x) - size - 1, int(edge_y) - size - 1))

        head_surf = pygame.Surface((head_span, 10), pygame.SRCALPHA)
        for j in range(head_span):
            local = j / max(1, head_span - 1)
            if conceded == 0:
                local_alpha = int(240 * local * fade_out)
            else:
                local_alpha = int(240 * (1.0 - local) * fade_out)
            if local_alpha < 4:
                continue
            pygame.draw.line(
                head_surf,
                (*scorer_color, local_alpha),
                (j, 2),
                (j, 7),
                2,
            )
        surf.blit(head_surf, (int(head_x) - (head_span if conceded == 0 else 0), int(edge_y) - 5))

    for y in (goal_top, goal_bottom):
        for i in range(48):
            if conceded == 0:
                y_pos = y - i * (goal_top - frame.top) / 48
                if y_pos < frame.top:
                    break
            else:
                y_pos = y + i * (frame.bottom - goal_bottom) / 48
                if y_pos > frame.bottom:
                    break
            t = i / 48
            alpha = int(170 * (1.0 - t) * fade_out)
            if alpha < 5:
                continue
            edge_x = frame.left + edge_inset if conceded == 0 else frame.right - edge_inset
            glow = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*scorer_color, alpha), (4, 4), 3)
            surf.blit(glow, (int(edge_x) - 4, int(y_pos) - 4))


def _draw_goal_markers(
    surf: pygame.Surface,
    rect: pygame.Rect,
    lighting: ArenaLightingState | None = None,
) -> None:
    """ゴール上下端 — 壁の外側へ90度に小さく出っ張る根の切り株。"""
    light = lighting or ArenaLightingState.inactive()
    play = playable_rect()
    goal_top, goal_bottom = goal_bounds()
    stub_len = 10
    stub_thick = 4
    bark = (58, 38, 24)
    bark_hi = (72, 52, 34)
    scorer_color = P1_COLOR if light.goal_flash_scorer == 0 else P2_COLOR
    flash_t = 0.0
    if light.goal_flash_timer > 0.0 and GOAL_SIDE_FLASH_DURATION > 0.0:
        flash_t = light.goal_flash_timer / GOAL_SIDE_FLASH_DURATION

    for y in (int(goal_top), int(goal_bottom)):
        for side_idx, (edge_x, outward) in enumerate(((play.left, -1), (play.right, 1))):
            if outward < 0:
                stub = pygame.Rect(edge_x - stub_len, y - stub_thick // 2, stub_len, stub_thick)
            else:
                stub = pygame.Rect(edge_x, y - stub_thick // 2, stub_len, stub_thick)
            pygame.draw.rect(surf, bark, stub, border_radius=1)
            hi_x0 = stub.left + 1
            hi_x1 = stub.right - 1
            pygame.draw.line(surf, bark_hi, (hi_x0, y), (hi_x1, y), 1)
            if flash_t > 0.0 and light.goal_flash_side == side_idx:
                glow_a = int(90 * flash_t)
                glow = pygame.Surface((stub.width + 12, stub.height + 12), pygame.SRCALPHA)
                pygame.draw.rect(
                    glow,
                    (*scorer_color, glow_a),
                    glow.get_rect(),
                    border_radius=3,
                )
                surf.blit(glow, stub.inflate(12, 12).topleft)


def draw_arena_table(
    surf: pygame.Surface,
    now: float = 0.0,
    lighting: ArenaLightingState | None = None,
) -> None:
    rect = table_rect()
    floor = get_court_floor()
    frame = get_court_frame()

    if floor is not None:
        scaled_floor = _scale_to(floor, (rect.width, rect.height))
        surf.blit(scaled_floor, rect.topleft)
        if has_court_floor_asset():
            wash = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            wash.fill((*TABLE_COLOR, 72))
            surf.blit(wash, rect.topleft)
    else:
        _draw_table_fallback_floor(surf, rect)

    has_frame = frame is not None
    _draw_table_overlays(surf, rect, organic_frame=has_frame, now=now, lighting=lighting)

    if has_frame:
        frame_rect = arena_frame_rect()
        goal_top, goal_bottom = goal_bounds()
        frame_corner = _effective_frame_corner(frame)
        _draw_court_frame_with_goal_gaps(
            surf,
            frame_rect,
            frame,
            corner=frame_corner,
            goal_top=goal_top,
            goal_bottom=goal_bottom,
            floor=floor,
            table=rect,
        )
        _restore_playable_floor(surf, floor, rect, playable_rect())

    _draw_goal_markers(surf, rect, lighting=lighting)
    _draw_goal_wall_pulse(surf, rect, lighting=lighting)
    _mask_outside_court_black(surf)


def draw_organic_plaque(surf: pygame.Surface, rect: pygame.Rect) -> None:
    plaque = get_hud_plaque()
    if plaque is not None:
        scaled = _scale_to(plaque, (rect.width + 8, rect.height + 6))
        dst = scaled.get_rect(center=rect.center)
        surf.blit(scaled, dst)
        dim = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
        dim.fill((6, 14, 8, 64))
        surf.blit(dim, dst)
        return

    pygame.draw.rect(surf, (32, 48, 34), rect, border_radius=10)
    inner = rect.inflate(-4, -4)
    pygame.draw.rect(surf, (42, 58, 44), inner, border_radius=8)
    pygame.draw.rect(surf, (58, 42, 28), inner, 2, border_radius=8)
    moss = pygame.Surface((inner.width, inner.height), pygame.SRCALPHA)
    for i in range(0, inner.height, 11):
        pygame.draw.line(moss, (58, 92, 62, 32), (4, i), (inner.width - 4, i + 3), 1)
    for _ in range(10):
        mx = _rng.randint(6, inner.width - 6)
        my = _rng.randint(4, inner.height - 4)
        pygame.draw.circle(moss, (72, 118, 78, 90), (mx, my), _rng.randint(2, 4))
    surf.blit(moss, inner.topleft)
