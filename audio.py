"""効果音 — assets/sounds/（BGMは Summer Engine / ElevenLabs 生成）"""

from __future__ import annotations

import array
import math
import sys
from enum import Enum, auto
from pathlib import Path

import pygame

from constants import BGM_BATTLE_VOLUME, BGM_ENABLED, BGM_TITLE_VOLUME


def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


SOUNDS_DIR = _app_root() / "assets" / "sounds"
SAMPLE_RATE = 22050


class BGMMode(Enum):
    TITLE = auto()
    BATTLE = auto()


def _make_tone(freq: float, duration: float, volume: float = 0.35) -> pygame.mixer.Sound:
    n = int(SAMPLE_RATE * duration)
    buf = array.array("h")
    max_amp = int(32767 * volume)
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 28)
        v = int(max_amp * env * math.sin(2 * math.pi * freq * t))
        buf.append(v)
        buf.append(v)
    return pygame.mixer.Sound(buffer=buf)


def _make_swoosh(duration: float = 0.11, volume: float = 0.32) -> pygame.mixer.Sound:
    n = int(SAMPLE_RATE * duration)
    buf = array.array("h")
    max_amp = int(32767 * volume)
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 22.0) * (1.0 - t / duration)
        freq = 920.0 - 520.0 * (t / duration)
        v = int(max_amp * env * math.sin(2 * math.pi * freq * t))
        buf.append(v)
        buf.append(v)
    return pygame.mixer.Sound(buffer=buf)


def _load_or_tone(name: str, freq: float, duration: float) -> pygame.mixer.Sound:
    for ext in (".wav", ".ogg", ".mp3"):
        path = SOUNDS_DIR / f"{name}{ext}"
        if path.is_file():
            try:
                return pygame.mixer.Sound(str(path))
            except pygame.error:
                pass
    return _make_tone(freq, duration)


def _load_or_swoosh(name: str) -> pygame.mixer.Sound:
    for ext in (".wav", ".ogg", ".mp3"):
        path = SOUNDS_DIR / f"{name}{ext}"
        if path.is_file():
            try:
                return pygame.mixer.Sound(str(path))
            except pygame.error:
                pass
    return _make_swoosh()


def _find_track(names: tuple[str, ...], extensions: tuple[str, ...] = (".mp3", ".ogg", ".wav")) -> Path | None:
    for name in names:
        for ext in extensions:
            path = SOUNDS_DIR / f"{name}{ext}"
            if path.is_file():
                return path
    return None


class SoundManager:
    def __init__(self) -> None:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=512)
        pygame.mixer.set_num_channels(12)
        self.enabled = True
        self._bounce_base = _load_or_tone("wall_bounce", 520, 0.07)
        self._goal = _load_or_tone("goal", 660, 0.35)
        self._countdown = _load_or_tone("countdown", 880, 0.06)
        self._start = _load_or_tone("start", 990, 0.12)
        self._fence_breach = _load_or_swoosh("fence_breach")
        self._last_bounce_at = 0.0
        self._last_trail_at = 0.0
        self._last_breach_at = 0.0
        self._bounce_cooldown = 0.04
        self._trail_cooldown = 0.045
        self._breach_cooldown = 0.06
        self._trail_pitch = 0.0
        self._title_path = _find_track(("bgm_title", "bgm", "music"))
        self._battle_path = _find_track(("bgm_battle", "battle_bgm", "bgm_fight"))
        self._current_mode: BGMMode | None = None
        self._bgm_playing = False
        self.bgm_muted = False

    @property
    def current_mode(self) -> BGMMode | None:
        return self._current_mode

    def _volume_for(self, mode: BGMMode) -> float:
        if self.bgm_muted:
            return 0.0
        if mode == BGMMode.BATTLE:
            return BGM_BATTLE_VOLUME
        return BGM_TITLE_VOLUME

    def _play_mode(self, mode: BGMMode) -> None:
        if not self.enabled or not BGM_ENABLED:
            return
        path = self._title_path if mode == BGMMode.TITLE else self._battle_path
        if path is None:
            return
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(self._volume_for(mode))
            pygame.mixer.music.play(-1)
            self._current_mode = mode
            self._bgm_playing = True
        except pygame.error:
            self._bgm_playing = False

    def play_title_bgm(self) -> None:
        self._play_mode(BGMMode.TITLE)

    def play_battle_bgm(self) -> None:
        self._play_mode(BGMMode.BATTLE)

    def start_bgm(self) -> None:
        """互換用 — タイトルBGMを再生"""
        self.play_title_bgm()

    def set_bgm_for_state(self, state_name: str) -> None:
        if state_name == "TITLE" or state_name in ("CPU_DIFF", "FADE", "TIPS"):
            if self._current_mode != BGMMode.TITLE:
                self.play_title_bgm()
        elif state_name in ("COUNTDOWN", "PLAYING", "RESULT"):
            if self._current_mode != BGMMode.BATTLE:
                self.play_battle_bgm()

    def stop_bgm(self) -> None:
        if self._bgm_playing:
            pygame.mixer.music.stop()
            self._bgm_playing = False
            self._current_mode = None

    def pause_bgm(self) -> None:
        if self._bgm_playing:
            pygame.mixer.music.pause()

    def resume_bgm(self) -> None:
        if self._bgm_playing:
            pygame.mixer.music.unpause()

    def toggle_bgm_mute(self) -> bool:
        self.bgm_muted = not self.bgm_muted
        if self._bgm_playing and self._current_mode is not None:
            pygame.mixer.music.set_volume(self._volume_for(self._current_mode))
        return self.bgm_muted

    def _play(self, sound: pygame.mixer.Sound, volume: float = 1.0) -> None:
        if not self.enabled:
            return
        try:
            sound.set_volume(max(0.0, min(1.0, volume)))
            sound.play()
        except pygame.error:
            pass

    def play_wall_bounce(self, bounce_count: int, now: float) -> None:
        if now - self._last_bounce_at < self._bounce_cooldown:
            return
        self._last_bounce_at = now
        vol = min(1.0, 0.5 + bounce_count * 0.04)
        if bounce_count <= 1:
            self._play(self._bounce_base, vol)
            return
        freq = 440 + min(14, bounce_count) * 48
        tone = _make_tone(freq, 0.05 + min(0.05, bounce_count * 0.003), 0.3 * vol)
        self._play(tone, 1.0)
        if bounce_count <= 3:
            self._play(self._bounce_base, vol * 0.35)

    def play_rally_milestone(self, bounce_count: int) -> None:
        if bounce_count not in (3, 5, 8):
            return
        freq = 520 + bounce_count * 40
        self._play(_make_tone(freq, 0.1, 0.45), 0.8)

    def play_trail_crawl(self, now: float) -> None:
        """体節が這うときのぽよ音"""
        if now - self._last_trail_at < self._trail_cooldown:
            return
        self._last_trail_at = now
        self._trail_pitch = 0.62 if self._trail_pitch < 0.5 else 0.38
        base = 210.0 if self._trail_pitch < 0.5 else 255.0
        tone = _make_tone(base, 0.035, 0.16)
        self._play(tone, 0.42)

    def play_fence_breach(self, now: float) -> None:
        """体節貫通時のシュッという音"""
        if now - self._last_breach_at < self._breach_cooldown:
            return
        self._last_breach_at = now
        self._play(self._fence_breach, 0.72)

    def play_goal(self) -> None:
        self._play(self._goal, 0.9)

    def play_countdown(self) -> None:
        self._play(self._countdown, 0.7)

    def play_start(self) -> None:
        self._play(self._start, 0.85)
