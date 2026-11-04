"""ゲームプレイの回帰テスト（ヘッドレス・固定 dt）

使い方: python dev/test_gameplay.py
main() を偽の時計とキー入力で実際に回し、ループ込みの挙動を確認する。
"""

from __future__ import annotations

import math
import os
import sys
import tempfile
import time
import unittest
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
# 実ユーザーの設定ファイルを触らない
os.environ["IMOMUSHI_SETTINGS_DIR"] = tempfile.mkdtemp(prefix="imomushi_test_")

import pygame

import main as game_main
from ai import CPUAI
from constants import (
    PADDLE_DASH_SPEED,
    PUCK_DASH_HIT_MAX_SPEED,
    PUCK_MAX_SPEED,
    RALLY_BOUNCE_MAX_MULT,
)
from entities import Paddle, Puck, playable_rect
from game import GameState, Match
from physics import resolve_puck_paddle, resolve_puck_wall
from result_flow import ResultPhase

FRAME_MS = 16


class _StopMain(Exception):
    """スクリプト終了で main() を抜ける"""


class MainDriver:
    """main() を 1 フレームずつ進めるハーネス"""

    def __init__(self) -> None:
        self.match: Match | None = None
        self.audio = None
        self.frame_ms = FRAME_MS
        self.held: set[int] = set()
        self.fake_time = 1000.0
        self.played: list[str] = []
        self.title_draws = 0
        self.cpu_diff_draws = 0

    def press(self, key: int) -> None:
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))

    def post(self, event_type: int) -> None:
        pygame.event.post(pygame.event.Event(event_type))

    def run(self, script) -> None:
        driver = self
        generator = script(self)

        class FakeClock:
            def tick(self, _fps: int = 0) -> int:
                driver.fake_time += driver.frame_ms / 1000.0
                return driver.frame_ms

        class CapturingMatch(Match):
            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                driver.match = self

        def fake_flip() -> None:
            try:
                next(generator)
            except StopIteration:
                raise _StopMain() from None

        def fake_pressed():
            state = defaultdict(bool)
            for key in driver.held:
                state[key] = True
            return state

        real_sound_manager = game_main.SoundManager

        def capturing_sound_manager():
            audio = real_sound_manager()
            driver.audio = audio
            real_play = audio._play

            def spy_play(sound, volume=1.0):
                for name, value in vars(audio).items():
                    if value is sound:
                        driver.played.append(name)
                        break
                else:
                    driver.played.append("_other")
                real_play(sound, volume)

            audio._play = spy_play
            return audio

        real_title = game_main.draw_title_screen
        real_diff = game_main.draw_cpu_difficulty_screen

        def spy_title(*args, **kwargs):
            driver.title_draws += 1
            real_title(*args, **kwargs)

        def spy_diff(*args, **kwargs):
            driver.cpu_diff_draws += 1
            real_diff(*args, **kwargs)

        saved = (
            pygame.time.Clock, pygame.display.flip, pygame.key.get_pressed,
            time.perf_counter, game_main.Match, game_main.SoundManager,
            game_main.draw_title_screen, game_main.draw_cpu_difficulty_screen,
        )
        pygame.time.Clock = FakeClock
        pygame.display.flip = fake_flip
        pygame.key.get_pressed = fake_pressed
        time.perf_counter = lambda: driver.fake_time
        game_main.Match = CapturingMatch
        game_main.SoundManager = capturing_sound_manager
        game_main.draw_title_screen = spy_title
        game_main.draw_cpu_difficulty_screen = spy_diff
        try:
            game_main.main()
        except _StopMain:
            pass
        finally:
            (
                pygame.time.Clock, pygame.display.flip, pygame.key.get_pressed,
                time.perf_counter, game_main.Match, game_main.SoundManager,
                game_main.draw_title_screen, game_main.draw_cpu_difficulty_screen,
            ) = saved
            pygame.event.clear()


def frames(seconds: float) -> int:
    return int(seconds * 1000 / FRAME_MS) + 1


def wait(seconds: float):
    for _ in range(frames(seconds)):
        yield


def wait_for_state(driver: MainDriver, state: GameState, limit: float = 20.0):
    for _ in range(frames(limit)):
        if driver.match.state == state:
            return
        yield
    raise AssertionError(f"{state} に到達しない（現在 {driver.match.state}）")


def start_two_player(driver: MainDriver):
    """タイトル → 2芋虫対戦 → PLAYING まで進める"""
    yield
    driver.press(pygame.K_DOWN)
    yield
    driver.press(pygame.K_SPACE)
    yield from wait_for_state(driver, GameState.PLAYING)


def force_result(driver: MainDriver):
    """スコアを勝利にして RESULT の HOLD まで進める"""
    match = driver.match
    match.scores = [3, 0]
    yield
    yield
    assert match.state == GameState.RESULT
    for _ in range(frames(4.0)):
        if match.result_phase == ResultPhase.HOLD:
            return
        yield
    raise AssertionError("リザルトが HOLD に到達しない")


def speed_of(puck: Puck) -> float:
    return math.hypot(puck.vx, puck.vy)


class MainLoopTests(unittest.TestCase):
    def test_pause_keeps_fences(self) -> None:
        """ポーズ中は体節の寿命が進まない"""
        seen: dict[str, object] = {}

        def script(d: MainDriver):
            yield from start_two_player(d)
            rect = playable_rect()
            puck = d.match.pucks[0]
            puck.x, puck.y, puck.vx, puck.vy = rect.centerx, rect.top + 40, 0.0, 0.0
            d.held = {pygame.K_d}
            for _ in range(frames(1.0)):
                if d.match.fences:
                    break
                yield
            d.held = set()
            self.assertTrue(d.match.fences, "体節が生成されない")
            fence = d.match.fences[0]
            d.press(pygame.K_p)
            yield
            self.assertEqual(d.match.state, GameState.PAUSE)
            yield from wait(8.0)
            d.press(pygame.K_p)
            yield
            yield
            seen["alive"] = fence in d.match.fences

        MainDriver().run(script)
        self.assertTrue(seen.get("alive"), "ポーズ明けに体節が消えている")

    def test_sound_after_rematch(self) -> None:
        """長い試合のあとに再戦しても壁バウンド音が鳴る"""
        seen: dict[str, int] = {}

        def script(d: MainDriver):
            yield from start_two_player(d)
            # 長い試合を経た状態（audio のクールダウン時刻が大きい）にする
            d.fake_time += 60.0
            rect = playable_rect()
            puck = d.match.pucks[0]
            puck.x, puck.y, puck.vx, puck.vy = rect.centerx, rect.top + 30, 0.0, -300.0
            for _ in range(frames(60.0)):
                d.frame_ms = 50
                d.match.scores = [0, 0]
                yield
            d.frame_ms = FRAME_MS
            yield from force_result(d)
            d.press(pygame.K_SPACE)
            yield from wait_for_state(d, GameState.PLAYING)
            d.played.clear()
            puck = d.match.pucks[0]
            puck.x, puck.y, puck.vx, puck.vy = rect.centerx, rect.top + 30, 0.0, -300.0
            yield from wait(0.3)
            seen["bounce"] = d.played.count("_bounce_base")

        MainDriver().run(script)
        self.assertGreater(seen.get("bounce", 0), 0, "再戦後に壁バウンド音が鳴らない")

    def test_rematch_keeps_difficulty_and_hides_menus(self) -> None:
        """CPU 戦の再戦は難易度を維持し、メニューを経由しない"""
        seen: dict[str, object] = {}

        def script(d: MainDriver):
            yield
            d.press(pygame.K_SPACE)
            yield from wait(1.2)
            d.press(pygame.K_5)
            yield
            d.press(pygame.K_SPACE)
            yield from wait_for_state(d, GameState.PLAYING)
            yield from force_result(d)
            d.title_draws = 0
            d.cpu_diff_draws = 0
            d.press(pygame.K_SPACE)
            yield
            yield
            seen["next_state"] = d.match.state
            yield from wait_for_state(d, GameState.COUNTDOWN)
            seen["title"] = d.title_draws
            seen["diff"] = d.cpu_diff_draws
            seen["index"] = d.match.cpu_diff_index
            seen["scores"] = list(d.match.scores)

        MainDriver().run(script)
        self.assertEqual(seen.get("next_state"), GameState.PREP, "難易度選択に戻っている")
        self.assertEqual(seen.get("title"), 0, "再戦中にタイトルが描画された")
        self.assertEqual(seen.get("diff"), 0, "再戦中に難易度画面が描画された")
        self.assertEqual(seen.get("index"), 2)
        self.assertEqual(seen.get("scores"), [0, 0])

    def test_dt_spike_is_clamped(self) -> None:
        """clock.tick が跳ねても 1 フレームの移動量は小さい"""
        seen: dict[str, float] = {}

        def script(d: MainDriver):
            yield from start_two_player(d)
            rect = playable_rect()
            puck = d.match.pucks[0]
            puck.x, puck.y, puck.vx, puck.vy = rect.centerx, rect.centery, 400.0, 0.0
            before = puck.x
            d.frame_ms = 2000
            yield
            d.frame_ms = FRAME_MS
            seen["moved"] = abs(puck.x - before)

        MainDriver().run(script)
        self.assertLess(seen["moved"], 60.0, "dt スパイクで葉っぱが飛んだ")

    def test_focus_loss_pauses(self) -> None:
        seen: dict[str, object] = {}

        def script(d: MainDriver):
            yield from start_two_player(d)
            d.post(pygame.WINDOWFOCUSLOST)
            yield
            yield
            seen["state"] = d.match.state

        MainDriver().run(script)
        self.assertEqual(seen.get("state"), GameState.PAUSE)

    def test_help_screen_opens_and_closes(self) -> None:
        seen: dict[str, object] = {}

        def script(d: MainDriver):
            yield
            d.press(pygame.K_h)
            yield
            yield
            seen["opened"] = d.match.state
            yield from wait(0.5)
            d.press(pygame.K_ESCAPE)
            yield
            yield
            seen["closed"] = d.match.state

        MainDriver().run(script)
        self.assertEqual(getattr(seen.get("opened"), "name", None), "HELP")
        self.assertEqual(seen.get("closed"), GameState.TITLE)

    def test_countdown_sounds_on_every_number(self) -> None:
        seen: dict[str, object] = {}

        def script(d: MainDriver):
            yield
            d.press(pygame.K_DOWN)
            yield
            d.played.clear()
            d.press(pygame.K_SPACE)
            yield from wait_for_state(d, GameState.PLAYING)
            seen["countdown"] = d.played.count("_countdown")
            seen["start"] = d.played.count("_start")

        MainDriver().run(script)
        self.assertEqual(seen.get("countdown"), 3, "3・2・1 の全てで音が鳴らない")
        self.assertEqual(seen.get("start"), 1)


class CpuDashTests(unittest.TestCase):
    def test_dash_lasts_multiple_frames(self) -> None:
        """CPU のダッシュは 1 フレームで切れない"""
        import random

        random.seed(3)
        ai = CPUAI("hard")
        ai.reset()
        rect = playable_rect()
        paddle = Paddle(player=1, x=rect.right - 40, y=rect.centery)
        opponent = Paddle(player=0, x=rect.left + 40, y=rect.centery)
        puck = Puck(x=rect.centerx + 40, y=rect.top + 60, vx=0.0, vy=0.0)
        now = 0.0
        runs: list[int] = []
        current = 0
        for _ in range(1200):
            now += 1.0 / 60.0
            _dx, _dy, dash = ai.decide(paddle, opponent, [puck], [], now, False)
            if dash:
                current += 1
            elif current:
                runs.append(current)
                current = 0
        self.assertTrue(runs, "ダッシュが一度も発生しない")
        self.assertGreaterEqual(max(runs), 6, f"ダッシュの持続フレーム: {runs[:10]}")


class SpeedLimitTests(unittest.TestCase):
    def _dash_hit(self) -> Puck:
        rect = playable_rect()
        puck = Puck(
            x=rect.centerx + 30, y=rect.centery,
            prev_x=rect.centerx + 30, prev_y=rect.centery, vx=0.0, vy=0.0,
        )
        paddle = Paddle(
            player=0, x=rect.centerx, y=rect.centery,
            prev_x=rect.centerx - 8, prev_y=rect.centery,
            vx=PADDLE_DASH_SPEED, vy=0.0, is_dashing=True,
        )
        self.assertTrue(resolve_puck_paddle(puck, paddle, 1.0))
        return puck

    def test_dash_shot_survives_wall_step(self) -> None:
        """ダッシュショットが次の壁判定で PUCK_MAX_SPEED に戻らない"""
        puck = self._dash_hit()
        hit_speed = speed_of(puck)
        self.assertGreater(hit_speed, PUCK_MAX_SPEED)
        self.assertLessEqual(hit_speed, PUCK_DASH_HIT_MAX_SPEED)
        resolve_puck_wall(puck)
        self.assertAlmostEqual(speed_of(puck), hit_speed, places=3)

    def test_dash_shot_outruns_dash_paddle(self) -> None:
        puck = self._dash_hit()
        resolve_puck_wall(puck)
        self.assertGreater(speed_of(puck), PADDLE_DASH_SPEED)

    def test_rally_accelerates_up_to_cap(self) -> None:
        rect = playable_rect()
        puck = Puck(x=rect.centerx, y=rect.top, vx=0.0, vy=-PUCK_MAX_SPEED)
        speeds = []
        for _ in range(40):
            puck.y = rect.top
            puck.vy = -abs(puck.vy)
            resolve_puck_wall(puck)
            speeds.append(speed_of(puck))
        self.assertGreater(speeds[0], PUCK_MAX_SPEED, "ラリー加速が効いていない")
        self.assertAlmostEqual(max(speeds), PUCK_MAX_SPEED * RALLY_BOUNCE_MAX_MULT, places=3)
        self.assertLessEqual(RALLY_BOUNCE_MAX_MULT, 1.4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
