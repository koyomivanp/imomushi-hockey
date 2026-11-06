"""X 宣伝用の縦動画（mp4）と OGP 画像をヘッドレスで書き出す

使い方: python dev/render_promo.py [探すシード数]
自動操作の芋虫どうしで試合をさせ、「ダッシュで打った葉っぱが体節を貫通 → そのままゴール」
の場面を探す。見つかった場面を、貫通の瞬間だけスローにして動画にする。
同じシードなら同じ試合になるので、1 回目は探すだけ、2 回目で描く。
"""

from __future__ import annotations

import math
import os
import random
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("IMOMUSHI_SETTINGS_DIR", os.path.join(ROOT, "dev", "out", "mobile_settings"))

import pygame

from constants import MOBILE_H, MOBILE_W, PB_INK, PB_SUN
from game import GameState
from mobile_art import text_fit
from mobile_main import MobileGame, draw_frame
from sprites import init_sprites

OUT_DIR = os.path.join(ROOT, "dev", "out", "promo")
FRAMES_DIR = os.path.join(OUT_DIR, "frames")
DT = 1 / 60
VIDEO_FPS = 30
SEARCH_LIMIT = 90.0  # 1 試合で探す長さ（秒）
LEAD_IN = 2.6  # 貫通の何秒前から映すか
SLOW_BEFORE, SLOW_AFTER = 0.2, 0.45  # スローにする範囲
GOAL_WITHIN = 3.0  # 貫通からこの秒数以内のゴールを探す
TAIL = 1.6  # ゴール後に映す長さ
OGP_FRAME_AFTER = 4  # 貫通から何フレーム後を OGP 画像に使うか
QUIET_BEFORE =4.0  # 映し始めより前に、ゴールなしでこれだけ経っている場面を選ぶ
BREACH_Y_RANGE =(260, 640)  # 貫通が画面のこの高さで起きた場面だけ使う（端だと演出が切れる）
CAPTIONS = (  # （貫通からの秒数の範囲, 字幕）
    ((-99.0, -0.6), "這った跡が、壁になる"),
    ((-0.6, 99.0), "ダッシュで打つと…突き破る！"),
)
TITLE_CARD = 2.2
BGM = os.path.join(ROOT, "assets", "sounds", "bgm_battle.mp3")


class PromoBot:
    """下の芋虫（P1）を動かす。葉っぱの後ろへ回り、近づいたらダッシュで打ち込む"""

    def __init__(self) -> None:
        self.next_update = 0.0
        self.target = (0.0, 0.0)
        self.dash_until = 0.0

    def move(self, match, now: float) -> tuple[float, float, bool]:
        if not match.pucks or match.pucks_frozen:
            return 0.0, 0.0, False
        paddle, puck = match.paddles[0], match.pucks[0]
        if now >= self.next_update:
            self.next_update = now + 0.16
            if puck.x < paddle.x + 6.0:
                side = 1.0 if paddle.y >= puck.y else -1.0
                self.target = (puck.x - 60.0, puck.y + side * 60.0)
            else:
                self.target = (puck.x - 18.0, puck.y + random.uniform(-10.0, 10.0))
            dist = math.hypot(puck.x - paddle.x, puck.y - paddle.y)
            if puck.x > paddle.x and dist < 120.0 and random.random() < 0.6:
                self.dash_until = now + 0.3
        dx, dy = self.target[0] - paddle.x, self.target[1] - paddle.y
        length = math.hypot(dx, dy)
        if length < 8.0:
            return 0.0, 0.0, False
        return dx / length, dy / length, now < self.dash_until


def new_game(seed: int) -> MobileGame:
    random.seed(seed)
    game = MobileGame(None)
    game.fx.rng.seed(seed)
    game.perform("cpu:1")
    game.controls.visible = False  # 動画では操作パッドを出さない（キーボードで遊んでいるときと同じ見た目）
    bot = PromoBot()
    game.external_moves = lambda: {0: bot.move(game.match, game.game_time)}
    return game


def find_scene(seed: int) -> tuple[int, int] | None:
    """（貫通したフレーム, ゴールしたフレーム）。貫通したのは P1 で、そのまま P1 が決めたもの"""
    game = new_game(seed)
    breach_frame = None
    last_goal = 0  # 直前のゴール（映し始めに「ゴール！」や縮んだ芋虫が入らないように）
    for frame in range(int(SEARCH_LIMIT / DT)):
        impacts = len(game.fx.impacts)
        scores = tuple(game.match.scores)
        game.step(DT)
        if game.match.state == GameState.RESULT:
            return None
        if len(game.fx.impacts) > impacts and game.match.pucks and game.match.pucks[0].breach_owner == 1:
            impact = game.fx.impacts[-1]
            if BREACH_Y_RANGE[0] <= impact.y <= BREACH_Y_RANGE[1] and 120 <= impact.x <= MOBILE_W - 120:
                breach_frame = frame
        if tuple(game.match.scores) != scores:
            if game.match.scores[0] != scores[0] and breach_frame is not None \
                    and (frame - breach_frame) * DT <= GOAL_WITHIN \
                    and (breach_frame - last_goal) * DT > LEAD_IN + QUIET_BEFORE:
                return breach_frame, frame
            breach_frame = None
            last_goal = frame
    return None


def _draw_caption(screen: pygame.Surface, caption: str) -> None:
    glyph = text_fit(caption, 44, PB_SUN, max_width=MOBILE_W - 40, outline=PB_INK, outline_px=7)
    screen.blit(glyph, glyph.get_rect(center=(MOBILE_W // 2, MOBILE_H // 2 + 150)))


def render(seed: int, breach: int, goal: int) -> list[str]:
    """フレームを PNG で書き出し、動画の並び順のパスを返す"""
    screen = pygame.display.get_surface()
    game = new_game(seed)
    start = breach - int(LEAD_IN / DT)
    end = goal + int(TAIL / DT)
    slow = range(breach - int(SLOW_BEFORE / DT), breach + int(SLOW_AFTER / DT))
    sequence: list[str] = []
    step_per_video_frame = round(1 / DT / VIDEO_FPS)
    for frame in range(end + 1):
        game.step(DT)
        if frame < start:
            continue
        in_slow = frame in slow
        if not in_slow and frame % step_per_video_frame:
            continue
        draw_frame(screen, game, game.game_time)
        if frame == breach + OGP_FRAME_AFTER:
            # OGP 用は字幕と画面の白い閃光を抜いて描き直す（静止画だと白っぽく見えるだけなので）
            game.fx.flash_alpha = lambda: 0
            draw_frame(screen, game, game.game_time)
            pygame.image.save(screen, os.path.join(OUT_DIR, "breach_frame.png"))
            del game.fx.flash_alpha
            draw_frame(screen, game, game.game_time)
        since = (frame - breach) * DT
        for (lo, hi), caption in CAPTIONS:
            if lo <= since < hi and frame < goal:
                _draw_caption(screen, caption)
        path = os.path.join(FRAMES_DIR, f"m{frame:05d}.png")
        pygame.image.save(screen, path)
        # スロー区間は 60fps の全フレームを 2 枚ずつ並べる（30fps の動画で 1/4 の速さ）
        sequence += [path] * (2 if in_slow else 1)
    return sequence


def render_title_card() -> list[str]:
    screen = pygame.display.get_surface()
    game = MobileGame(None)
    sequence = []
    caption = text_fit("ブラウザですぐ遊べる", 40, PB_SUN, max_width=MOBILE_W - 60, outline=PB_INK, outline_px=6)
    for i in range(int(TITLE_CARD * VIDEO_FPS)):
        now = i / VIDEO_FPS
        draw_frame(screen, game, now)
        screen.blit(caption, caption.get_rect(center=(MOBILE_W // 2, MOBILE_H - 48)))
        path = os.path.join(FRAMES_DIR, f"t{i:05d}.png")
        pygame.image.save(screen, path)
        sequence.append(path)
    shutil.copy(sequence[-1], os.path.join(OUT_DIR, "title_frame.png"))
    return sequence


def encode(sequence: list[str]) -> str:
    listing = os.path.join(OUT_DIR, "frames.txt")
    with open(listing, "w", encoding="utf-8") as f:
        for path in sequence:
            f.write(f"file '{path.replace(os.sep, '/')}'\nduration {1 / VIDEO_FPS:.6f}\n")
        f.write(f"file '{sequence[-1].replace(os.sep, '/')}'\n")
    seconds = len(sequence) / VIDEO_FPS
    out = os.path.join(OUT_DIR, "imomushi-hockey-promo.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing]
    if os.path.exists(BGM):
        cmd += ["-i", BGM, "-af", f"afade=t=out:st={seconds - 1.0:.2f}:d=1.0", "-shortest", "-c:a", "aac", "-b:a", "128k"]
    cmd += [
        "-vf", f"fps={VIDEO_FPS},scale=1080:1920:flags=lanczos,format=yuv420p",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-movflags", "+faststart", "-t", f"{seconds:.2f}", out,
    ]
    subprocess.run(cmd, check=True)
    return out


def make_ogp(breach_png: str, title_png: str) -> str:
    """1200x630。左に縦画面 2 枚、右にタイトルと一言"""
    ogp = pygame.Surface((1200, 630))
    ogp.fill((46, 112, 58))
    for i in range(0, 1200, 40):
        pygame.draw.line(ogp, (52, 122, 64), (i, 0), (i - 300, 630), 14)
    shots = [pygame.image.load(title_png), pygame.image.load(breach_png)]
    h = 590
    w = round(MOBILE_W * h / MOBILE_H)
    for i, shot in enumerate(shots):
        x = 30 + i * (w + 24)
        scaled = pygame.transform.smoothscale(shot, (w, h))
        frame = pygame.Rect(x, 20, w, h)
        pygame.draw.rect(ogp, PB_INK, frame.inflate(10, 10), border_radius=18)
        ogp.blit(scaled, frame)
    right = 30 + 2 * (w + 24) + 10
    cx = (right + 1200) // 2
    lines = [
        ("芋虫ホッケー", 64, PB_SUN),
        ("這った跡が壁になる", 34, (255, 253, 244)),
        ("エアホッケー", 34, (255, 253, 244)),
        ("ダッシュで打てば", 30, (255, 253, 244)),
        ("相手の体を突き破る！", 30, PB_SUN),
        ("スマホ・PCの", 28, (255, 253, 244)),
        ("ブラウザで無料", 28, (255, 253, 244)),
    ]
    y = 120
    for i, (label, size, color) in enumerate(lines):
        glyph = text_fit(label, size, color, max_width=1200 - right - 30, outline=PB_INK, outline_px=5)
        ogp.blit(glyph, glyph.get_rect(center=(cx, y)))
        y += 64 if i == 0 else (size + 22)
        if i in (0, 2, 4):
            y += 26
    out = os.path.join(OUT_DIR, "og.png")
    pygame.image.save(ogp, out)
    return out


def main() -> int:
    seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    pygame.init()
    pygame.display.set_mode((MOBILE_W, MOBILE_H))
    init_sprites()
    shutil.rmtree(FRAMES_DIR, ignore_errors=True)
    os.makedirs(FRAMES_DIR, exist_ok=True)
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    for seed in range(first, first + seeds):
        scene = find_scene(seed)
        if scene is not None:
            break
    else:
        print("場面が見つからなかった")
        return 1
    breach, goal = scene
    print(f"seed={seed} breach={breach * DT:.2f}s goal={goal * DT:.2f}s")
    sequence = render(seed, breach, goal) + render_title_card()
    print("video:", encode(sequence), f"{len(sequence) / VIDEO_FPS:.1f}s")
    print("ogp:", make_ogp(os.path.join(OUT_DIR, "breach_frame.png"), os.path.join(OUT_DIR, "title_frame.png")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
