"""ネオン風描画ヘルパー"""

import pygame


def draw_neon_line(
    surf: pygame.Surface,
    p1: tuple[int, int],
    p2: tuple[int, int],
    color: tuple[int, int, int],
    fade: float = 1.0,
    pulse: float = 0.0,
) -> None:
    f = max(0.0, min(1.0, fade)) * (0.82 + 0.18 * pulse)
    r, g, b = color
    layers = (
        (16, (int(r * 0.12 * f), int(g * 0.12 * f), int(b * 0.12 * f))),
        (10, (int(r * 0.35 * f), int(g * 0.35 * f), int(b * 0.35 * f))),
        (6, (int(min(255, r * 0.7 * f)), int(min(255, g * 0.7 * f)), int(min(255, b * 0.7 * f)))),
        (3, (int(min(255, r * f)), int(min(255, g * f)), int(min(255, b * f)))),
        (1, (int(255 * f), int(255 * f), int(255 * f))),
    )
    for width, c in layers:
        pygame.draw.line(surf, c, p1, p2, width)


def draw_neon_capsule(
    surf: pygame.Surface,
    p1: tuple[int, int],
    p2: tuple[int, int],
    color: tuple[int, int, int],
    fade: float = 1.0,
    pulse: float = 0.0,
    cap_radius: int = 8,
) -> None:
    """線分＋両端の半円（カプセル形）。壁の当たり判定と見た目を揃える。"""
    draw_neon_line(surf, p1, p2, color, fade=fade, pulse=pulse)
    r = max(2, cap_radius)
    draw_neon_disc(surf, p1[0], p1[1], r, color, fade=fade, pulse=pulse)
    draw_neon_disc(surf, p2[0], p2[1], r, color, fade=fade, pulse=pulse)


def draw_neon_disc(
    surf: pygame.Surface,
    x: int,
    y: int,
    radius: int,
    color: tuple[int, int, int],
    fade: float = 1.0,
    pulse: float = 0.0,
) -> None:
    f = max(0.0, min(1.0, fade)) * (0.85 + 0.15 * pulse)
    r, g, b = color
    for scale, alpha in ((1.55, 0.12), (1.25, 0.28), (1.0, 0.55), (0.72, 1.0)):
        rad = max(1, int(radius * scale))
        c = (
            int(min(255, r * alpha * f)),
            int(min(255, g * alpha * f)),
            int(min(255, b * alpha * f)),
        )
        pygame.draw.circle(surf, c, (x, y), rad)
        pygame.draw.circle(surf, (int(255 * f), int(255 * f), int(255 * f)), (x, y), max(1, radius // 3))


def make_window_icon() -> pygame.Surface:
    """ウィンドウアイコン（32×32・芋虫＋葉っぱ）"""
    from caterpillar_art import draw_body_stamp, draw_caterpillar_head, draw_leaf_puck

    icon = pygame.Surface((32, 32), pygame.SRCALPHA)
    icon.fill((6, 14, 8, 255))
    pygame.draw.rect(icon, (180, 220, 160), (2, 2, 28, 28), 1)
    draw_body_stamp(icon, 10, 20, 0.0, 3.5, 0)
    draw_body_stamp(icon, 15, 18, 0.0, 3.5, 0)
    draw_caterpillar_head(icon, 21, 16, 7, 0, 0.0, 0.0, (0, 255, 255))
    draw_leaf_puck(icon, 24, 25, 4, 0.0)
    return icon
