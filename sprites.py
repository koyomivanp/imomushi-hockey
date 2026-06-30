"""Summer Engine / Gemini 生成スプライトの読み込み（無ければプロシージャル描画にフォールバック）"""

from __future__ import annotations

import math
from pathlib import Path

import pygame

_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "sprites"

_SPRITE_NAMES = {
    "body_p1": "caterpillar_p1_segment.png",
    "body_p2": "caterpillar_p2_segment.png",
    "leaf": "leaf_puck.png",
}

# 体節スプライトは横顔・背景残りがありやすいためオフ（葉っぱのみスプライト可）
BODY_SPRITE_ENABLED = False

_cache: dict[str, pygame.Surface | None] = {}
_loaded = False
_MAX_SPRITE_PX = 128
_BG_LUM_THRESHOLD = 42
_BG_COLOR_DIST = 48


def _ensure_display() -> None:
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1), pygame.HIDDEN)


def _sample_bg_color(surf: pygame.Surface) -> tuple[int, int, int]:
    w, h = surf.get_size()
    samples = [
        surf.get_at((0, 0))[:3],
        surf.get_at((w - 1, 0))[:3],
        surf.get_at((0, h - 1))[:3],
        surf.get_at((w - 1, h - 1))[:3],
        surf.get_at((w // 2, 0))[:3],
        surf.get_at((w // 2, h - 1))[:3],
    ]
    return (
        sum(c[0] for c in samples) // len(samples),
        sum(c[1] for c in samples) // len(samples),
        sum(c[2] for c in samples) // len(samples),
    )


def _remove_background(surf: pygame.Surface) -> pygame.Surface:
    """黒〜暗色背景とアンチエイリアス縁をアルファ透過"""
    _ensure_display()
    try:
        src = surf.convert_alpha()
    except pygame.error:
        src = surf.convert()
    w, h = src.get_size()
    bg = _sample_bg_color(src)
    out = pygame.Surface((w, h), pygame.SRCALPHA)

    for y in range(h):
        for x in range(w):
            r, g, b = src.get_at((x, y))[:3]
            lum = r + g + b
            dist = math.sqrt((r - bg[0]) ** 2 + (g - bg[1]) ** 2 + (b - bg[2]) ** 2)
            if lum < _BG_LUM_THRESHOLD * 3 or dist < _BG_COLOR_DIST:
                alpha = 0
            elif lum < _BG_LUM_THRESHOLD * 3 + 55 or dist < _BG_COLOR_DIST + 35:
                edge = min(
                    (lum - _BG_LUM_THRESHOLD * 3) / 55.0,
                    (dist - _BG_COLOR_DIST) / 35.0,
                )
                alpha = int(max(0, min(255, 255 * edge)))
            else:
                alpha = 255
            out.set_at((x, y), (r, g, b, alpha))

    return _crop_alpha(out)


def _crop_alpha(surf: pygame.Surface) -> pygame.Surface:
    w, h = surf.get_size()
    min_x, min_y = w, h
    max_x, max_y = 0, 0
    found = False
    for y in range(h):
        for x in range(w):
            if surf.get_at((x, y))[3] > 8:
                found = True
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if not found:
        return surf
    pad = 2
    min_x = max(0, min_x - pad)
    min_y = max(0, min_y - pad)
    max_x = min(w - 1, max_x + pad)
    max_y = min(h - 1, max_y + pad)
    cropped = pygame.Surface((max_x - min_x + 1, max_y - min_y + 1), pygame.SRCALPHA)
    cropped.blit(surf, (0, 0), pygame.Rect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1))
    return cropped


def _load_sprite_surface(path: Path) -> pygame.Surface:
    _ensure_display()
    raw = pygame.image.load(str(path))
    w, h = raw.get_size()
    longest = max(w, h)
    if longest > _MAX_SPRITE_PX:
        scale = _MAX_SPRITE_PX / longest
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        raw = pygame.transform.smoothscale(raw, (nw, nh))
    try:
        raw = raw.convert_alpha()
    except pygame.error:
        raw = raw.convert()
    return _remove_background(raw)


def init_sprites() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    _ASSET_DIR.mkdir(parents=True, exist_ok=True)
    legacy_heads = {
        "head_p1": "caterpillar_p1_head.png",
        "head_p2": "caterpillar_p2_head.png",
    }
    for name, filename in _SPRITE_NAMES.items():
        path = _ASSET_DIR / filename
        if path.is_file():
            try:
                _cache[name] = _load_sprite_surface(path)
            except (pygame.error, OSError):
                _cache[name] = None
        else:
            _cache[name] = None
    for legacy_key, legacy_file in legacy_heads.items():
        if legacy_key not in _cache and (_ASSET_DIR / legacy_file).is_file():
            try:
                _cache[legacy_key] = _load_sprite_surface(_ASSET_DIR / legacy_file)
            except (pygame.error, OSError):
                pass


def reload_sprites() -> None:
    global _loaded
    _loaded = False
    _cache.clear()
    init_sprites()


def has_sprite(name: str) -> bool:
    init_sprites()
    return _cache.get(name) is not None


def _body_sprite_key(player: int) -> str:
    return "body_p1" if player == 0 else "body_p2"


def _blit_sprite(
    surf: pygame.Surface,
    sprite: pygame.Surface,
    x: float,
    y: float,
    diameter: float,
    angle: float = 0.0,
    alpha: int = 255,
) -> None:
    base = max(sprite.get_width(), sprite.get_height())
    scale = diameter / base
    tw = max(1, int(sprite.get_width() * scale))
    th = max(1, int(sprite.get_height() * scale))
    scaled = pygame.transform.smoothscale(sprite, (tw, th))
    if alpha < 255:
        scaled = scaled.copy()
        scaled.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
    if abs(angle) > 0.001:
        scaled = pygame.transform.rotate(scaled, -math.degrees(angle))
    rect = scaled.get_rect(center=(int(x), int(y)))
    surf.blit(scaled, rect)


def draw_body_sprite(
    surf: pygame.Surface,
    x: float,
    y: float,
    radius: float,
    player: int,
    alpha: int = 255,
    angle: float = 0.0,
) -> bool:
    if not BODY_SPRITE_ENABLED:
        return False
    init_sprites()
    sprite = _cache.get(_body_sprite_key(player))
    if sprite is None:
        return False
    _blit_sprite(surf, sprite, x, y, radius * 2.0, angle, alpha)
    return True


def draw_head_sprite(
    surf: pygame.Surface,
    x: float,
    y: float,
    radius: float,
    player: int,
    heading: float,
    alpha: int = 255,
) -> bool:
    """頭も体節と同じ直径で描画（スリザリオ風）"""
    return draw_body_sprite(surf, x, y, radius, player, alpha, heading)


def draw_segment_sprite(
    surf: pygame.Surface,
    x: float,
    y: float,
    radius: float,
    player: int,
    alpha: int = 255,
) -> bool:
    return draw_body_sprite(surf, x, y, radius, player, alpha)


def draw_leaf_sprite(
    surf: pygame.Surface,
    x: float,
    y: float,
    radius: float,
    spin: float,
    alpha: int = 255,
) -> bool:
    init_sprites()
    sprite = _cache.get("leaf")
    if sprite is None:
        return False
    _blit_sprite(surf, sprite, x, y, radius * 2.4, spin, alpha)
    return True
