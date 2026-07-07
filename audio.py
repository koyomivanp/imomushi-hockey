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


def _make_wood_tap(duration: float = 0.11, volume: float = 0.48) -> pygame.mixer.Sound:
    n = int(SAMPLE_RATE * duration)
    buf = array.array("h")
    max_amp = int(32767 * volume)
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 28)
        thump = math.sin(2 * math.pi * 95 * t) * 0.42 * math.exp(-t * 22)
        body = math.sin(2 * math.pi * 145 * t) * 0.55 + math.sin(2 * math.pi * 290 * t) * 0.18
        click = math.sin(2 * math.pi * 380 * t) * 0.14 * math.exp(-t * 95)
        grain = math.sin(t * 6800 + i * 0.6) * 0.1 * math.exp(-t * 50)
        v = int(max_amp * env * (thump + body + click + grain))
        buf.append(v)
        buf.append(v)
    return pygame.mixer.Sound(buffer=buf)


def _make_leaf_swoosh(duration: float = 0.14, volume: float = 0.38) -> pygame.mixer.Sound:
    n = int(SAMPLE_RATE * duration)
    buf = array.array("h")
    max_amp = int(32767 * volume)
    for i in range(n):
        t = i / SAMPLE_RATE
        env = (1.0 - t / duration) * math.exp(-t * 12)
        freq = 900.0 - 520.0 * (t / duration)
        tone = math.sin(2 * math.pi * freq * t) * 0.35
        rustle = math.sin(t * 6200 + i * 1.3) * 0.18 * (1.0 - t / duration)
        v = int(max_amp * env * (tone + rustle))
        buf.append(v)
        buf.append(v)
    return pygame.mixer.Sound(buffer=buf)


def _make_goal_chime(duration: float = 0.42, volume: float = 0.5) -> pygame.mixer.Sound:
    freqs = (392.0, 523.25, 659.25)
    n = int(SAMPLE_RATE * duration)
    buf = array.array("h")
    max_amp = int(32767 * volume)
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 5.5)
        sample = 0.0
        for j, f in enumerate(freqs):
            onset = j * 0.06
            if t >= onset:
                sample += math.sin(2 * math.pi * f * (t - onset)) * 0.32 * math.exp(-(t - onset) * 4)
        v = int(max_amp * env * sample)
        buf.append(v)
        buf.append(v)
    return pygame.mixer.Sound(buffer=buf)


def _make_pop(freq: float = 320.0, duration: float = 0.07, volume: float = 0.3) -> pygame.mixer.Sound:
    n = int(SAMPLE_RATE * duration)
    buf = array.array("h")
    max_amp = int(32767 * volume)
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 40)
        v = int(max_amp * env * math.sin(2 * math.pi * freq * t))
        buf.append(v)
        buf.append(v)
    return pygame.mixer.Sound(buffer=buf)


def _make_trail_boop(base: float, duration: float = 0.032, volume: float = 0.1) -> pygame.mixer.Sound:
    n = int(SAMPLE_RATE * duration)
    buf = array.array("h")
    max_amp = int(32767 * volume)
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 72)
        soft = math.sin(2 * math.pi * base * t) * 0.55
        squish = math.sin(2 * math.pi * base * 0.75 * t) * 0.25 * math.exp(-t * 90)
        v = int(max_amp * env * (soft + squish))
        buf.append(v)
        buf.append(v)
    return pygame.mixer.Sound(buffer=buf)


def _load_or_wood_tap(name: str) -> pygame.mixer.Sound:
    for ext in (".wav", ".ogg", ".mp3"):
        path = SOUNDS_DIR / f"{name}{ext}"
        if path.is_file():
            try:
                return pygame.mixer.Sound(str(path))
            except pygame.error:
                pass
    return _make_wood_tap()


def _load_or_leaf_swoosh(name: str) -> pygame.mixer.Sound:
    for ext in (".wav", ".ogg", ".mp3"):
        path = SOUNDS_DIR / f"{name}{ext}"
        if path.is_file():
            try:
                return pygame.mixer.Sound(str(path))
            except pygame.error:
                pass
    return _make_leaf_swoosh()


def _load_or_goal(name: str) -> pygame.mixer.Sound:
    for ext in (".wav", ".ogg", ".mp3"):
        path = SOUNDS_DIR / f"{name}{ext}"
        if path.is_file():
            try:
                return pygame.mixer.Sound(str(path))
            except pygame.error:
                pass
    return _make_goal_chime()


def _load_or_pop(name: str, freq: float) -> pygame.mixer.Sound:
    for ext in (".wav", ".ogg", ".mp3"):
        path = SOUNDS_DIR / f"{name}{ext}"
        if path.is_file():
            try:
                return pygame.mixer.Sound(str(path))
            except pygame.error:
                pass
    return _make_pop(freq)


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
        self._bounce_base = _load_or_wood_tap("wall_bounce")
        self._goal = _load_or_goal("goal")
        self._countdown = _load_or_pop("countdown", 320.0)
        self._start = _load_or_pop("start", 440.0)
        self._fence_breach = _load_or_leaf_swoosh("fence_breach")
        self._last_bounce_at = 0.0
        self._last_trail_at = 0.0
        self._last_breach_at = 0.0
        self._bounce_cooldown = 0.045
        self._trail_cooldown = 0.065
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

    def set_bgm_for_state(self, state_name: str) -> None:
        if state_name == "TITLE" or state_name in ("CPU_DIFF", "PREP"):
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
        vol = min(0.32, 0.14 + bounce_count * 0.012)
        self._play(self._bounce_base, vol)

    def play_rally_milestone(self, bounce_count: int) -> None:
        if bounce_count not in (3, 5, 8):
            return
        self._play(self._bounce_base, min(0.28, 0.18 + bounce_count * 0.008))

    def play_trail_crawl(self, now: float) -> None:
        """体節が這うときのぽよ音"""
        if now - self._last_trail_at < self._trail_cooldown:
            return
        self._last_trail_at = now
        self._trail_pitch = 0.62 if self._trail_pitch < 0.5 else 0.38
        base = 130.0 if self._trail_pitch < 0.5 else 155.0
        tone = _make_trail_boop(base)
        self._play(tone, 0.17)

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
