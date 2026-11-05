"""スマホ版の回帰テスト（ヘッドレス・固定 dt）

使い方: python dev/test_mobile.py
"""

from __future__ import annotations

import os
import sys
import math
import tempfile
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
    PB_P1,
    PB_P2,
)
from entities import Fence, goal_score_bounds, playable_rect
from game import GameState
from mobile_art import court_screen_rect, draw_title_ladybug, draw_title_worm, logic_to_screen, scaled, text
from mobile_main import MobileGame, draw_frame, run_frame
from mobile_view import CPU_LABEL, TITLE_DIFF_LABEL_Y, _chain_points, pause_button_rect, screen_dir_to_logic, title_buttons
from result_flow import ResultPhase
from touch_input import FlickStick, TouchControls

DT = 1 / 60
BOTTOM_Y = 800.0
TOP_Y = 160.0


class FlickStickTest(unittest.TestCase):
    def test_slow_drag_crawls_without_dash(self) -> None:
        stick = FlickStick()
        stick.press(1, 100, 500, 0.0)
        for i in range(1, 11):
            stick.move(1, 100, 500 - i * 6, i * 0.05)
        dx, dy, dash = stick.output(0.5)
        self.assertFalse(dash)
        self.assertAlmostEqual(dx, 0.0)
        self.assertAlmostEqual(dy, -1.0)

    def test_tiny_movement_stays_still(self) -> None:
        stick = FlickStick()
        stick.press(1, 100, 500, 0.0)
        stick.move(1, 104, 500, 0.1)
        self.assertEqual(stick.output(0.1), (0.0, 0.0, False))

    def test_fast_flick_dashes_then_stops_after_release(self) -> None:
        stick = FlickStick()
        stick.press(1, 100, 500, 0.0)
        stick.move(1, 180, 500, 0.03)
        stick.release(1, 180, 500, 0.04)
        dx, dy, dash = stick.output(0.05)
        self.assertTrue(dash)
        self.assertAlmostEqual(dx, 1.0)
        self.assertEqual(stick.output(1.0), (0.0, 0.0, False))

    def test_quick_short_swipe_released_counts_as_flick(self) -> None:
        stick = FlickStick()
        stick.press(1, 100, 500, 0.0)
        stick.move(1, 120, 500, 0.08)
        stick.release(1, 140, 500, 0.16)
        self.assertTrue(stick.output(0.17)[2])

    def test_slow_release_is_not_a_flick(self) -> None:
        stick = FlickStick()
        stick.press(1, 100, 500, 0.0)
        stick.move(1, 160, 500, 0.5)
        stick.release(1, 160, 500, 0.6)
        self.assertEqual(stick.output(0.61), (0.0, 0.0, False))

    def test_reversing_takes_effect_without_returning_to_anchor(self) -> None:
        stick = FlickStick()
        stick.press(1, 100, 500, 0.0)
        for i in range(1, 21):
            stick.move(1, 100 + i * 10, 500, i * 0.1)
        stick.move(1, 270, 500, 2.2)
        stick.move(1, 245, 500, 2.4)
        self.assertLess(stick.output(2.4)[0], 1.0 + 1e-6)
        stick.move(1, 225, 500, 2.6)
        stick.move(1, 205, 500, 2.8)
        self.assertLess(stick.output(2.8)[0], 0.0, "接地点が追従せず切り返せない")


class TouchControlsTest(unittest.TestCase):
    def test_two_player_fingers_go_to_own_half(self) -> None:
        controls = TouchControls(MOBILE_H)
        controls.press(1, 100, BOTTOM_Y, 0.0, two_player=True)
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
        controls.press(1, 100, BOTTOM_Y, 0.0, two_player=False)
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
        self.assertGreater(scaled(tuning.body_radius()) * 2, 54.0)
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

    def test_trail_survives_laggy_frames(self) -> None:
        """フレームが飛んでも跡が途切れない（間隔と上限の窓をまたぐ問題）"""
        from constants import MAX_FRAME_DT

        game = self._game_in_play()
        game.on_press(1, 270, BOTTOM_Y)
        for i in range(1, 13):
            game.on_move(1, 270, BOTTOM_Y - i * 8)
            game.step(MAX_FRAME_DT)
        self.assertGreater(len([f for f in game.match.fences if f.owner == 0]), 1)

    def test_flick_dashes_without_trail(self) -> None:
        game = self._game_in_play()
        paddle = game.match.paddles[0]
        game.on_press(1, 150, BOTTOM_Y)
        game.step(DT)
        game.on_move(1, 260, BOTTOM_Y)
        game.step(DT)
        self.assertTrue(paddle.is_dashing)
        self.assertAlmostEqual(paddle.vy, PADDLE_DASH_SPEED)
        self.assertEqual(len([f for f in game.match.fences if f.owner == 0]), 0)
        game.on_release(1, 260, BOTTOM_Y)
        self._run(game, 0.6)
        self.assertFalse(paddle.is_dashing)
        self.assertEqual(paddle.vy, 0.0)

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
