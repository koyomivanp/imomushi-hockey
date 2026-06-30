"""アイテム効果（重ね掛け対応）"""

import math
import random

from constants import (
    ASSIST_DURATION,
    BAR_DURATION,
    BIG_PADDLE_DURATION,
    FENCE_DELAY,
    FENCE_DURATION,
    FENCE_HALF_WIDTH,
    FENCE_MIN_LENGTH,
    GUARD_DEFENSE_X_RATIO,
    GUARD_FIRE_INTERVAL,
    GUARD_MAX_COUNT,
    GUARD_THREAT_MIN,
    MAX_PUCKS,
    PUCK_BURST_COUNT,
    RAY_BALL_RADIUS,
    RAY_BALL_SPEED,
    RAY_KNOCKBACK,
    WIND_ACCEL,
    WIND_DURATION,
)
from entities import (
    ITEM_LABELS,
    ITEM_TYPES,
    Bar,
    FallingItem,
    Fence,
    GuardSoldier,
    Paddle,
    PendingFence,
    Puck,
    RayShot,
    WindEffect,
    random_corner_item_motion,
    spawn_puck_burst,
    table_rect,
)
from physics import apply_knockback_to_paddle, apply_knockback_to_puck, circle_overlap, resolve_ray_bar


def random_item_kind() -> str:
    return random.choice(ITEM_TYPES)


def spawn_falling_item() -> FallingItem:
    x, y, vx, vy = random_corner_item_motion()
    return FallingItem(
        kind=random_item_kind(),
        x=x,
        y=y,
        vx=vx,
        vy=vy,
    )


def stack_label(kind: str, level: int) -> str:
    base = ITEM_LABELS.get(kind, kind.upper())
    if level >= 2:
        return f"{base} x{level}"
    return base


def guard_fire_interval(level: int) -> float:
    return GUARD_FIRE_INTERVAL / max(1, level)


def guard_ray_stats(level: int, size_scale: float) -> tuple[float, float]:
    ball_speed = RAY_BALL_SPEED * (1.0 + 0.12 * (level - 1))
    knockback = RAY_KNOCKBACK * (1.0 + 0.15 * (level - 1)) * size_scale
    return ball_speed, knockback


def wind_accel_for(wind: WindEffect) -> float:
    return WIND_ACCEL * (0.65 + 0.35 * wind.level)


def _finalize_fence_end(
    x1: float, y1: float, x2: float, y2: float, last_dir: tuple[float, float],
) -> tuple[float, float]:
    dx = x2 - x1
    dy = y2 - y1
    if math.hypot(dx, dy) >= FENCE_MIN_LENGTH:
        return x2, y2
    lx, ly = last_dir
    length = math.hypot(lx, ly)
    if length < 1e-6:
        lx, ly = 0.0, -1.0
        length = 1.0
    return x1 + lx / length * FENCE_MIN_LENGTH, y1 + ly / length * FENCE_MIN_LENGTH


def activate_pending_fence(
    pending: PendingFence,
    paddle: Paddle,
    now: float,
    level: int = 1,
) -> Fence:
    x2, y2 = _finalize_fence_end(pending.x1, pending.y1, paddle.x, paddle.y, paddle.last_dir)
    extra = 0.15 * (level - 1)
    return Fence(
        owner=pending.owner,
        x1=pending.x1,
        y1=pending.y1,
        x2=x2,
        y2=y2,
        until=now + FENCE_DURATION * (1.0 + extra),
        created_at=now,
        half_width=FENCE_HALF_WIDTH,
    )


def _spawn_guard_squad(owner: int, level: int, now: float, paddle: Paddle) -> list[GuardSoldier]:
    rect = table_rect()
    spawn_x = rect.left - 52 if owner == 0 else rect.right + 52
    count = min(GUARD_MAX_COUNT, max(1, level))
    squad: list[GuardSoldier] = []
    for i in range(count):
        t = (i + 1) / (count + 1)
        y = rect.top + rect.height * t
        squad.append(GuardSoldier(
            owner=owner,
            x=spawn_x,
            y=y,
            until=now + ASSIST_DURATION,
            level=level,
            ray_next_fire=now + 0.2 * i,
        ))
    return squad


def _clear_owner_guards(guards: list[GuardSoldier], owner: int) -> None:
    for guard in list(guards):
        if guard.owner == owner:
            guards.remove(guard)


def apply_item(
    kind: str,
    owner: int,
    paddles: list[Paddle],
    pucks: list[Puck],
    guards: list[GuardSoldier],
    pending_fences: list[PendingFence],
    fences: list[Fence],
    winds: list[WindEffect],
    bars: list[Bar],
    now: float,
) -> str:
    paddle = paddles[owner]
    level = paddle.add_stack(kind)

    if kind == "assist":
        _clear_owner_guards(guards, owner)
        squad = _spawn_guard_squad(owner, level, now, paddle)
        guards.extend(squad)
        return f"{stack_label(kind, level)} x{len(squad)}"
    elif kind == "big_paddle":
        paddle.big_until = now + BIG_PADDLE_DURATION
    elif kind == "puck_burst":
        room = MAX_PUCKS - len(pucks)
        count = PUCK_BURST_COUNT + (level - 1) * 4
        to_add = min(count, room)
        if to_add > 0:
            pucks.extend(spawn_puck_burst(to_add))
    elif kind == "fence":
        pending_fences[:] = [p for p in pending_fences if p.owner != owner]
        pending_fences.append(
            PendingFence(
                owner=owner,
                x1=paddle.x,
                y1=paddle.y,
                activate_at=now + FENCE_DELAY / max(1, level * 0.6),
            )
        )
    elif kind == "wind":
        existing = next((w for w in winds if w.owner == owner), None)
        if existing is not None:
            existing.level = level
            existing.until = now + WIND_DURATION
            existing.started = now
        else:
            winds.append(WindEffect(owner=owner, started=now, until=now + WIND_DURATION, level=level))
    elif kind == "bar":
        existing = next((b for b in bars if b.owner == owner), None)
        if existing is not None:
            existing.level = level
            existing.until = now + BAR_DURATION
            existing.started = now
            existing.segment_hits.clear()
            existing.broken_segments.clear()
        else:
            bars.append(Bar(owner=owner, started=now, until=now + BAR_DURATION, level=level))

    return stack_label(kind, level)


def try_collect_item(item: FallingItem, paddles: list[Paddle], now: float) -> int | None:
    for p in paddles:
        dx = item.x - p.x
        dy = item.y - p.y
        if dx * dx + dy * dy <= (item.radius + p.radius(now)) ** 2:
            return p.player
    return None


def _puck_threat_score(puck: Puck, owner: int, defender_x: float, defender_y: float) -> float:
    """自ゴールに近く、こちらへ来ているパックほど高スコア"""
    rect = table_rect()
    if owner == 0:
        dist_goal = max(puck.x - rect.left, 20.0)
        toward = max(0.0, -puck.vx)
    else:
        dist_goal = max(rect.right - puck.x, 20.0)
        toward = max(0.0, puck.vx)
    dist_defender = math.hypot(puck.x - defender_x, puck.y - defender_y)
    return toward * 2.0 + 800.0 / dist_goal + 120.0 / max(dist_defender, 40.0)


def pick_guard_target(guard: GuardSoldier, pucks: list[Puck]) -> Puck | None:
    best: Puck | None = None
    best_score = GUARD_THREAT_MIN
    for puck in pucks:
        if puck.carried_by >= 0:
            continue
        score = _puck_threat_score(puck, guard.owner, guard.x, guard.y)
        if score > best_score:
            best_score = score
            best = puck
    return best


def _ray_lead_aim_point(
    shooter_x: float, shooter_y: float, puck: Puck, ball_speed: float,
) -> tuple[float, float]:
    rx = puck.x - shooter_x
    ry = puck.y - shooter_y
    pvx, pvy = puck.vx, puck.vy
    bs = ball_speed

    t = math.hypot(rx, ry) / bs
    a = pvx * pvx + pvy * pvy - bs * bs
    b = 2.0 * (rx * pvx + ry * pvy)
    c = rx * rx + ry * ry
    if abs(a) > 1e-6:
        disc = b * b - 4.0 * a * c
        if disc >= 0:
            sqrt_d = math.sqrt(disc)
            candidates = [(-b - sqrt_d) / (2.0 * a), (-b + sqrt_d) / (2.0 * a)]
            positive = [tc for tc in candidates if tc > 0.02]
            if positive:
                t = min(positive)

    t = min(t, 1.2)
    return puck.x + pvx * t, puck.y + pvy * t


def fire_guard_ray(guard: GuardSoldier, pucks: list[Puck]) -> RayShot | None:
    target = pick_guard_target(guard, pucks)
    if target is None:
        return None

    ball_speed, knockback = guard_ray_stats(guard.level, guard.size_scale)
    aim_x, aim_y = _ray_lead_aim_point(guard.x, guard.y, target, ball_speed)

    dx = aim_x - guard.x
    dy = aim_y - guard.y
    length = math.hypot(dx, dy)
    if length < 1e-6:
        direction = 1 if guard.owner == 0 else -1
        dx, dy = float(direction), 0.0
        length = 1.0
    else:
        dx /= length
        dy /= length

    return RayShot(
        x=guard.x,
        y=guard.y,
        vx=dx * ball_speed,
        vy=dy * ball_speed,
        owner=guard.owner,
        radius=RAY_BALL_RADIUS * guard.size_scale,
        knockback=knockback,
    )


def update_ray_shot(
    shot: RayShot,
    dt: float,
    pucks: list[Puck],
    paddles: list[Paddle],
    bars: list[Bar],
    now: float,
) -> bool:
    """弾を進め、命中 or 場外なら True（削除）"""
    shot.x += shot.vx * dt
    shot.y += shot.vy * dt

    rect = table_rect()
    m = shot.radius + 2
    if (
        shot.x < rect.left - m
        or shot.x > rect.right + m
        or shot.y < rect.top - m
        or shot.y > rect.bottom + m
    ):
        return True

    kb = shot.knockback if shot.knockback > 0 else RAY_KNOCKBACK

    for puck in pucks:
        if puck.carried_by >= 0:
            continue
        if circle_overlap(shot.x, shot.y, shot.radius, puck.x, puck.y, puck.radius):
            apply_knockback_to_puck(puck, shot.x - shot.vx * dt, shot.y - shot.vy * dt, kb)
            return True

    for bar in bars:
        if bar.owner == shot.owner:
            continue
        if resolve_ray_bar(shot, bar, paddles[bar.owner], now):
            return True

    for pad in paddles:
        if pad.player == shot.owner:
            continue
        if circle_overlap(shot.x, shot.y, shot.radius, pad.x, pad.y, pad.radius(now)):
            apply_knockback_to_paddle(
                pad, shot.x - shot.vx * dt, shot.y - shot.vy * dt, kb, now,
            )
            return True

    return False
