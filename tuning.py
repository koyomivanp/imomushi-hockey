"""実行時の寸法（スマホ版だけ芋虫と葉っぱを太くする）

PC 版は既定値のまま（倍率 1.0）。`use_mobile_scale()` を呼んだプロセスだけ
当たり判定と描画の寸法が一緒に太くなる。描画だけ太らせると当たり判定とずれるので、
描画側も必ずここの値を使う。
"""

from __future__ import annotations

from constants import (
    CATERPILLAR_BODY_RADIUS,
    MAX_FRAME_DT,
    PADDLE_DASH_SPEED,
    MOBILE_BODY_RADIUS_SCALE,
    MOBILE_PUCK_RADIUS_SCALE,
    MOBILE_TRAIL_WALL_MAX_PER_PLAYER,
    PUCK_RADIUS,
    TRAIL_WALL_MAX_PER_PLAYER,
    TRAIL_MAX_GAP_RATIO,
    TRAIL_SEGMENT_INTERVAL_RATIO,
)

_body_scale = 1.0
_puck_scale = 1.0
_trail_wall_max = TRAIL_WALL_MAX_PER_PLAYER
_mobile = False


def use_mobile_scale() -> None:
    """スマホ版の寸法に切り替える（エントリ側で一度だけ呼ぶ）"""
    global _body_scale, _puck_scale, _trail_wall_max, _mobile
    _mobile = True
    _body_scale = MOBILE_BODY_RADIUS_SCALE
    _puck_scale = MOBILE_PUCK_RADIUS_SCALE
    _trail_wall_max = MOBILE_TRAIL_WALL_MAX_PER_PLAYER


def use_desktop_scale() -> None:
    global _body_scale, _puck_scale, _trail_wall_max, _mobile
    _mobile = False
    _body_scale = 1.0
    _puck_scale = 1.0
    _trail_wall_max = TRAIL_WALL_MAX_PER_PLAYER


def body_radius() -> float:
    """芋虫の半径（頭も体節も同じ太さ）"""
    return CATERPILLAR_BODY_RADIUS * _body_scale


def puck_radius() -> float:
    return PUCK_RADIUS * _puck_scale


def fence_half_width() -> float:
    return body_radius()


def trail_segment_interval() -> float:
    return body_radius() * TRAIL_SEGMENT_INTERVAL_RATIO


def trail_max_gap() -> float:
    """これ以上離れたら跡をつなげない上限

    スマホのブラウザはフレームが飛ぶ。1フレームの移動量が
    「間隔〜上限」の窓をまたぐと跡が1つも出なくなるので、
    ダッシュの最大 dt 分の移動を足した幅を確保する。
    """
    gap = body_radius() * TRAIL_MAX_GAP_RATIO
    if _mobile:
        gap = max(gap, trail_segment_interval() + PADDLE_DASH_SPEED * MAX_FRAME_DT * 1.4)
    return gap


def one_piece_body() -> bool:
    """スマホ版は止まってもダッシュしても、頭から尻尾まで1本につなげる"""
    return _mobile


def trail_wall_max() -> int:
    """1人あたりの体節の上限（太い分スマホでは少し短くする）"""
    return _trail_wall_max
