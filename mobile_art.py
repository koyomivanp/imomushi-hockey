"""スマホ版の絵 — C案「絵本の庭」（切り絵の絵本ふうの庭）

試合ロジックは横画面 800x600 の座標のまま。ここでは縦画面 540x960 へ
直接描く（回転ブリットを挟まないので速く、コート外の黒帯も出ない）。
静止物はサーフェスに焼いて使い回す。
"""

from __future__ import annotations

import math
import random

import pygame

from constants import (
    MOBILE_COURT_CX,
    MOBILE_COURT_CY,
    MOBILE_COURT_ORIGIN_X,
    MOBILE_COURT_ORIGIN_Y,
    MOBILE_COURT_SCALE,
    MOBILE_H,
    MOBILE_W,
    PB_BALL,
    PB_COURT_RADIUS,
    PB_CREAM,
    PB_GROUND,
    PB_GROUND_DARK,
    PB_HILL_HI,
    PB_HILL_LO,
    PB_INK,
    PB_MOSS,
    PB_MOSS_SPOT,
    PB_OUTLINE_W,
    PB_P1,
    PB_P1_DARK,
    PB_P2,
    PB_P2_DARK,
    PB_PINK,
    PB_SUN,
    PB_WHITE,
)
from entities import goal_bounds, playable_rect
from title_typography import _load_font

S = MOBILE_COURT_SCALE


# --- 座標変換（横画面の論理座標 → 縦画面） ---

def logic_to_screen(x: float, y: float) -> tuple[float, float]:
    """左ゴール(P1)が下、右ゴールが上。等倍率なので当たり判定と見た目がずれない"""
    return (
        MOBILE_COURT_CX + (y - MOBILE_COURT_ORIGIN_Y) * S,
        MOBILE_COURT_CY + (MOBILE_COURT_ORIGIN_X - x) * S,
    )


def screen_dir_to_logic(dx: float, dy: float) -> tuple[float, float]:
    """縦画面の向き → 横画面の向き（logic_to_screen の回転の逆）"""
    return -dy, dx


def logic_heading_to_screen(heading: float) -> float:
    """論理座標の向き（rad）→ 画面上の向き"""
    dx, dy = math.cos(heading), math.sin(heading)
    return math.atan2(-dx, dy)


def scaled(v: float) -> float:
    return v * S


def court_screen_rect() -> pygame.Rect:
    rect = playable_rect()
    left, bottom = logic_to_screen(rect.left, rect.top)
    right, top = logic_to_screen(rect.right, rect.bottom)
    return pygame.Rect(round(left), round(top), round(right - left), round(bottom - top))


def goal_mouth_span() -> tuple[int, int]:
    top, bottom = goal_bounds()
    return round(logic_to_screen(0, top)[0]), round(logic_to_screen(0, bottom)[0])


# --- 下ごしらえ ---

def _ink_ring(surf: pygame.Surface, center, radius: float, width: int = PB_OUTLINE_W) -> None:
    pygame.draw.circle(surf, PB_INK, center, int(radius), width)


def _blob(surf: pygame.Surface, color, center, radius: float, *, outline: bool = True) -> None:
    pygame.draw.circle(surf, color, center, int(radius))
    if outline:
        _ink_ring(surf, center, radius)


def _petal_arc(cx: float, cy: float, radius: float, count: int, a0: float, a1: float):
    for i in range(count):
        t = i / max(1, count - 1)
        ang = a0 + (a1 - a0) * t
        yield cx + math.cos(ang) * radius, cy + math.sin(ang) * radius


def _flower(surf: pygame.Surface, x: float, y: float, r: float, color, core=PB_SUN) -> None:
    for i in range(5):
        ang = -math.pi / 2 + i * math.tau / 5
        px, py = x + math.cos(ang) * r, y + math.sin(ang) * r
        pygame.draw.circle(surf, PB_INK, (int(px), int(py)), int(r * 0.78) + 3)
    for i in range(5):
        ang = -math.pi / 2 + i * math.tau / 5
        px, py = x + math.cos(ang) * r, y + math.sin(ang) * r
        pygame.draw.circle(surf, color, (int(px), int(py)), int(r * 0.78))
    pygame.draw.circle(surf, PB_INK, (int(x), int(y)), int(r * 0.6) + 3)
    pygame.draw.circle(surf, core, (int(x), int(y)), int(r * 0.6))


def _leaf(surf: pygame.Surface, x: float, y: float, r: float, angle: float, color) -> None:
    pts = []
    for ax, ay in ((1.0, 0.0), (0.05, 0.55), (-1.0, 0.0), (0.05, -0.55)):
        c, s = math.cos(angle), math.sin(angle)
        pts.append((int(x + (ax * c - ay * s) * r), int(y + (ax * s + ay * c) * r)))
    pygame.draw.polygon(surf, PB_INK, pts)
    inner = [(int(x + (px - x) * 0.74), int(y + (py - y) * 0.74)) for px, py in pts]
    pygame.draw.polygon(surf, color, inner)


def _grass_tuft(surf: pygame.Surface, x: float, y: float, h: float, color) -> None:
    for i, lean in enumerate((-0.42, 0.0, 0.42)):
        tip = (x + lean * h * 0.9, y - h * (0.72 + 0.14 * (i % 2)))
        pygame.draw.line(surf, PB_INK, (int(x), int(y)), (int(tip[0]), int(tip[1])), 7)
    for i, lean in enumerate((-0.42, 0.0, 0.42)):
        tip = (x + lean * h * 0.9, y - h * (0.72 + 0.14 * (i % 2)))
        pygame.draw.line(surf, color, (int(x), int(y)), (int(tip[0]), int(tip[1])), 3)


# --- コート ---

_court_cache: pygame.Surface | None = None


def court_surface() -> pygame.Surface:
    """庭とコート（静止物）。一度だけ焼いて毎フレーム 1 回ブリットする"""
    global _court_cache
    if _court_cache is None:
        surf = pygame.Surface((MOBILE_W, MOBILE_H)).convert()
        _build_court(surf)
        _court_cache = surf
    return _court_cache


def reset_court_cache() -> None:
    global _court_cache
    _court_cache = None


def _build_court(surf: pygame.Surface) -> None:
    rng = random.Random(20260301)
    surf.fill(PB_GROUND)

    # 庭の地面 — ざっくりした草のまだら
    for _ in range(90):
        x = rng.uniform(0, MOBILE_W)
        y = rng.uniform(0, MOBILE_H)
        pygame.draw.circle(surf, PB_GROUND_DARK, (int(x), int(y)), rng.randint(8, 22))

    court = court_screen_rect()
    mouth_a, mouth_b = goal_mouth_span()
    _draw_goal_arch(surf, mouth_a, mouth_b, court.top, PB_SUN, up=True)
    _draw_goal_arch(surf, mouth_a, mouth_b, court.bottom, PB_PINK, up=False)

    # 苔の広場
    pygame.draw.rect(surf, PB_INK, court.inflate(PB_OUTLINE_W * 2, PB_OUTLINE_W * 2),
                     border_radius=PB_COURT_RADIUS + PB_OUTLINE_W)
    pygame.draw.rect(surf, PB_MOSS, court, border_radius=PB_COURT_RADIUS)
    moss = pygame.Surface(court.size, pygame.SRCALPHA)
    for _ in range(120):
        x = rng.uniform(0, court.width)
        y = rng.uniform(0, court.height)
        pygame.draw.circle(moss, (*PB_MOSS_SPOT, 255), (int(x), int(y)), rng.randint(7, 24))
    mask = pygame.Surface(court.size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=PB_COURT_RADIUS)
    moss.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(moss, court.topleft)

    # ゴール口 — 広場のふちにまたがる門
    for y, color in ((court.top, PB_SUN), (court.bottom, PB_PINK)):
        mouth = pygame.Rect(0, 0, mouth_b - mouth_a, 38)
        mouth.center = (int((mouth_a + mouth_b) / 2), int(y))
        pygame.draw.rect(surf, PB_INK, mouth.inflate(PB_OUTLINE_W * 2, PB_OUTLINE_W * 2), border_radius=18)
        pygame.draw.rect(surf, PB_CREAM, mouth, border_radius=18)
        pygame.draw.line(surf, color, (mouth.left + 10, y), (mouth.right - 10, y), 8)

    # 中央の破線とまんなかの丸
    mid_y = court.centery
    dash, gap = 26, 20
    x = court.left + 24
    while x < court.right - 24:
        pygame.draw.line(surf, PB_WHITE, (x, mid_y), (min(x + dash, court.right - 24), mid_y), 7)
        x += dash + gap
    pygame.draw.circle(surf, PB_WHITE, (court.centerx, mid_y), 54, 7)

    # 庭の飾り（コートの外側）
    for x, y, r in ((504, 236, 13), (36, 744, 13), (506, 826, 15)):
        _flower(surf, x, y, r, PB_PINK)
    for x, y, ang in ((24, 420, -0.5), (516, 548, 0.4), (22, 622, 0.3), (518, 352, -0.3)):
        _leaf(surf, x, y, 30, ang, PB_HILL_HI)


def _draw_goal_arch(surf: pygame.Surface, x0: int, x1: int, y: int, color, *, up: bool) -> None:
    """ゴールは花びらのアーチ。広場の外側にふくらむ"""
    cx = (x0 + x1) / 2
    half = (x1 - x0) / 2
    depth = 46
    sign = -1 if up else 1
    petals = 5
    pr = half / 2.6
    base_y = y
    for pass_color, pad in ((PB_INK, PB_OUTLINE_W), (color, 0)):
        for px, py in _petal_arc(cx, base_y, half - pr * 0.75, petals, math.pi, math.tau):
            pygame.draw.circle(surf, pass_color, (int(px), int(base_y + sign * (base_y - py) * (depth / half))),
                               int(pr) + pad)
        pygame.draw.circle(surf, pass_color, (int(cx), int(base_y + sign * depth * 0.42)), int(pr * 1.18) + pad)



# --- 芋虫 ---

def palette(player: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    return (PB_P1, PB_P1_DARK) if player == 0 else (PB_P2, PB_P2_DARK)


def draw_tube(surf: pygame.Surface, points: list[tuple[float, float, float]], player: int) -> None:
    """点列を丸で埋めてシームレスな1本のチューブにする（凹凸・節目を出さない）

    輪郭をすべて先に打ってから中身を打つので、重なっても線が体を横切らない。
    """
    if not points:
        return
    body, _dark = palette(player)
    dense = _densify(points)
    for color, pad in ((PB_INK, PB_OUTLINE_W), (body, 0)):
        for x, y, r in dense:
            pygame.draw.circle(surf, color, (int(x), int(y)), int(r) + pad)


def _densify(points: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    """丸と丸のすき間が出ないよう、半径に対して十分細かく打ち直す"""
    out: list[tuple[float, float, float]] = [points[0]]
    for i in range(1, len(points)):
        x0, y0, r0 = points[i - 1]
        x1, y1, r1 = points[i]
        dist = math.hypot(x1 - x0, y1 - y0)
        step = max(3.0, min(r0, r1) * 0.26)
        n = max(1, int(dist / step))
        for k in range(1, n + 1):
            t = k / n
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, r0 + (r1 - r0) * t))
    return out


_face_cache: dict[tuple[int, int], pygame.Surface] = {}


def _face_surface(player: int, radius: int) -> pygame.Surface:
    """右（0rad）を向いた顔。使うときは heading だけ回す"""
    key = (player, radius)
    cached = _face_cache.get(key)
    if cached is not None:
        return cached
    _body, dark = palette(player)
    r = radius
    size = r * 4
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = size / 2
    eye_r = max(7.0, r * 0.46)
    sep = eye_r * 1.02
    fwd = r * 0.30
    # 触角
    for side in (-1, 1):
        base = (cx + r * 0.1, cy + side * r * 0.5)
        tip = (cx + r * 0.95, cy + side * r * 1.15)
        pygame.draw.line(surf, PB_INK, base, tip, 7)
        pygame.draw.circle(surf, PB_INK, (int(tip[0]), int(tip[1])), 8)
        pygame.draw.circle(surf, dark, (int(tip[0]), int(tip[1])), 5)
    for side in (-1, 1):
        ex, ey = cx + fwd, cy + side * sep
        pygame.draw.circle(surf, PB_INK, (int(ex), int(ey)), int(eye_r) + 3)
        pygame.draw.circle(surf, PB_WHITE, (int(ex), int(ey)), int(eye_r))
        px, py = ex + eye_r * 0.34, ey + side * eye_r * 0.1
        pygame.draw.circle(surf, PB_INK, (int(px), int(py)), max(3, int(eye_r * 0.47)))
        pygame.draw.circle(surf, PB_WHITE, (int(px - eye_r * 0.16), int(py - eye_r * 0.2)),
                           max(1, int(eye_r * 0.16)))
    # ほっぺと口
    pygame.draw.arc(surf, PB_INK, pygame.Rect(int(cx + r * 0.3), int(cy - r * 0.3), int(r * 0.7), int(r * 0.6)),
                    -1.0, 1.0, 5)
    _face_cache[key] = surf
    return surf


def draw_face(surf: pygame.Surface, x: float, y: float, radius: float, heading: float, player: int) -> None:
    """進行方向を見る大きな白目（heading は画面座標の rad）"""
    face = _face_surface(player, int(radius))
    rotated = pygame.transform.rotate(face, -math.degrees(heading))
    surf.blit(rotated, rotated.get_rect(center=(int(x), int(y))))


def dash_tail_points(x: float, y: float, heading: float, radius: float, phase: float) -> list[tuple[float, float, float]]:
    """ダッシュ中の身体 — 後ろへ波打って伸びる"""
    pts: list[tuple[float, float, float]] = []
    fx, fy = math.cos(heading), math.sin(heading)
    px, py = -fy, fx
    length = radius * 3.9
    for i in range(7):
        t = i / 6
        wave = math.sin(phase * 19.0 - t * 5.4) * radius * 0.42 * t
        r = radius * (1.0 - 0.46 * t * t)
        pts.append((x - fx * length * t + px * wave, y - fy * length * t + py * wave, r))
    pts.reverse()
    return pts


# --- ボール（てんとう虫） ---

_ladybug_cache: dict[int, pygame.Surface] = {}


def _ladybug_surface(radius: int) -> pygame.Surface:
    cached = _ladybug_cache.get(radius)
    if cached is not None:
        return cached
    scale = 3
    r = radius * scale
    size = r * 2 + 16 * scale
    big = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    pygame.draw.circle(big, PB_INK, (c, c), r + 3 * scale)
    pygame.draw.circle(big, PB_BALL, (c, c), r)
    # 頭（進行方向=右）
    head = pygame.Rect(0, 0, int(r * 0.86), int(r * 1.7))
    head.center = (int(c + r * 0.66), c)
    pygame.draw.ellipse(big, PB_INK, head)
    # 中央の線
    pygame.draw.line(big, PB_INK, (c - int(r * 0.92), c), (c + int(r * 0.3), c), 3 * scale)
    # 黒い点4つ
    for sx, sy in ((-0.46, -0.44), (-0.46, 0.44), (0.05, -0.5), (0.05, 0.5)):
        pygame.draw.circle(big, PB_INK, (int(c + r * sx), int(c + r * sy)), int(r * 0.2))
    # つや
    pygame.draw.circle(big, (255, 255, 255, 110), (int(c - r * 0.38), int(c - r * 0.52)), int(r * 0.2))
    # 目
    for side in (-1, 1):
        ex, ey = c + r * 0.92, c + side * r * 0.36
        pygame.draw.circle(big, PB_WHITE, (int(ex), int(ey)), int(r * 0.17))
    small = pygame.transform.smoothscale(big, (size // scale, size // scale))
    _ladybug_cache[radius] = small
    return small


def draw_ladybug(surf: pygame.Surface, x: float, y: float, radius: float, heading: float) -> None:
    base = _ladybug_surface(int(radius))
    rotated = pygame.transform.rotate(base, -math.degrees(heading))
    surf.blit(rotated, rotated.get_rect(center=(int(x), int(y))))


# --- UI 部品 ---

_text_cache: dict[tuple, pygame.Surface] = {}
_font_cache: dict[tuple[int, bool], pygame.font.Font] = {}


def font(size: int, *, medium: bool = False) -> pygame.font.Font:
    key = (size, medium)
    cached = _font_cache.get(key)
    if cached is None:
        cached = _load_font(size, medium=medium)
        _font_cache[key] = cached
    return cached


def text(label: str, size: int, color=PB_INK, *, medium: bool = False,
         outline: tuple[int, int, int] | None = None, outline_px: int = 4) -> pygame.Surface:
    """文字は焼いて使い回す（毎フレームの文字描画はスマホで重い）"""
    key = (label, size, color, medium, outline, outline_px)
    cached = _text_cache.get(key)
    if cached is not None:
        return cached
    face = font(size, medium=medium)
    body = face.render(label, True, color)
    if outline is None:
        _text_cache[key] = body
        return body
    pad = outline_px
    out = pygame.Surface((body.get_width() + pad * 2, body.get_height() + pad * 2), pygame.SRCALPHA)
    stamp = face.render(label, True, outline)
    for ang in range(0, 360, 30):
        dx = math.cos(math.radians(ang)) * pad
        dy = math.sin(math.radians(ang)) * pad
        out.blit(stamp, (pad + dx, pad + dy))
    out.blit(body, (pad, pad))
    _text_cache[key] = out
    return out


def text_fit(label: str, size: int, color=PB_INK, *, max_width: int = MOBILE_W - 36,
             medium: bool = False, outline: tuple[int, int, int] | None = None,
             outline_px: int = 4) -> pygame.Surface:
    """画面からはみ出す文字は縮める"""
    key = ("fit", label, size, color, max_width, medium, outline, outline_px)
    cached = _text_cache.get(key)
    if cached is not None:
        return cached
    glyph = text(label, size, color, medium=medium, outline=outline, outline_px=outline_px)
    if glyph.get_width() > max_width:
        k = max_width / glyph.get_width()
        glyph = pygame.transform.smoothscale(
            glyph, (int(glyph.get_width() * k), int(glyph.get_height() * k)),
        )
    _text_cache[key] = glyph
    return glyph


def draw_pill(surf: pygame.Surface, rect: pygame.Rect, fill, *, pressed: float = 0.0,
              label: str = "", label_size: int = 30, label_color=PB_INK) -> None:
    """丸いピル型ボタン。押すと弾む"""
    squash = 1.0 - 0.07 * pressed
    grow = 1.0 + 0.05 * pressed
    draw_rect = pygame.Rect(0, 0, int(rect.width * grow), int(rect.height * squash))
    draw_rect.center = rect.center
    radius = draw_rect.height // 2
    shadow = draw_rect.move(0, 6)
    pygame.draw.rect(surf, PB_INK, shadow.inflate(PB_OUTLINE_W, PB_OUTLINE_W), border_radius=radius)
    pygame.draw.rect(surf, PB_INK, draw_rect.inflate(PB_OUTLINE_W * 2, PB_OUTLINE_W * 2), border_radius=radius)
    pygame.draw.rect(surf, fill, draw_rect, border_radius=radius)
    highlight = pygame.Rect(draw_rect.left + 14, draw_rect.top + 7, draw_rect.width - 28, max(6, draw_rect.height // 6))
    pygame.draw.rect(surf, (*PB_WHITE, 90), highlight, border_radius=highlight.height // 2)
    if label:
        glyph = text(label, label_size, label_color)
        surf.blit(glyph, glyph.get_rect(center=draw_rect.center))


_badge_cache: dict[tuple[int, int], pygame.Surface] = {}


def score_badge(player: int, score: int, radius: int = 46) -> pygame.Surface:
    key = (player, score)
    cached = _badge_cache.get(key)
    if cached is not None:
        return cached
    body, dark = palette(player)
    size = radius * 2 + 16
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    pygame.draw.circle(surf, PB_INK, (c, c + 4), radius + PB_OUTLINE_W)
    pygame.draw.circle(surf, PB_INK, (c, c), radius + PB_OUTLINE_W)
    pygame.draw.circle(surf, body, (c, c), radius)
    pygame.draw.circle(surf, dark, (c, c), radius, 4)
    glyph = text(str(score), 58, PB_WHITE, outline=PB_INK, outline_px=4)
    surf.blit(glyph, glyph.get_rect(center=(c, c - 2)))
    _badge_cache[key] = surf
    return surf


def draw_pause_button(surf: pygame.Surface, rect: pygame.Rect, pressed: float = 0.0) -> None:
    grow = 1.0 + 0.08 * pressed
    r = int(rect.width / 2 * grow)
    c = rect.center
    pygame.draw.circle(surf, PB_INK, (c[0], c[1] + 4), r + PB_OUTLINE_W)
    pygame.draw.circle(surf, PB_INK, c, r + PB_OUTLINE_W)
    pygame.draw.circle(surf, PB_CREAM, c, r)
    for offset in (-10, 10):
        bar = pygame.Rect(c[0] + offset - 5, c[1] - 14, 10, 28)
        pygame.draw.rect(surf, PB_INK, bar, border_radius=4)


# --- タイトルの庭 ---

_title_bg_cache: pygame.Surface | None = None


def title_backdrop() -> pygame.Surface:
    global _title_bg_cache
    if _title_bg_cache is None:
        surf = pygame.Surface((MOBILE_W, MOBILE_H)).convert()
        _build_title_backdrop(surf)
        _title_bg_cache = surf
    return _title_bg_cache


def reset_title_cache() -> None:
    global _title_bg_cache
    _title_bg_cache = None


def _hill(surf: pygame.Surface, cy: int, height: int, color) -> None:
    rect = pygame.Rect(-120, cy, MOBILE_W + 240, height * 2)
    pygame.draw.ellipse(surf, PB_INK, rect.inflate(0, PB_OUTLINE_W * 2))
    pygame.draw.ellipse(surf, color, rect)


def _build_title_backdrop(surf: pygame.Surface) -> None:
    rng = random.Random(7788)
    surf.fill(PB_CREAM)

    # 太陽（右上）
    sun = (MOBILE_W - 62, 68)
    for i in range(12):
        ang = i * math.tau / 12
        tip = (sun[0] + math.cos(ang) * 88, sun[1] + math.sin(ang) * 88)
        pygame.draw.line(surf, PB_INK, sun, (int(tip[0]), int(tip[1])), 10)
    for i in range(12):
        ang = i * math.tau / 12
        tip = (sun[0] + math.cos(ang) * 84, sun[1] + math.sin(ang) * 84)
        pygame.draw.line(surf, PB_SUN, sun, (int(tip[0]), int(tip[1])), 6)
    _blob(surf, PB_SUN, sun, 44)

    # ふわふわ雲
    for cx, cy, r in ((74, 92, 26), (120, 104, 19), (40, 108, 17)):
        _blob(surf, PB_WHITE, (cx, cy), r)

    # 丘2段（ボタンの下）
    _hill(surf, 824, 110, PB_HILL_HI)
    _hill(surf, 886, 130, PB_HILL_LO)

    # 花と草
    for x, y, r in ((58, 876, 22), (468, 862, 18), (196, 912, 16), (372, 930, 20)):
        _flower(surf, x, y, r, PB_PINK)
    for _ in range(10):
        x = rng.uniform(10, MOBILE_W - 10)
        y = rng.uniform(876, 952)
        _grass_tuft(surf, x, y, rng.uniform(26, 44), PB_HILL_HI if y > 910 else PB_HILL_LO)
    for x, y, r in ((112, 948, 22), (462, 938, 19)):
        _flower(surf, x, y, r, PB_WHITE, core=PB_SUN)


def draw_title_worm(surf: pygame.Surface, now: float) -> None:
    """タイトルの大きな緑の芋虫（丘の上をゆっくり波打つ）"""
    radius = 31.0
    pts: list[tuple[float, float, float]] = []
    for i in range(11):
        t = i / 10
        x = 62 + t * 286
        y = 364 + math.sin(now * 1.1 + t * 3.0) * 12 - t * 6
        pts.append((x, y, radius))
    draw_tube(surf, pts, 0)
    hx, hy, _ = pts[-1]
    prev = pts[-3]
    heading = math.atan2(hy - prev[1], hx - prev[0])
    draw_face(surf, hx, hy, radius, heading, 0)


def draw_title_ladybug(surf: pygame.Surface, now: float) -> None:
    x = 456 + math.sin(now * 0.8) * 9
    y = 344 + math.sin(now * 1.6) * 6
    draw_ladybug(surf, x, y, 40, math.radians(-22))


_rot_cache: dict[tuple, pygame.Surface] = {}


def _rotated_text(label: str, size: int, color, angle: float) -> pygame.Surface:
    key = (label, size, color, angle)
    cached = _rot_cache.get(key)
    if cached is None:
        cached = pygame.transform.rotate(
            text_fit(label, size, color, outline=PB_INK, outline_px=7), angle,
        )
        _rot_cache[key] = cached
    return cached


def draw_logo(surf: pygame.Surface, center: tuple[int, int], now: float) -> None:
    """「芋虫」緑 ×「ホッケー」赤 の絵本ロゴ"""
    from constants import PB_LOGO_GREEN, PB_LOGO_RED

    tilt1 = _rotated_text("芋虫", 104, PB_LOGO_GREEN, 4)
    tilt2 = _rotated_text("ホッケー", 88, PB_LOGO_RED, -3)
    bob = math.sin(now * 1.7) * 4
    surf.blit(tilt1, tilt1.get_rect(center=(center[0], center[1] - 54 + bob)))
    surf.blit(tilt2, tilt2.get_rect(center=(center[0], center[1] + 52 - bob)))
