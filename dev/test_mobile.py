"""スマホ版の回帰テスト（ヘッドレス・固定 dt）

使い方: python dev/test_mobile.py
"""

from __future__ import annotations

import os
import sys
import math
import tempfile
import collections
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["IMOMUSHI_SETTINGS_DIR"] = tempfile.mkdtemp(prefix="imomushi_test_")

import pygame

import tuning
from constants import (
    MOBILE_H,
    MOBILE_W,
    PADDLE_DASH_SPEED,
    PADDLE_SPEED,
    PB_INK,
    TOUCH_DASH_RADIUS,
    TOUCH_PAD_RADIUS,
    PB_P1,
    PB_P2,
    PB_SUN,
)
from entities import Fence, goal_score_bounds, playable_rect
from game import GameState
from mobile_art import court_screen_rect, draw_title_ladybug, draw_title_worm, logic_to_screen, scaled, text
from mobile_main import MobileGame, draw_frame, run_frame
from mobile_view import (
    CPU_LABEL,
    TITLE_DIFF_LABEL_Y,
    _chain_points,
    pause_button_rect,
    score_badge_centers,
    screen_dir_to_logic,
    title_buttons,
)
from result_flow import ResultPhase
from touch_input import PlayerTouch, TouchControls, dash_button_center, keyboard_output, pad_home

DT = 1 / 60
BOTTOM_Y = 800.0
TOP_Y = 160.0


class PlayerTouchTest(unittest.TestCase):
    def test_slide_crawls_without_dash(self) -> None:
        stick = PlayerTouch(0)
        stick.press_pad(1, 100, 500)
        stick.move(1, 100, 460)
        dx, dy, dash = stick.output(0.5)
        self.assertFalse(dash)
        self.assertAlmostEqual(dx, 0.0)
        self.assertAlmostEqual(dy, -1.0)

    def test_fast_swipe_does_not_dash(self) -> None:
        """誤爆しないよう、ダッシュはボタンだけで出る"""
        stick = PlayerTouch(0)
        stick.press_pad(1, 100, 500)
        stick.move(1, 180, 500)
        stick.release(1)
        self.assertEqual(stick.output(0.05), (0.0, 0.0, False))

    def test_tiny_movement_stays_still(self) -> None:
        stick = PlayerTouch(0)
        stick.press_pad(1, 100, 500)
        stick.move(1, 104, 500)
        self.assertEqual(stick.output(0.1), (0.0, 0.0, False))

    def test_press_on_pad_uses_pad_center(self) -> None:
        stick = PlayerTouch(0)
        hx, hy = pad_home(0)
        stick.press_pad(1, hx + 30, hy)
        self.assertEqual((stick.anchor_x, stick.anchor_y), (hx, hy))
        self.assertAlmostEqual(stick.output(0.0)[0], 1.0)

    def test_dash_button_holds_and_tap_gives_short_burst(self) -> None:
        stick = PlayerTouch(0)
        stick.press_pad(1, 100, 500)
        stick.move(1, 160, 500)
        stick.press_dash(2, 0.0)
        self.assertEqual(stick.output(5.0), (1.0, 0.0, True), "押している間は続く")
        stick.release(2)
        self.assertEqual(stick.output(5.0), (1.0, 0.0, False))
        stick.release(1)
        stick.press_dash(2, 6.0)
        stick.release(2)
        self.assertEqual(stick.output(6.1), (1.0, 0.0, True), "パッドなしなら最後の向きへ")
        self.assertEqual(stick.output(7.0), (0.0, 0.0, False))

    def test_reversing_takes_effect_without_returning_to_anchor(self) -> None:
        stick = PlayerTouch(0)
        stick.press_pad(1, 100, 500)
        stick.move(1, 300, 500)
        stick.move(1, 225, 500)
        self.assertLess(stick.output(0.1)[0], 0.0, "中心が追従せず切り返せない")


class TouchControlsTest(unittest.TestCase):
    def test_two_player_fingers_go_to_own_half(self) -> None:
        controls = TouchControls(MOBILE_H)
        controls.press(1, 270, BOTTOM_Y, 0.0, two_player=True)
        controls.press(2, 100, TOP_Y, 0.0, two_player=True)
        self.assertEqual(controls.sticks[0].finger, 1)
        self.assertEqual(controls.sticks[1].finger, 2)
        controls.move(2, 100, TOP_Y + 40, 0.5)
        self.assertEqual(controls.sticks[0].output(0.5), (0.0, 0.0, False))
        self.assertGreater(controls.sticks[1].output(0.5)[1], 0.0)

    def test_vs_cpu_top_half_also_controls_player(self) -> None:
        controls = TouchControls(MOBILE_H)
        controls.press(1, 100, TOP_Y, 0.0, two_player=False)
        self.assertEqual(controls.sticks[0].finger, 1)
        self.assertIsNone(controls.sticks[1].finger)

    def test_second_finger_does_not_steal_stick(self) -> None:
        controls = TouchControls(MOBILE_H)
        controls.press(1, 270, BOTTOM_Y, 0.0, two_player=False)
        controls.press(2, 300, BOTTOM_Y, 0.0, two_player=False)
        self.assertEqual(controls.sticks[0].finger, 1)


class PortraitMappingTest(unittest.TestCase):
    def test_goals_are_top_and_bottom_and_p1_is_bottom(self) -> None:
        left, right = goal_score_bounds()
        self.assertGreater(logic_to_screen(left, 300)[1], logic_to_screen(right, 300)[1])

    def test_court_fits_portrait_canvas_without_black_bands(self) -> None:
        canvas = pygame.Rect(0, 0, MOBILE_W, MOBILE_H)
        rect = playable_rect()
        for x, y in ((rect.left, rect.top), (rect.right, rect.bottom)):
            sx, sy = logic_to_screen(x, y)
            self.assertTrue(canvas.collidepoint(sx, sy), (sx, sy))
        court = court_screen_rect()
        self.assertGreater(court.width / MOBILE_W, 0.9, "コートが画面幅を使えていない")
        self.assertGreater(court.height / MOBILE_H, 0.8)

    def test_direction_matches_position_mapping(self) -> None:
        for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            lx, ly = screen_dir_to_logic(sx, sy)
            ax, ay = logic_to_screen(300, 300)
            bx, by = logic_to_screen(300 + lx, 300 + ly)
            dx, dy = bx - ax, by - ay
            norm = math.hypot(dx, dy)
            self.assertAlmostEqual(dx / norm, sx)
            self.assertAlmostEqual(dy / norm, sy)

    def test_mobile_bodies_are_big_enough_to_see(self) -> None:
        self.assertGreater(scaled(tuning.body_radius()) * 2, 46.0)
        self.assertGreater(scaled(tuning.puck_radius()) * 2, 54.0)
        self.assertAlmostEqual(tuning.fence_half_width(), tuning.body_radius())

    def test_all_title_buttons_are_on_screen(self) -> None:
        canvas = pygame.Rect(0, 0, MOBILE_W, MOBILE_H)
        for button in title_buttons(False):
            self.assertTrue(canvas.contains(button.rect), button.label)

    def test_difficulty_label_is_not_hidden_on_title(self) -> None:
        label = text(f"つよさ（vs {CPU_LABEL}）", 24, PB_INK).get_rect(center=(MOBILE_W // 2, TITLE_DIFF_LABEL_Y))
        for button in title_buttons(False):
            self.assertFalse(label.colliderect(button.rect), button.label)
        for i in range(120):  # 芋虫とてんとう虫は波打つので、いろいろな時刻で確かめる
            layer = pygame.Surface((MOBILE_W, MOBILE_H), pygame.SRCALPHA)
            draw_title_worm(layer, i * 0.1)
            draw_title_ladybug(layer, i * 0.1)
            self.assertEqual(layer.subsurface(label).get_bounding_rect().size, (0, 0), f"t={i * 0.1:.1f}")


class MobileGameTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        pygame.display.set_mode((MOBILE_W, MOBILE_H))

    def _game_in_play(self, *, vs_cpu: bool = True) -> MobileGame:
        game = MobileGame(None)
        game.perform("cpu:0" if vs_cpu else "two_player")
        for _ in range(60 * 5):
            game.step(DT)
            if game.match.state == GameState.PLAYING:
                return game
        self.fail("カウントダウンが終わらない")

    def _run(self, game: MobileGame, seconds: float) -> None:
        for _ in range(int(seconds * 60)):
            game.step(DT)

    def test_title_button_starts_match_with_chosen_difficulty(self) -> None:
        game = MobileGame(None)
        diff = next(b.rect for b in title_buttons(False) if b.action == "cpu_diff:2")
        game.on_press(1, *diff.center)
        self.assertEqual(game.match.state, GameState.TITLE)
        start = next(b.rect for b in title_buttons(False, game.match.cpu_diff_index) if b.action.startswith("cpu:"))
        game.on_press(1, *start.center)
        self.assertEqual(game.match.state, GameState.COUNTDOWN)
        self.assertTrue(game.match.vs_cpu)
        self.assertEqual(game.cpu_ai.difficulty.key, "hard")

    def test_drag_up_moves_worm_toward_opponent_and_leaves_trail(self) -> None:
        game = self._game_in_play()
        paddle = game.match.paddles[0]
        start_screen_y = logic_to_screen(paddle.x, paddle.y)[1]
        game.on_press(1, 270, BOTTOM_Y)
        for i in range(1, 11):
            game.on_move(1, 270, BOTTOM_Y - i * 4)
            game.step(DT * 3)
        self.assertAlmostEqual(paddle.vx, PADDLE_SPEED)
        self.assertFalse(paddle.is_dashing)
        self.assertLess(logic_to_screen(paddle.x, paddle.y)[1], start_screen_y)
        self.assertGreater(len([f for f in game.match.fences if f.owner == 0]), 0)

    def _moves(self, game, seq) -> None:
        for move, seconds in seq:
            game.external_moves = lambda m=move: {0: m, 1: (0.0, 0.0, False)}
            self._run(game, seconds)

    def test_body_stays_one_piece_through_stop_and_dash(self) -> None:
        """止まる・ダッシュする・また這う、を挟んでも胴体は頭まで1本"""
        game = self._game_in_play()
        game.match.pucks = []
        self._moves(game, [
            ((1.0, 0.0, False), 0.4), ((0.0, 0.0, False), 0.2),
            ((0.0, 1.0, False), 0.4), ((-1.0, 0.0, True), 0.15), ((0.0, -1.0, False), 0.4),
        ])
        fences = [f for f in game.match.fences if f.owner == 0]
        self.assertGreaterEqual(len(fences), 3)
        self.assertEqual(len(_chain_points(fences, game.game_time)), 1, "胴体が切れている")

    def test_severed_tail_retracts_quickly(self) -> None:
        """葉っぱに切られたら、頭につながらない尻尾側はすぐ消えて2本に残らない"""
        game = self._game_in_play()
        game.match.pucks = []
        self._moves(game, [((1.0, 0.0, False), 0.9)])
        body = sorted((f for f in game.match.fences if f.owner == 0), key=lambda f: f.created_at)
        self.assertGreaterEqual(len(body), 4)
        game.match.fences.remove(body[1])
        self._moves(game, [((0.0, 0.0, False), 0.3)])
        left = [f for f in game.match.fences if f.owner == 0]
        self.assertFalse(any(f is body[0] for f in left), "切れた尻尾が残っている")
        self.assertTrue(all(any(f is k for f in left) for k in body[2:]), "頭側まで消えた")

    def test_keyboard_moves_on_screen_directions(self) -> None:
        """矢印キーでも WASD でも、CPU 戦は自分が画面の向きどおりに動く"""
        for key in (pygame.K_UP, pygame.K_w):
            pressed = collections.defaultdict(bool, {key: True})
            self.assertEqual(keyboard_output(pressed, 0, two_player=False), (0.0, -1.0, False))
            self.assertEqual(keyboard_output(pressed, 1, two_player=False), (0.0, 0.0, False))
        both = collections.defaultdict(bool, {pygame.K_UP: True, pygame.K_w: True, pygame.K_LSHIFT: True})
        self.assertEqual(keyboard_output(both, 0, two_player=False), (0.0, -1.0, True))
        arrows = collections.defaultdict(bool, {pygame.K_LEFT: True})
        self.assertEqual(keyboard_output(arrows, 0, two_player=True), (0.0, 0.0, False))
        self.assertEqual(keyboard_output(arrows, 1, two_player=True), (-1.0, 0.0, False))
        game = self._game_in_play()
        before = logic_to_screen(game.match.paddles[0].x, game.match.paddles[0].y)[1]
        with mock.patch("pygame.key.get_pressed", lambda: collections.defaultdict(bool, {pygame.K_UP: True})):
            self._run(game, 0.3)
            self.assertLess(logic_to_screen(game.match.paddles[0].x, game.match.paddles[0].y)[1], before)

    def test_trail_survives_laggy_frames(self) -> None:
        """フレームが飛んでも跡が途切れない（間隔と上限の窓をまたぐ問題）"""
        from constants import MAX_FRAME_DT

        game = self._game_in_play()
        game.on_press(1, 270, BOTTOM_Y)
        for i in range(1, 13):
            game.on_move(1, 270, BOTTOM_Y - i * 8)
            game.step(MAX_FRAME_DT)
        self.assertGreater(len([f for f in game.match.fences if f.owner == 0]), 1)

    def test_dash_button_moves_along_pad_and_keeps_body_connected(self) -> None:
        game = self._game_in_play()
        paddle = game.match.paddles[0]
        game.on_press(1, *pad_home(0))
        game.on_move(1, pad_home(0)[0] - 40, pad_home(0)[1])
        game.step(DT)
        self.assertFalse(paddle.is_dashing)
        game.on_press(2, *dash_button_center(0))
        game.step(DT)
        self.assertTrue(paddle.is_dashing)
        self.assertAlmostEqual(paddle.vy, -PADDLE_DASH_SPEED)
        game.on_release(2, *dash_button_center(0))
        game.on_release(1, pad_home(0)[0] - 40, pad_home(0)[1])
        self._run(game, 0.6)
        self.assertEqual(len(_chain_points([f for f in game.match.fences if f.owner == 0], game.game_time)), 1)
        self.assertFalse(paddle.is_dashing)
        self.assertEqual(paddle.vy, 0.0)

    def test_touch_controls_do_not_overlap_score_or_pause(self) -> None:
        game = self._game_in_play()
        badges = score_badge_centers()
        for player in (0, 1):
            for center, radius in ((pad_home(player), TOUCH_PAD_RADIUS), (dash_button_center(player), TOUCH_DASH_RADIUS)):
                self.assertTrue(pygame.Rect(0, 0, MOBILE_W, MOBILE_H).collidepoint(center))
                area = pygame.Rect(center[0] - radius, center[1] - radius, radius * 2, radius * 2)
                self.assertFalse(area.colliderect(pause_button_rect()))
                for bx, by in badges:
                    self.assertFalse(area.colliderect(pygame.Rect(bx - 38, by - 38, 76, 76)))

    def test_keyboard_hides_touch_controls_until_touched(self) -> None:
        game = self._game_in_play()
        game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
        self.assertFalse(game.controls.visible)
        game.on_press(1, 270, BOTTOM_Y)
        self.assertTrue(game.controls.visible)

    def test_two_players_move_independently(self) -> None:
        game = self._game_in_play(vs_cpu=False)
        p1, p2 = game.match.paddles
        game.on_press(1, 270, BOTTOM_Y)
        game.on_press(2, 270, TOP_Y)
        game.step(DT)
        game.on_move(1, 270, BOTTOM_Y - 20)
        game.step(DT * 2)
        game.on_move(2, 270, TOP_Y + 20)
        game.step(DT * 2)
        self.assertGreater(p1.vx, 0.0)
        self.assertLess(p2.vx, 0.0)

    def test_pause_button_stops_game_clock_and_resume_clears_touch(self) -> None:
        game = self._game_in_play()
        game.on_press(1, *pause_button_rect().center)
        self.assertEqual(game.match.state, GameState.PAUSE)
        before = game.game_time
        self._run(game, 1.0)
        self.assertEqual(game.game_time, before)
        game.perform("resume")
        self.assertEqual(game.match.state, GameState.PLAYING)
        self.assertIsNone(game.controls.sticks[0].finger)

    def test_focus_lost_pauses_and_releases_finger(self) -> None:
        game = self._game_in_play()
        game.on_press(1, 270, BOTTOM_Y)
        game.on_focus_lost()
        self.assertEqual(game.match.state, GameState.PAUSE)
        self.assertIsNone(game.controls.sticks[0].finger)

    def test_rematch_keeps_mode_and_resets_score(self) -> None:
        game = self._game_in_play(vs_cpu=False)
        game.match.scores = [3, 1]
        game.match.winner = 0
        game.match.state = GameState.RESULT
        game.match.result_phase = ResultPhase.HOLD
        self.assertIn("rematch", [b.action for b in game.visible_buttons()])
        game.perform("rematch")
        self.assertEqual(game.match.state, GameState.COUNTDOWN)
        self.assertFalse(game.match.vs_cpu)
        self.assertEqual(game.match.scores, [0, 0])

    def test_full_match_finishes_with_touch_player_idle(self) -> None:
        game = self._game_in_play()
        for _ in range(60 * 300):
            game.step(DT)
            if game.match.state == GameState.RESULT:
                break
        self.assertEqual(game.match.state, GameState.RESULT)


def _count_color(surface: pygame.Surface, color: tuple[int, int, int], tol: int = 12) -> int:
    """その色のピクセル数（numpy なしで数える）"""
    return pygame.transform.threshold(None, surface, color, (tol, tol, tol, 255), None, 0)


class TrailRenderingTest(unittest.TestCase):
    """體節が画面に出ないバグの回帰テスト

    体節の寿命は game.game_time 基準。描画に壁時計（time.perf_counter）を渡すと
    寿命切れ扱いになって這った跡が消える。実際のループ本体 run_frame を、
    壁時計を大きくずらした状態で回して、跡のピクセルが残ることを確かめる。
    """

    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        cls.screen = pygame.display.set_mode((MOBILE_W, MOBILE_H))

    def _crawling_game(self) -> MobileGame:
        game = MobileGame(None)
        game.perform("cpu:0")
        for _ in range(60 * 5):
            game.step(DT)
            if game.match.state == GameState.PLAYING:
                break
        self.assertEqual(game.match.state, GameState.PLAYING)
        game.on_press(1, 270, BOTTOM_Y)
        for i in range(1, 26):
            game.on_move(1, 270, BOTTOM_Y - i * 5)
            game.step(DT * 2)
        self.assertGreaterEqual(len([f for f in game.match.fences if f.owner == 0]), 3)
        return game

    def _trail_pixels(self, game: MobileGame) -> int:
        """跡のピクセル数（頭だけの分を差し引く）"""
        draw_frame(self.screen, game, game.game_time)
        with_trail = _count_color(self.screen, PB_P1)
        fences = game.match.fences
        game.match.fences = []
        draw_frame(self.screen, game, game.game_time)
        head_only = _count_color(self.screen, PB_P1)
        game.match.fences = fences
        return with_trail - head_only

    def test_crawling_draws_trail_pixels(self) -> None:
        game = self._crawling_game()
        self.assertGreater(self._trail_pixels(game), 3000, "這った跡が描かれていない")

    def test_trail_survives_wall_clock_drift(self) -> None:
        """タブの復帰などで壁時計が大きく進んでも跡は消えない"""
        game = self._crawling_game()
        drift = time.perf_counter() + 600.0
        with mock.patch("time.perf_counter", lambda: drift):
            run_frame(self.screen, game, DT)
            trail = _count_color(self.screen, PB_P1)
            game.match.fences = []
            run_frame(self.screen, game, DT)
            head_only = _count_color(self.screen, PB_P1)
        self.assertGreater(trail - head_only, 3000, "壁時計のずれで体節が消えている")

    def test_both_players_are_drawn_in_their_colors(self) -> None:
        game = self._crawling_game()
        draw_frame(self.screen, game, game.game_time)
        self.assertGreater(_count_color(self.screen, PB_P1), 1500)
        self.assertGreater(_count_color(self.screen, PB_P2), 1500)


class WormShapeTest(unittest.TestCase):
    def test_connected_fences_become_one_chain(self) -> None:
        fences = [
            Fence(owner=0, x1=100, y1=100, x2=140, y2=100, until=99.0, created_at=1.0, half_width=20.0),
            Fence(owner=0, x1=140, y1=100, x2=180, y2=130, until=99.0, created_at=1.1, half_width=20.0),
            Fence(owner=0, x1=400, y1=400, x2=440, y2=400, until=99.0, created_at=1.2, half_width=20.0),
        ]
        chains = _chain_points(fences, now=2.0)
        self.assertEqual([len(c) for c in chains], [3, 2], "つながった体節が1本になっていない")

    def test_tail_shrinks_from_the_tail_end(self) -> None:
        fence = Fence(owner=0, x1=100, y1=100, x2=200, y2=100, until=10.0, created_at=1.0, half_width=20.0)
        fresh = _chain_points([fence], now=9.0)[0]
        dying = _chain_points([fence], now=9.9)[0]
        self.assertEqual(fresh[0], (100.0, 100.0))
        self.assertGreater(dying[0][0], fresh[0][0], "尻尾側から縮んでいない")
        self.assertEqual(dying[1], (200.0, 100.0), "頭側が縮んでいる")


class MobileEffectsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        pygame.display.set_mode((MOBILE_W, MOBILE_H))

    def test_goal_spawns_petals_and_shake(self) -> None:
        game = MobileGame(None)
        game.perform("cpu:0")
        for _ in range(60 * 5):
            game.step(DT)
            if game.match.state == GameState.PLAYING:
                break
        game.match.scores = [1, 0]
        game.match.score_pop_player = 0
        game.step(DT)
        self.assertGreater(len(game.fx.particles), 10)
        self.assertGreater(game.fx.goal_text_timer, 0.0)
        self.assertGreater(game.shake_timer, 0.0)
        self.assertNotEqual(game.shake_offset(), (0.0, 0.0))

    def test_victory_starts_butterfly(self) -> None:
        game = MobileGame(None)
        game.perform("cpu:0")
        game.match.state = GameState.RESULT
        game.match.winner = 0
        game.step(DT)
        self.assertTrue(game.butterfly.active)

    def _breach_scene(self):
        """ダッシュで打った葉っぱが相手の体節へ飛び込む直前の場面"""
        game = MobileGame(None)
        game.perform("cpu:0")
        for _ in range(60 * 5):
            game.step(DT)
            if game.match.state == GameState.PLAYING:
                break
        match = game.match
        puck = match.pucks[0]
        puck.x, puck.y, puck.vx, puck.vy = 500.0, 300.0, 500.0, 0.0
        puck.prev_x, puck.prev_y = puck.x, puck.y
        puck.dash_breach_until = game.game_time + 1.0
        puck.fence_ignore_until = 0.0
        match.paddles[0].x, match.paddles[0].y = 150.0, 500.0
        match.paddles[1].x, match.paddles[1].y = 650.0, 500.0
        game.cpu_ai.decide = lambda *a, **k: (0.0, 0.0, False)
        match.fences = [Fence(
            owner=1, x1=530.0, y1=240.0, x2=530.0, y2=360.0,
            until=game.game_time + 9.0, created_at=game.game_time, half_width=tuning.fence_half_width(),
        )]
        return game, puck

    def test_real_breach_plays_big_effect_in_the_owners_color(self) -> None:
        game, puck = self._breach_scene()
        game.step(DT)
        self.assertEqual(puck.breach_owner, 1)
        self.assertEqual(len(game.fx.impacts), 1, "閃光が出ていない")
        self.assertGreaterEqual(len(game.fx.particles), 20)
        self.assertGreater(game.hitstop_timer, 0.0)
        self.assertGreater(game.shake_timer, 0.0)
        self.assertEqual(game.match.fences, [], "貫かれた体節が消えていない")
        screen = pygame.display.get_surface()
        draw_frame(screen, game, game.game_time)
        self.assertGreater(_count_color(screen, PB_SUN), 800, "閃光が描かれていない")

    def test_breach_effect_does_not_repeat_for_neighboring_segments(self) -> None:
        game, puck = self._breach_scene()
        game.step(DT)
        puck.breach_flash_until = game.game_time + 0.5
        game._watch_match_events()
        self.assertEqual(len(game.fx.impacts), 1)

    def test_dash_has_no_extra_tail_or_dust_on_the_body(self) -> None:
        """ダッシュ中も頭と体節だけを描く"""
        import mobile_view

        game = MobileGame(None)
        game.perform("cpu:0")
        for _ in range(60 * 5):
            game.step(DT)
            if game.match.state == GameState.PLAYING:
                break
        game.match.pucks = []
        game.external_moves = lambda: {0: (0.0, -1.0, True), 1: (0.0, 0.0, False)}
        calls = []
        real = mobile_view.draw_tube
        with mock.patch.object(mobile_view, "draw_tube", lambda s, pts, p: (calls.append((p, len(pts))), real(s, pts, p))):
            for _ in range(10):
                game.step(DT)
            calls.clear()
            mobile_view.draw_worm(pygame.display.get_surface(), game.match, 0, game.game_time, (0, 0))
        self.assertLessEqual(len(calls), 2, "胴体と頭以外が描かれている")
        self.assertEqual(calls[-1][1], 1)
        self.assertFalse(hasattr(mobile_view, "dash_tail_points"))

    def test_hitstop_freezes_the_match_briefly(self) -> None:
        game = MobileGame(None)
        game.perform("cpu:0")
        for _ in range(60 * 5):
            game.step(DT)
            if game.match.state == GameState.PLAYING:
                break
        game.hitstop_timer = 0.05
        before = game.game_time
        game.step(DT)
        self.assertEqual(game.game_time, before, "強打の停止中に時計が進んでいる")
        for _ in range(5):
            game.step(DT)
        self.assertGreater(game.game_time, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
