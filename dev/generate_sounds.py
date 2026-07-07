"""森テーマ SE / BGM をプロシージャル生成（Summer MCP 代替）"""

from __future__ import annotations

import array
import math
import os
import struct
import sys
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets", "sounds")
SAMPLE_RATE = 22050


def _write_wav(path: str, samples: array.array) -> None:
    with wave.open(path, "w") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(samples.tobytes())


def _stereo(mono: list[int]) -> array.array:
    buf = array.array("h")
    for v in mono:
        buf.append(v)
        buf.append(v)
    return buf


def _env(t: float, attack: float, decay: float, duration: float) -> float:
    if t < attack:
        return t / max(attack, 1e-6)
    if t > duration - decay:
        return max(0.0, (duration - t) / max(decay, 1e-6))
    return 1.0


def synth_wood_tap() -> array.array:
    duration = 0.11
    n = int(SAMPLE_RATE * duration)
    mono: list[int] = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = _env(t, 0.003, 0.05, duration) * math.exp(-t * 28)
        thump = math.sin(2 * math.pi * 95 * t) * 0.42 * math.exp(-t * 22)
        body = math.sin(2 * math.pi * 145 * t) * 0.55 + math.sin(2 * math.pi * 290 * t) * 0.18
        click = math.sin(2 * math.pi * 380 * t) * 0.14 * math.exp(-t * 95)
        grain = math.sin(t * 6800 + i * 0.6) * 0.1 * math.exp(-t * 50)
        v = int(32767 * 0.48 * env * (thump + body + click + grain))
        mono.append(v)
    return _stereo(mono)


def synth_leaf_swoosh() -> array.array:
    duration = 0.14
    n = int(SAMPLE_RATE * duration)
    mono: list[int] = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = (1.0 - t / duration) * math.exp(-t * 12)
        freq = 900 - 520 * (t / duration)
        tone = math.sin(2 * math.pi * freq * t) * 0.35
        rustle = math.sin(t * 6200 + i * 1.3) * 0.18 * (1.0 - t / duration)
        v = int(32767 * 0.38 * env * (tone + rustle))
        mono.append(v)
    return _stereo(mono)


def synth_goal_chime() -> array.array:
    duration = 0.42
    freqs = (392.0, 523.25, 659.25)
    n = int(SAMPLE_RATE * duration)
    mono: list[int] = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 5.5)
        sample = 0.0
        for j, f in enumerate(freqs):
            onset = j * 0.06
            if t >= onset:
                sample += math.sin(2 * math.pi * f * (t - onset)) * 0.32 * math.exp(-(t - onset) * 4)
        flutter = math.sin(t * 4800) * 0.04 * math.exp(-t * 18)
        v = int(32767 * 0.5 * env * (sample + flutter))
        mono.append(v)
    return _stereo(mono)


def synth_pop() -> array.array:
    duration = 0.07
    n = int(SAMPLE_RATE * duration)
    mono: list[int] = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 40)
        v = int(32767 * 0.3 * env * math.sin(2 * math.pi * 320 * t))
        mono.append(v)
    return _stereo(mono)


def synth_start_fanfare() -> array.array:
    duration = 0.22
    notes = ((293.66, 0.0), (440.0, 0.09))
    n = int(SAMPLE_RATE * duration)
    mono: list[int] = []
    for i in range(n):
        t = i / SAMPLE_RATE
        sample = 0.0
        for freq, onset in notes:
            if t >= onset:
                sample += math.sin(2 * math.pi * freq * (t - onset)) * 0.38 * math.exp(-(t - onset) * 8)
        v = int(32767 * 0.45 * sample)
        mono.append(v)
    return _stereo(mono)


def synth_score_tick() -> array.array:
    duration = 0.12
    freqs = (523.25, 659.25)
    n = int(SAMPLE_RATE * duration)
    mono: list[int] = []
    for i in range(n):
        t = i / SAMPLE_RATE
        sample = 0.0
        for j, f in enumerate(freqs):
            onset = j * 0.04
            if t >= onset:
                sample += math.sin(2 * math.pi * f * (t - onset)) * 0.42 * math.exp(-(t - onset) * 9)
        wood = math.sin(2 * math.pi * 196 * t) * 0.08 * math.exp(-t * 18)
        v = int(32767 * 0.34 * sample * math.exp(-t * 6) + 32767 * wood)
        mono.append(v)
    return _stereo(mono)


def synth_victory_fanfare() -> array.array:
    duration = 0.78
    notes = ((392.0, 0.0), (523.25, 0.14), (659.25, 0.28), (783.99, 0.42))
    n = int(SAMPLE_RATE * duration)
    mono: list[int] = []
    for i in range(n):
        t = i / SAMPLE_RATE
        sample = 0.0
        for freq, onset in notes:
            if t >= onset:
                sample += math.sin(2 * math.pi * freq * (t - onset)) * 0.34 * math.exp(-(t - onset) * 3.2)
        flutter = math.sin(t * 4200) * 0.05 * math.exp(-t * 10)
        v = int(32767 * 0.52 * (sample + flutter) * math.exp(-t * 2.8))
        mono.append(v)
    return _stereo(mono)


def synth_defeat_tone() -> array.array:
    duration = 0.55
    notes = ((349.23, 0.0), (261.63, 0.22))
    n = int(SAMPLE_RATE * duration)
    mono: list[int] = []
    for i in range(n):
        t = i / SAMPLE_RATE
        sample = 0.0
        for freq, onset in notes:
            if t >= onset:
                sample += math.sin(2 * math.pi * freq * (t - onset)) * 0.36 * math.exp(-(t - onset) * 4.5)
        v = int(32767 * 0.38 * sample * math.exp(-t * 3.5))
        mono.append(v)
    return _stereo(mono)


def synth_menu_move() -> array.array:
    duration = 0.06
    n = int(SAMPLE_RATE * duration)
    mono: list[int] = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 55)
        tap = math.sin(2 * math.pi * 280 * t) * 0.5 + math.sin(2 * math.pi * 420 * t) * 0.15 * math.exp(-t * 80)
        v = int(32767 * 0.26 * env * tap)
        mono.append(v)
    return _stereo(mono)


def synth_result_card() -> array.array:
    duration = 0.32
    n = int(SAMPLE_RATE * duration)
    mono: list[int] = []
    for i in range(n):
        t = i / SAMPLE_RATE
        swoosh_env = (1.0 - t / duration) * math.exp(-t * 8)
        freq = 720.0 - 380.0 * (t / duration)
        swoosh = math.sin(2 * math.pi * freq * t) * 0.28 * swoosh_env
        chime = 0.0
        if t >= 0.12:
            ct = t - 0.12
            chime = math.sin(2 * math.pi * 440 * ct) * 0.3 * math.exp(-ct * 7)
        v = int(32767 * 0.36 * (swoosh + chime))
        mono.append(v)
    return _stereo(mono)


def _ambient_track(bpm: float, chords: list[tuple[float, ...]], seconds: float, pulse: float) -> array.array:
    n = int(SAMPLE_RATE * seconds)
    beat = 60.0 / bpm
    mono: list[int] = []
    for i in range(n):
        t = i / SAMPLE_RATE
        beat_t = (t % (beat * 4)) / beat
        chord_idx = int(t / (beat * 8)) % len(chords)
        freqs = chords[chord_idx]
        pad = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs)
        marimba = 0.0
        if pulse > 0 and beat_t < 0.08:
            marimba = math.sin(2 * math.pi * freqs[1] * 2 * t) * pulse * math.exp(-beat_t * 20)
        rustle = math.sin(t * 3100 + i * 0.02) * 0.03
        env = 0.55 + 0.08 * math.sin(t * 0.4)
        v = int(32767 * 0.22 * env * (pad * 0.7 + marimba + rustle))
        mono.append(v)
    return _stereo(mono)


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    assets = {
        "wall_bounce.wav": synth_wood_tap(),
        "fence_breach.wav": synth_leaf_swoosh(),
        "goal.wav": synth_goal_chime(),
        "countdown.wav": synth_pop(),
        "start.wav": synth_start_fanfare(),
        "score_tick.wav": synth_score_tick(),
        "victory.wav": synth_victory_fanfare(),
        "defeat.wav": synth_defeat_tone(),
        "menu_move.wav": synth_menu_move(),
        "result_card.wav": synth_result_card(),
        "bgm_title.wav": _ambient_track(
            85,
            [(146.83, 220.0, 293.66), (164.81, 246.94, 329.63)],
            32.0,
            pulse=0.0,
        ),
        "bgm_battle.wav": _ambient_track(
            104,
            [(146.83, 220.0, 293.66), (174.61, 261.63, 349.23)],
            32.0,
            pulse=0.12,
        ),
    }
    for name, samples in assets.items():
        path = os.path.join(OUT_DIR, name)
        _write_wav(path, samples)
        print(f"  {path}")
    print(f"Wrote {len(assets)} sound assets to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
