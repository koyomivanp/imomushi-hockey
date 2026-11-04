"""スマホ版の回帰テスト（ヘッドレス・固定 dt）

使い方: python dev/test_mobile.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["IMOMUSHI_SETTINGS_DIR"] = tempfile.mkdtemp(prefix="imomushi_test_")

import pygame

from constants import MOBILE_ARENA_Y, MOBILE_H, MOBILE_W, PADDLE_DASH_SPEED, PADDLE_SPEED, SCREEN_W
from entities import goal_score_bounds
from game import GameState
from mobile_main import MobileGame
from mobile_view import logic_to_screen, pause_button_rect, screen_dir_to_logic, title_buttons
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

    def test_arena_fits_portrait_canvas(self) -> None:
        self.assertEqual(logic_to_screen(SCREEN_W, 60), (0.0, MOBILE_ARENA_Y))
        self.assertEqual(logic_to_screen(0, 600), (MOBILE_W, MOBILE_ARENA_Y + SCREEN_W))

    def test_direction_matches_position_mapping(self) -> None:
        for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            lx, ly = screen_dir_to_logic(sx, sy)
            ax, ay = logic_to_screen(300, 300)
            bx, by = logic_to_screen(300 + lx, 300 + ly)
            self.assertAlmostEqual(bx - ax, sx)
            self.assertAlmostEqual(by - ay, sy)

    def test_all_title_buttons_are_on_screen(self) -> None:
        canvas = pygame.Rect(0, 0, MOBILE_W, MOBILE_H)
        for button in title_buttons(False):
            self.assertTrue(canvas.contains(button.rect), button.label)


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
        rect = next(b.rect for b in title_buttons(False) if b.action == "cpu:2")
        game.on_press(1, *rect.center)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
