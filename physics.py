"""衝突・反射・押し出し"""

import math
import random
from typing import Optional

from constants import (
    BAR_BOOST,
    BAR_HALF_WIDTH,
    ELASTICITY,
    FENCE_BOOST,
    FENCE_HALF_WIDTH,
    HIT_JITTER_ANGLE,
    HIT_JITTER_CHANCE,
    HIT_JITTER_HEAD_CHANCE,
    PADDLE_CHASE_HIT_SPEED,
    PADDLE_CLOSE_PUCK_IGNORE_TIME,
    PADDLE_CLOSE_PUCK_IMPULSE,
    PADDLE_CLOSE_PUCK_MARGIN,
    PADDLE_CLOSE_PUCK_MIN_EXIT,
    PADDLE_CLOSE_PUCK_SEPARATION,
    PADDLE_CLOSE_PUCK_SPEED_RATIO,
    PADDLE_DASH_PUCK_IGNORE_TIME,
    PADDLE_DASH_PUCK_IMPULSE,
    PADDLE_DASH_PUCK_MIN_EXIT,
    PADDLE_DASH_PUCK_SEPARATION,
    PADDLE_DASH_PUCK_SPEED_RATIO,
    PADDLE_HEAD_ON_DOT,
    PADDLE_HEAD_ON_IGNORE_TIME,
    PADDLE_HEAD_ON_MIN_EXIT,
    PADDLE_HEAD_ON_MIN_EXIT_RATIO,
    PADDLE_HEAD_ON_REL_SEP,
    PADDLE_HEAD_ON_SEP_MARGIN,
    PADDLE_HIT_COOLDOWN,
    PADDLE_HIT_FORGIVENESS,
    PADDLE_KB_DRAG,
    PADDLE_KB_IMPULSE,
    PADDLE_PUCK_IMPULSE,
    PADDLE_PUCK_IGNORE_TIME,
    PADDLE_PUCK_SEPARATION,
    PADDLE_SPEED,
    PUCK_PADDLE_MIN_EXIT,
    WALL_GRIND_ALLOW_TIME,
    WALL_GRIND_MARGIN,
    WALL_GRIND_MAX_SPEED,
    WALL_GRIND_SLIP_EXIT,
    WALL_GRIND_SLIP_IGNORE,
    WALL_PINCH_ESCAPE_BIAS,
    RALLY_BOUNCE_BOOST,
    RALLY_BOUNCE_MAX_MULT,
    PUCK_MAX_SPEED,
)
from constants import (
    GUARD_DEFENSE_X_RATIO,
    GUARD_ENTER_SPEED,
)
from entities import Assist, Bar, Fence, GuardSoldier, Paddle, Puck, clamp_speed, goal_bounds, table_rect


def _normalize(dx: float, dy: float) -> tuple[float, float]:
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return 0.0, 0.0
    return dx / d, dy / d


def circle_overlap(
    x1: float, y1: float, r1: float,
    x2: float, y2: float, r2: float,
) -> Optional[tuple[float, float, float]]:
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    min_dist = r1 + r2
    if dist >= min_dist or dist < 1e-9:
        return None
    if dist < 1e-9:
        return 0.0, -1.0, min_dist
    nx, ny = dx / dist, dy / dist
    return nx, ny, min_dist - dist


def resolve_puck_wall(puck: Puck) -> tuple[Optional[int], bool]:
    """壁反射。返値: (ゴール側 0=P1左 1=P2右, 壁バウンドしたか)"""
    if puck.scored:
        return None, False
    rect = table_rect()
    r = puck.radius
    goal_top, goal_bottom = goal_bounds()
    scored_side: Optional[int] = None
    bounced = False

    # 上下壁（全面）
    if puck.y - r < rect.top:
        puck.y = rect.top + r
        puck.vy = abs(puck.vy) * ELASTICITY
        bounced = True
    elif puck.y + r > rect.bottom:
        puck.y = rect.bottom - r
        puck.vy = -abs(puck.vy) * ELASTICITY
        bounced = True

    # 左壁（P1ゴール）
    if puck.x - r < rect.left:
        if goal_top <= puck.y <= goal_bottom:
            scored_side = 0
            puck.scored = True
        else:
            puck.x = rect.left + r
            puck.vx = abs(puck.vx) * ELASTICITY
            bounced = True

    # 右壁（P2ゴール）
    if puck.x + r > rect.right:
        if goal_top <= puck.y <= goal_bottom:
            scored_side = 1
            puck.scored = True
        else:
            puck.x = rect.right - r
            puck.vx = -abs(puck.vx) * ELASTICITY
            bounced = True

    if bounced and scored_side is None:
        _apply_rally_escalation(puck)

    puck.vx, puck.vy = clamp_speed(puck.vx, puck.vy)
    return scored_side, bounced


def puck_paddle_in_ignore(puck: Puck, paddle: Paddle, now: float) -> bool:
    until = puck.paddle_ignore_until.get(paddle.player, 0.0)
    return now < until


def mark_puck_paddle_hit(puck: Puck, paddle: Paddle, now: float, ignore_time: float | None = None) -> None:
    puck.paddle_ignore_players.add(paddle.player)
    if ignore_time is None:
        ignore_time = PADDLE_PUCK_IGNORE_TIME
    puck.paddle_ignore_until[paddle.player] = now + ignore_time


def _paddle_move_unit(paddle: Paddle) -> tuple[float, float, float]:
    speed = math.hypot(paddle.vx, paddle.vy)
    if speed > 24.0:
        return paddle.vx / speed, paddle.vy / speed, speed
    ldx, ldy = paddle.last_dir
    llen = math.hypot(ldx, ldy)
    if llen > 1e-6:
        return ldx / llen, ldy / llen, 0.0
    return 1.0, 0.0, 0.0


def _is_head_on_hit(paddle: Paddle, pnx: float, pny: float) -> bool:
    mvx, mvy, _ = _paddle_move_unit(paddle)
    return abs(mvx * pnx + mvy * pny) >= PADDLE_HEAD_ON_DOT


def _wall_cling_axis(puck: Puck) -> tuple[bool, float]:
    """上下壁際。返値: (壁際か, コート内方向の y 成分)"""
    rect = table_rect()
    r = puck.radius
    if puck.y - r <= rect.top + WALL_GRIND_MARGIN:
        return True, 1.0
    if puck.y + r >= rect.bottom - WALL_GRIND_MARGIN:
        return True, -1.0
    return False, 0.0


def _is_wall_pinch(puck: Puck, paddle: Paddle) -> tuple[bool, float]:
    """上下壁と自機に挟まれている（自機がコート側から壁へ押している）"""
    near_wall, inward_y = _wall_cling_axis(puck)
    if not near_wall:
        return False, 0.0
    if inward_y > 0.0:
        if paddle.y < puck.y - 6.0:
            return False, 0.0
    elif paddle.y > puck.y + 6.0:
        return False, 0.0
    return True, inward_y


def _reset_wall_grind(puck: Puck) -> None:
    puck.grind_started_at = -1.0
    puck.grind_paddle = -1
    puck.grind_escape_x = 0.0


def _pick_escape_x(puck: Puck) -> float:
    if puck.grind_escape_x != 0.0:
        return puck.grind_escape_x
    rect = table_rect()
    room_l = puck.x - rect.left
    room_r = rect.right - puck.x
    if random.random() < WALL_PINCH_ESCAPE_BIAS:
        side = -1.0 if room_l >= room_r else 1.0
    else:
        side = -1.0 if random.random() < 0.5 else 1.0
    puck.grind_escape_x = side
    return side


def _unstick_from_wall(puck: Puck, inward_y: float) -> None:
    rect = table_rect()
    r = puck.radius
    if inward_y > 0.0:
        puck.y = max(puck.y, rect.top + r + 3.0)
    elif inward_y < 0.0:
        puck.y = min(puck.y, rect.bottom - r - 3.0)


def _maybe_jitter_dir(sx: float, sy: float, *, head_on: bool) -> tuple[float, float]:
    chance = HIT_JITTER_HEAD_CHANCE if head_on else HIT_JITTER_CHANCE
    if random.random() > chance:
        return sx, sy
    spread = HIT_JITTER_ANGLE * (0.4 + random.random() * 0.6)
    sign = 1.0 if random.random() < 0.5 else -1.0
    px, py = -sy * sign, sx * sign
    jx, jy = _normalize(sx + px * spread, sy + py * spread)
    if jx == 0.0 and jy == 0.0:
        return sx, sy
    return jx, jy


def _boost_strike_dir(paddle: Paddle, pnx: float, pny: float) -> tuple[float, float]:
    head_on = _is_head_on_hit(paddle, pnx, pny)
    if head_on:
        mx, my, _ = _paddle_move_unit(paddle)
        sx, sy = mx, my
    else:
        sx, sy = pnx, pny
    return _maybe_jitter_dir(sx, sy, head_on=head_on)


def _resolve_puck_paddle_overlap(
    puck: Puck,
    paddle: Paddle,
    pr: float,
    separation: float,
    pnx: float,
    pny: float,
    dist: float,
    *,
    wall_pinch: bool,
    pinch_inward: float,
) -> tuple[float, float, float, float]:
    """円同士の重なりを接点法線方向にだけ押し出す（瞬間移動しない）"""
    min_sep = pr + puck.radius + separation
    if dist >= min_sep:
        return dist, pnx, pny, min_sep
    overlap = min_sep - dist
    if wall_pinch:
        ex = _pick_escape_x(puck)
        puck.x += pnx * overlap * 0.48 + ex * overlap * 0.42
        puck.y += pny * overlap * 0.38
        _unstick_from_wall(puck, pinch_inward)
    else:
        puck.x += pnx * overlap
        puck.y += pny * overlap
    dx = puck.x - paddle.x
    dy = puck.y - paddle.y
    new_dist = math.hypot(dx, dy)
    if new_dist > 1e-6:
        return new_dist, dx / new_dist, dy / new_dist, min_sep
    return min_sep, pnx, pny, min_sep


def _apply_wall_grind_hit(puck: Puck, paddle: Paddle) -> None:
    """挟み状態の短時間: 選ばれた左右へ沿壁スライド（壁へは押さない）"""
    ex = _pick_escape_x(puck)
    mvx, mvy, speed = _paddle_move_unit(paddle)
    if speed < 1.0:
        mvx, mvy = ex, 0.0
        speed = PADDLE_SPEED
    tang_speed = min(WALL_GRIND_MAX_SPEED, max(speed * 0.9, 150.0))
    puck.vx = ex * tang_speed * 0.78 + mvx * tang_speed * 0.22
    puck.vy = mvy * tang_speed * 0.08


def _apply_wall_pinch_escape(puck: Puck, inward_y: float) -> None:
    """挟み続行 → 左右どちらかへ抜け"""
    ex = _pick_escape_x(puck)
    speed = WALL_GRIND_SLIP_EXIT
    sx, sy = _normalize(ex, inward_y * 0.06)
    if sx == 0.0 and sy == 0.0:
        sx, sy = ex, 0.0
    puck.vx = sx * speed
    puck.vy = sy * speed
    puck.x += ex * 14.0
    _unstick_from_wall(puck, inward_y)
    rect = table_rect()
    r = puck.radius
    puck.x = max(rect.left + r, min(rect.right - r, puck.x))


def _head_on_min_exit(paddle: Paddle, *, min_exit_base: float = 0.0, speed_ratio: float = 0.0) -> float:
    """正面ヒット後、法線方向にラケット実速度より速く離れる最低速度"""
    paddle_speed = math.hypot(paddle.vx, paddle.vy)
    min_exit = max(
        PADDLE_HEAD_ON_MIN_EXIT,
        paddle_speed * PADDLE_HEAD_ON_MIN_EXIT_RATIO,
        paddle_speed + PADDLE_HEAD_ON_SEP_MARGIN,
    )
    if min_exit_base > 0.0 or speed_ratio > 0.0:
        min_exit = max(min_exit, min_exit_base, paddle_speed * speed_ratio)
    return min_exit


def _apply_head_on_puck_hit(
    puck: Puck,
    paddle: Paddle,
    pnx: float,
    pny: float,
    impulse: float,
    *,
    min_exit_base: float = 0.0,
    speed_ratio: float = 0.0,
) -> None:
    """接点法線で反射し、ラケットより速く離脱（頭ドリブル防止）"""
    min_exit = _head_on_min_exit(paddle, min_exit_base=min_exit_base, speed_ratio=speed_ratio)
    dot = puck.vx * pnx + puck.vy * pny
    rvx = (puck.vx - 2.0 * dot * pnx) * ELASTICITY + paddle.vx * impulse
    rvy = (puck.vy - 2.0 * dot * pny) * ELASTICITY + paddle.vy * impulse

    exit_n = rvx * pnx + rvy * pny
    if exit_n < min_exit:
        rvx += pnx * (min_exit - exit_n)
        rvy += pny * (min_exit - exit_n)

    push_n = paddle.vx * pnx + paddle.vy * pny
    rel_n = rvx * pnx + rvy * pny - push_n
    if rel_n < PADDLE_HEAD_ON_REL_SEP:
        rvx += pnx * (PADDLE_HEAD_ON_REL_SEP - rel_n)
        rvy += pny * (PADDLE_HEAD_ON_REL_SEP - rel_n)

    puck.vx, puck.vy = rvx, rvy


def _apply_boosted_puck_hit(
    puck: Puck,
    paddle: Paddle,
    pnx: float,
    pny: float,
    *,
    min_exit_base: float,
    speed_ratio: float,
    impulse: float,
    normal_floor: float = 0.65,
) -> None:
    paddle_speed = math.hypot(paddle.vx, paddle.vy)
    min_exit = max(min_exit_base, paddle_speed * speed_ratio)
    head_on = _is_head_on_hit(paddle, pnx, pny)

    if head_on:
        _apply_head_on_puck_hit(
            puck, paddle, pnx, pny, impulse,
            min_exit_base=min_exit_base,
            speed_ratio=speed_ratio,
        )
        return

    sx, sy = _boost_strike_dir(paddle, pnx, pny)
    puck.vx = sx * min_exit + paddle.vx * impulse
    puck.vy = sy * min_exit + paddle.vy * impulse
    exit_strike = puck.vx * sx + puck.vy * sy
    if exit_strike < min_exit * normal_floor:
        boost = min_exit * normal_floor - exit_strike
        puck.vx += sx * boost
        puck.vy += sy * boost


def _apply_dash_puck_hit(puck: Puck, paddle: Paddle, pnx: float, pny: float) -> None:
    """ダッシュ中: 移動方向へ強く吹き飛ばし、頭ドリブルを防ぐ"""
    _apply_boosted_puck_hit(
        puck, paddle, pnx, pny,
        min_exit_base=PADDLE_DASH_PUCK_MIN_EXIT,
        speed_ratio=PADDLE_DASH_PUCK_SPEED_RATIO,
        impulse=PADDLE_DASH_PUCK_IMPULSE,
    )


def _apply_close_puck_hit(puck: Puck, paddle: Paddle, pnx: float, pny: float) -> None:
    """近接ヒット: 歩き速度より速くはじき、載せ続けを防ぐ"""
    _apply_boosted_puck_hit(
        puck, paddle, pnx, pny,
        min_exit_base=max(PADDLE_CLOSE_PUCK_MIN_EXIT, PADDLE_SPEED * 1.12),
        speed_ratio=PADDLE_CLOSE_PUCK_SPEED_RATIO,
        impulse=PADDLE_CLOSE_PUCK_IMPULSE,
    )


def _is_close_puck_contact(dist: float, paddle_radius: float, puck_radius: float) -> bool:
    return dist < paddle_radius + puck_radius + PADDLE_CLOSE_PUCK_MARGIN


def resolve_puck_paddle(puck: Puck, paddle: Paddle, now: float) -> bool:
    pr = paddle.radius(now)
    dx = puck.x - paddle.x
    dy = puck.y - paddle.y
    dist = math.hypot(dx, dy)
    touch_dist = pr + puck.radius + PADDLE_HIT_FORGIVENESS

    if dist >= touch_dist:
        if paddle.player in puck.paddle_ignore_players and not puck_paddle_in_ignore(puck, paddle, now):
            puck.paddle_ignore_players.discard(paddle.player)
        return False

    if dist < 1e-6:
        dx, dy = 1.0, 0.0
        dist = 1.0
    pnx, pny = dx / dist, dy / dist
    is_close = _is_close_puck_contact(dist, pr, puck.radius)
    head_on = _is_head_on_hit(paddle, pnx, pny)

    if paddle.is_dashing:
        separation = PADDLE_DASH_PUCK_SEPARATION
    elif is_close:
        separation = PADDLE_CLOSE_PUCK_SEPARATION
    else:
        separation = PADDLE_PUCK_SEPARATION
    min_sep = pr + puck.radius + separation
    wall_pinch, pinch_inward = _is_wall_pinch(puck, paddle)
    overlapping = dist < min_sep
    if overlapping:
        dist, pnx, pny, min_sep = _resolve_puck_paddle_overlap(
            puck, paddle, pr, separation, pnx, pny, dist,
            wall_pinch=wall_pinch and is_close,
            pinch_inward=pinch_inward,
        )

    in_ignore = puck_paddle_in_ignore(puck, paddle, now)

    # 正面ヒット後は ignore 中に速度を再適用しない（近接 sticky ループで載せ続け防止）
    if in_ignore and head_on and not paddle.is_dashing:
        return False

    rel_vx = puck.vx - paddle.vx
    rel_vy = puck.vy - paddle.vy
    rel_out = rel_vx * pnx + rel_vy * pny
    paddle_push = paddle.vx * pnx + paddle.vy * pny
    penetrating = overlapping

    if paddle.is_dashing:
        want_hit = penetrating or rel_out < paddle_push + 120.0
    elif is_close:
        want_hit = penetrating or rel_out < paddle_push + 70.0
    else:
        want_hit = (
            rel_out < 90.0
            or paddle_push > PADDLE_CHASE_HIT_SPEED
            or penetrating
        )

    sticky_hit = paddle.is_dashing or (is_close and penetrating and not head_on)
    if in_ignore and not sticky_hit and rel_out > 30.0 and not penetrating:
        return False
    if not want_hit:
        return False

    near_wall, inward_y = _wall_cling_axis(puck)
    wall_pinch_active = is_close and wall_pinch
    if not near_wall:
        _reset_wall_grind(puck)

    if wall_pinch_active:
        if puck.grind_paddle != paddle.player or puck.grind_started_at < 0.0:
            puck.grind_started_at = now
            puck.grind_paddle = paddle.player
        grind_elapsed = now - puck.grind_started_at
        if grind_elapsed < WALL_GRIND_ALLOW_TIME:
            _apply_wall_grind_hit(puck, paddle)
            ignore_time = PADDLE_CLOSE_PUCK_IGNORE_TIME
        else:
            _apply_wall_pinch_escape(puck, inward_y)
            _reset_wall_grind(puck)
            ignore_time = WALL_GRIND_SLIP_IGNORE
    elif paddle.is_dashing:
        _apply_dash_puck_hit(puck, paddle, pnx, pny)
        ignore_time = PADDLE_DASH_PUCK_IGNORE_TIME
    elif is_close:
        _apply_close_puck_hit(puck, paddle, pnx, pny)
        ignore_time = PADDLE_HEAD_ON_IGNORE_TIME if head_on else PADDLE_CLOSE_PUCK_IGNORE_TIME
    elif head_on:
        _apply_head_on_puck_hit(puck, paddle, pnx, pny, PADDLE_PUCK_IMPULSE)
        ignore_time = PADDLE_HEAD_ON_IGNORE_TIME
        _reset_wall_grind(puck)
    else:
        dot = puck.vx * pnx + puck.vy * pny
        puck.vx = (puck.vx - 2 * dot * pnx) * ELASTICITY + paddle.vx * PADDLE_PUCK_IMPULSE
        puck.vy = (puck.vy - 2 * dot * pny) * ELASTICITY + paddle.vy * PADDLE_PUCK_IMPULSE

        exit_speed = puck.vx * pnx + puck.vy * pny
        if exit_speed < PUCK_PADDLE_MIN_EXIT:
            boost = PUCK_PADDLE_MIN_EXIT - exit_speed
            puck.vx += pnx * boost
            puck.vy += pny * boost
        ignore_time = PADDLE_PUCK_IGNORE_TIME
        _reset_wall_grind(puck)

    puck.vx, puck.vy = clamp_speed(puck.vx, puck.vy)
    mark_puck_paddle_hit(puck, paddle, now, ignore_time)
    return True


def resolve_puck_puck(a: Puck, b: Puck) -> None:
    overlap = circle_overlap(a.x, a.y, a.radius, b.x, b.y, b.radius)
    if not overlap:
        return
    nx, ny, depth = overlap
    a.x -= nx * depth * 0.5
    a.y -= ny * depth * 0.5
    b.x += nx * depth * 0.5
    b.y += ny * depth * 0.5
    rel_vx = a.vx - b.vx
    rel_vy = a.vy - b.vy
    rel_dot = rel_vx * nx + rel_vy * ny
    if rel_dot > 0:
        return
    impulse = -(1 + ELASTICITY) * rel_dot / 2
    a.vx += impulse * nx
    a.vy += impulse * ny
    b.vx -= impulse * nx
    b.vy -= impulse * ny
    a.vx, a.vy = clamp_speed(a.vx, a.vy)
    b.vx, b.vy = clamp_speed(b.vx, b.vy)


def resolve_paddle_paddle(a: Paddle, b: Paddle, now: float) -> None:
    overlap = circle_overlap(a.x, a.y, a.radius(now), b.x, b.y, b.radius(now))
    if not overlap:
        return
    nx, ny, depth = overlap
    a.x -= nx * depth * 0.5
    a.y -= ny * depth * 0.5
    b.x += nx * depth * 0.5
    b.y += ny * depth * 0.5


def clamp_paddle_to_table(paddle: Paddle, now: float) -> None:
    rect = table_rect()
    r = paddle.radius(now)
    paddle.x = max(rect.left + r, min(rect.right - r, paddle.x))
    paddle.y = max(rect.top + r, min(rect.bottom - r, paddle.y))


def apply_knockback_to_puck(puck: Puck, from_x: float, from_y: float, strength: float) -> None:
    dx, dy = _normalize(puck.x - from_x, puck.y - from_y)
    if dx == 0 and dy == 0:
        dx = 1.0
    puck.vx = dx * strength
    puck.vy = dy * strength
    puck.vx, puck.vy = clamp_speed(puck.vx, puck.vy)


def apply_knockback_to_paddle(
    paddle: Paddle,
    from_x: float,
    from_y: float,
    strength: float,
    now: float,
) -> None:
    dx, dy = _normalize(paddle.x - from_x, paddle.y - from_y)
    if dx == 0 and dy == 0:
        dx = 1 if paddle.player == 0 else -1

    peak_v = strength * PADDLE_KB_IMPULSE
    paddle.kb_vx = dx * peak_v
    paddle.kb_vy = dy * peak_v
    paddle.hit_cooldown_until = max(paddle.hit_cooldown_until, now + PADDLE_HIT_COOLDOWN)


def resolve_assist_puck(guard: GuardSoldier, puck: Puck, owner: int) -> None:
    """旧API互換"""
    pass


def update_guard_soldier(guard: GuardSoldier, dt: float, now: float, pucks: list[Puck]) -> None:
    rect = table_rect()
    direction = 1 if guard.owner == 0 else -1
    defend_x = (
        rect.left + rect.width * GUARD_DEFENSE_X_RATIO
        if guard.owner == 0
        else rect.right - rect.width * GUARD_DEFENSE_X_RATIO
    )

    if guard.state == "entering":
        guard.x += direction * GUARD_ENTER_SPEED * dt
        if (guard.owner == 0 and guard.x >= defend_x) or (guard.owner == 1 and guard.x <= defend_x):
            guard.x = defend_x
            guard.state = "guarding"
            if guard.ray_next_fire <= 0:
                guard.ray_next_fire = now


update_stag_beetle = update_guard_soldier


def update_assist(assist: GuardSoldier, dt: float) -> None:
    """旧API互換"""
    pass


def _closest_on_segment(
    px: float, py: float,
    x1: float, y1: float, x2: float, y2: float,
) -> tuple[float, float]:
    dx = x2 - x1
    dy = y2 - y1
    len_sq = dx * dx + dy * dy
    if len_sq < 1e-9:
        return x1, y1
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / len_sq))
    return x1 + t * dx, y1 + t * dy


def resolve_puck_line(
    puck: Puck,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    now: float,
    half_width: float,
    boost: float,
) -> bool:
    if now < puck.fence_ignore_until:
        return False

    cx, cy = _closest_on_segment(puck.x, puck.y, x1, y1, x2, y2)
    dist_x = puck.x - cx
    dist_y = puck.y - cy
    dist = math.hypot(dist_x, dist_y)
    hit_dist = puck.radius + half_width
    if dist >= hit_dist:
        return False

    lx = x2 - x1
    ly = y2 - y1
    length = math.hypot(lx, ly)
    if length < 1e-6:
        return False

    nx, ny = -ly / length, lx / length
    if dist > 1e-6:
        if dist_x * nx + dist_y * ny < 0:
            nx, ny = -nx, -ny
    elif puck.vx * nx + puck.vy * ny < 0:
        nx, ny = -nx, -ny

    overlap = hit_dist - dist
    if overlap > 0:
        puck.x += nx * overlap
        puck.y += ny * overlap

    dot = puck.vx * nx + puck.vy * ny
    if dot < 0:
        puck.vx -= (1 + ELASTICITY) * dot * nx
        puck.vy -= (1 + ELASTICITY) * dot * ny
        puck.vx += nx * boost
        puck.vy += ny * boost

    puck.vx, puck.vy = clamp_speed(puck.vx, puck.vy)
    puck.fence_ignore_until = now + 0.08
    return True


def _apply_rally_escalation(puck: Puck) -> None:
    puck.wall_bounces += 1
    speed = math.hypot(puck.vx, puck.vy)
    if speed < 1e-6:
        return
    cap = PUCK_MAX_SPEED * RALLY_BOUNCE_MAX_MULT
    new_speed = min(cap, speed * (1 + RALLY_BOUNCE_BOOST))
    scale = new_speed / speed
    puck.vx *= scale
    puck.vy *= scale
    puck.vx, puck.vy = clamp_speed(puck.vx, puck.vy)


def resolve_puck_fence(puck: Puck, fence: Fence, now: float) -> bool:
    hw = fence.half_width if fence.half_width > 0 else FENCE_HALF_WIDTH
    hit = resolve_puck_line(
        puck, fence.x1, fence.y1, fence.x2, fence.y2, now, hw, FENCE_BOOST,
    )
    if hit:
        _apply_rally_escalation(puck)
    return hit


def bar_half_width(paddle: Paddle, now: float) -> float:
    return BAR_HALF_WIDTH


def resolve_puck_bar(puck: Puck, bar: Bar, paddle: Paddle, now: float) -> bool:
    if bar.grow_ratio(now) < 0.05:
        return False
    hw = bar_half_width(paddle, now)
    hit = False
    for _, x1, y1, x2, y2 in bar.active_segments(paddle, now):
        if resolve_puck_line(puck, x1, y1, x2, y2, now, hw, BAR_BOOST):
            hit = True
    return hit


def resolve_ray_bar(shot, bar: Bar, paddle: Paddle, now: float) -> bool:
    """光線弾が相手バーに当たったら区画ダメージ。命中したら True"""
    if bar.grow_ratio(now) < 0.05:
        return False
    hw = bar_half_width(paddle, now)
    for idx, x1, y1, x2, y2 in bar.active_segments(paddle, now):
        cx, cy = _closest_on_segment(shot.x, shot.y, x1, y1, x2, y2)
        dist = math.hypot(shot.x - cx, shot.y - cy)
        if dist <= shot.radius + hw:
            bar.register_ray_hit(idx)
            return True
    return False
