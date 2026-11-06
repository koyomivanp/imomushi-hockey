"""効果音・BGM の候補を合成して書き出す（聴き比べ用）

使い方: python dev/sound_lab.py
dev/out/sound_lab/ に候補の wav / mp3 を書き出す。決まったものは assets/sounds へコピーして使う。
音声ファイルの素材は使わず、すべてここで合成する（権利の心配がない）。
"""

from __future__ import annotations

import os
import subprocess
import sys
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "dev", "out", "sound_lab")
SR = 44100
rng = np.random.default_rng(7)


# --- 部品 ---
def midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def times(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * SR)) / SR


def env(seconds: float, attack: float = 0.004, decay: float = 0.3, release: float = 0.02) -> np.ndarray:
    """立ち上がり → 指数で減衰 → 最後に短く消す"""
    t = times(seconds)
    e = np.minimum(1.0, t / max(attack, 1e-5)) * np.exp(-np.maximum(0.0, t - attack) / decay)
    tail = int(release * SR)
    if tail:
        e[-tail:] *= np.linspace(1.0, 0.0, tail)
    return e


def hold_env(seconds: float, attack: float = 0.01, release: float = 0.08) -> np.ndarray:
    n = int(seconds * SR)
    e = np.ones(n)
    a, r = int(attack * SR), int(release * SR)
    e[:a] = np.linspace(0.0, 1.0, a)
    e[-r:] *= np.linspace(1.0, 0.0, r)
    return e


def phase(freq, seconds: float) -> np.ndarray:
    f = np.broadcast_to(np.asarray(freq, dtype=float), (int(seconds * SR),))
    return 2 * np.pi * np.cumsum(f) / SR


def additive(freq, seconds: float, partials: list[tuple[float, float]]) -> np.ndarray:
    """（倍音の倍率, 音量）の和。ナイキストを超える倍音は入れない"""
    ph = phase(freq, seconds)
    top = float(np.max(np.asarray(freq))) if np.ndim(freq) else float(freq)
    out = np.zeros_like(ph)
    for mult, amp in partials:
        if top * mult < SR / 2 * 0.9:
            out += amp * np.sin(ph * mult)
    return out


def saw_partials(n: int = 12) -> list[tuple[float, float]]:
    return [(k, 1.0 / k) for k in range(1, n + 1)]


def square_partials(n: int = 9) -> list[tuple[float, float]]:
    return [(k, 1.0 / k) for k in range(1, n + 1, 2)]


def band(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(spec, len(x))


def noise(seconds: float) -> np.ndarray:
    return rng.uniform(-1.0, 1.0, int(seconds * SR))


def mix_at(buf: np.ndarray, sound: np.ndarray, at: float, gain: float = 1.0, wrap: bool = False) -> None:
    start = int(at * SR)
    end = start + len(sound)
    if end <= len(buf):
        buf[start:end] += sound * gain
        return
    fit = len(buf) - start
    buf[start:] += sound[:fit] * gain
    if wrap:  # ループ曲は、はみ出た余韻を頭に戻す
        rest = sound[fit:]
        buf[: len(rest)] += rest * gain


def normalize(x: np.ndarray, peak: float = 0.89) -> np.ndarray:
    m = np.max(np.abs(x))
    return x if m == 0 else x * (peak / m)


def soft_clip(x: np.ndarray, drive: float = 1.2) -> np.ndarray:
    return np.tanh(x * drive) / np.tanh(drive)


# --- 楽器 ---
def marimba(n: float, seconds: float = 0.5, decay: float = 0.22) -> np.ndarray:
    f = midi(n)
    t = times(seconds)
    body = np.sin(phase(f, seconds)) * env(seconds, 0.002, decay)
    over = 0.35 * np.sin(phase(f * 3.93, seconds)) * np.exp(-t / 0.03)
    click = 0.12 * np.sin(phase(f * 9.2, seconds)) * np.exp(-t / 0.006)
    return body + over + click


def bell(n: float, seconds: float = 0.9, decay: float = 0.35) -> np.ndarray:
    f = midi(n)
    t = times(seconds)
    return (np.sin(phase(f, seconds)) * env(seconds, 0.001, decay)
            + 0.45 * np.sin(phase(f * 2.76, seconds)) * np.exp(-t / (decay * 0.45))
            + 0.25 * np.sin(phase(f * 5.4, seconds)) * np.exp(-t / (decay * 0.2)))


def pluck(n: float, seconds: float = 0.4, decay: float = 0.12, bright: int = 8) -> np.ndarray:
    return additive(midi(n), seconds, saw_partials(bright)) * env(seconds, 0.003, decay) * 0.6


def bass(n: float, seconds: float, kind: str = "round") -> np.ndarray:
    f = midi(n)
    if kind == "round":
        tone = additive(f, seconds, [(1, 1.0), (2, 0.35), (3, 0.12)])
        return tone * env(seconds, 0.004, 0.35, 0.03)
    # 弾むベース（矩形の低いところだけ）
    tone = additive(f, seconds, square_partials(7))
    return soft_clip(tone * 0.8, 1.5) * env(seconds, 0.003, 0.16, 0.03)


def pad(notes: list[float], seconds: float, level: float = 0.18) -> np.ndarray:
    out = np.zeros(int(seconds * SR))
    for n in notes:
        for detune in (-0.08, 0.08):
            out += additive(midi(n + detune), seconds, saw_partials(6))
    return out * hold_env(seconds, 0.12, 0.25) * level / max(1, len(notes))


def flute(n: float, seconds: float) -> np.ndarray:
    t = times(seconds)
    vib = midi(n) * (1 + 0.006 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1, t / 0.2))
    tone = additive(vib, seconds, [(1, 1.0), (2, 0.18), (3, 0.06)])
    breath = band(noise(seconds), midi(n) * 0.8, midi(n) * 3) * 0.05
    return (tone + breath) * hold_env(seconds, 0.03, 0.08)


def kick(level: float = 1.0) -> np.ndarray:
    s = 0.32
    t = times(s)
    f = 48 + 110 * np.exp(-t / 0.035)
    return np.sin(phase(f, s)) * env(s, 0.001, 0.11) * level


def snare(level: float = 1.0) -> np.ndarray:
    s = 0.22
    t = times(s)
    body = np.sin(phase(190, s)) * np.exp(-t / 0.04) * 0.5
    sn = band(noise(s), 1200, 9000) * np.exp(-t / 0.06)
    return (body + sn) * level


def clap(level: float = 1.0) -> np.ndarray:
    s = 0.25
    t = times(s)
    burst = np.zeros_like(t)
    for d in (0.0, 0.011, 0.022):
        burst += np.exp(-np.maximum(0, t - d) / 0.012) * (t >= d)
    tail = np.exp(-t / 0.08) * 0.5
    return band(noise(s), 900, 5000) * (burst * 0.6 + tail) * level


def hat(level: float = 1.0, open_: bool = False) -> np.ndarray:
    s = 0.25 if open_ else 0.06
    t = times(s)
    return band(noise(s), 6000, 16000) * np.exp(-t / (0.09 if open_ else 0.018)) * level


def shaker(level: float = 1.0) -> np.ndarray:
    s = 0.08
    t = times(s)
    e = np.minimum(1, t / 0.012) * np.exp(-t / 0.025)
    return band(noise(s), 4000, 12000) * e * level


def crash(seconds: float = 1.4, level: float = 1.0) -> np.ndarray:
    t = times(seconds)
    return band(noise(seconds), 3500, 16000) * np.exp(-t / 0.45) * level


# --- ホイッスル ---
def whistle(seconds: float, pitch: float = 2950.0, trill: float = 34.0, depth: float = 170.0) -> np.ndarray:
    """審判の笛。中の玉が転がって音が細かく震える（周波数と音量を速く揺らす）"""
    t = times(seconds)
    wobble = np.sin(2 * np.pi * trill * t + 0.3 * np.sin(2 * np.pi * 3.1 * t))
    f = pitch + depth * wobble + 60 * np.minimum(1, t / 0.04)
    tone = np.sin(phase(f, seconds)) + 0.22 * np.sin(phase(f * 2, seconds))
    am = 1 - 0.32 * (0.5 + 0.5 * wobble)
    breath = band(noise(seconds), pitch * 0.75, pitch * 1.5) * 0.22
    return (tone * am + breath) * hold_env(seconds, 0.012, min(0.07, seconds * 0.4))


# --- カウントダウン（3・2・1）と試合開始 ---
def countdown_whistle() -> np.ndarray:
    return normalize(whistle(0.13, 2900, 34, 120), 0.8)


def start_whistle() -> np.ndarray:
    """ピッ、ピーーッ"""
    out = np.zeros(int(1.05 * SR))
    mix_at(out, whistle(0.12, 3050), 0.0)
    mix_at(out, whistle(0.78, 3050), 0.2)
    return normalize(out)


def countdown_beep() -> np.ndarray:
    s = 0.16
    tone = additive(midi(81), s, square_partials(5)) * hold_env(s, 0.004, 0.03)
    return normalize(tone, 0.75)


def start_beep() -> np.ndarray:
    """1 オクターブ上を長く。レースの「ポッ・ポッ・ポッ・ポーン」"""
    s = 0.75
    tone = additive(midi(93), s, square_partials(5)) * env(s, 0.004, 0.6, 0.08)
    tone += 0.4 * additive(midi(88), s, square_partials(3)) * env(s, 0.004, 0.5, 0.08)
    return normalize(tone)


def countdown_wood() -> np.ndarray:
    s = 0.35
    return normalize(marimba(79, s, 0.12) + 0.6 * marimba(67, s, 0.12), 0.8)


def start_wood() -> np.ndarray:
    """木琴の駆け上がり → 笛"""
    out = np.zeros(int(1.0 * SR))
    for i, n in enumerate((72, 76, 79, 84)):
        mix_at(out, marimba(n, 0.4, 0.15), i * 0.045, 0.7)
    mix_at(out, whistle(0.6, 3100), 0.2, 0.9)
    return normalize(out)


# --- ゴール ---
def goal_sparkle() -> np.ndarray:
    """ドンッ＋明るい和音の駆け上がり＋キラキラの余韻"""
    s = 1.5
    out = np.zeros(int(s * SR))
    mix_at(out, kick(1.1), 0.0)
    for i, n in enumerate((72, 76, 79, 84, 88)):
        mix_at(out, bell(n, 1.0, 0.45), 0.012 + i * 0.045, 0.55)
    mix_at(out, pad([60, 64, 67, 72], 1.2, 0.5), 0.0)
    sparkle_rng = np.random.default_rng(3)
    for k in range(14):
        n = 96 + sparkle_rng.integers(-5, 6)
        mix_at(out, bell(float(n), 0.3, 0.08), 0.25 + k * 0.06, 0.18 * (1 - k / 16))
    return normalize(soft_clip(out, 1.1))


def goal_cheer() -> np.ndarray:
    """短いファンファーレ＋歓声"""
    s = 1.7
    out = np.zeros(int(s * SR))
    t = times(s)
    swell = np.minimum(1, t / 0.08) * np.exp(-np.maximum(0, t - 0.25) / 0.6)
    crowd = np.zeros_like(t)
    crowd_rng = np.random.default_rng(11)
    for _ in range(9):  # 人の声の帯域をずらして重ね、ゆっくり揺らす
        lo = crowd_rng.uniform(350, 900)
        voice = band(noise(s), lo, lo * 2.6)
        crowd += voice * (0.6 + 0.4 * np.sin(2 * np.pi * crowd_rng.uniform(2, 6) * t + crowd_rng.uniform(0, 6)))
    out += crowd / 9 * swell * 1.6
    for at, notes, dur in ((0.0, (67, 72, 76), 0.12), (0.14, (72, 76, 79), 0.55)):
        for n in notes:
            stab = additive(midi(n), dur, saw_partials(9)) * hold_env(dur, 0.006, 0.12)
            mix_at(out, stab, at, 0.22)
    mix_at(out, kick(0.9), 0.0)
    return normalize(soft_clip(out, 1.2))


def goal_boom() -> np.ndarray:
    """太鼓ドン！＋シンバル＋「タ・ダーン」"""
    s = 1.6
    out = np.zeros(int(s * SR))
    big = kick(1.0)
    mix_at(out, big, 0.0, 1.3)
    mix_at(out, crash(1.5), 0.0, 0.45)
    for at, notes, dur in ((0.05, (79, 74, 67), 0.11), (0.18, (84, 79, 76, 72), 0.9)):
        for n in notes:
            horn = additive(midi(n), dur, saw_partials(7))
            horn *= hold_env(dur, 0.012, 0.3 if dur > 0.5 else 0.03)
            mix_at(out, horn, at, 0.2)
    return normalize(soft_clip(out, 1.3))


# --- 対戦 BGM（16 小節のループ） ---
def render_loop(bpm: float, bars: int, parts) -> np.ndarray:
    beat = 60.0 / bpm
    total = bars * 4 * beat
    buf = np.zeros(int(total * SR))
    for at_beat, sound, gain in parts(beat):
        mix_at(buf, sound, at_beat * beat, gain, wrap=True)
    return buf


def bgm_march() -> np.ndarray:
    """A: 明るく跳ねる 132BPM。木琴の伴奏とシェイカー、メロディーは 2 小節おきに少しだけ"""
    bpm = 132
    chords = [(60, 64, 67), (57, 60, 64), (53, 57, 60), (55, 59, 62)] * 3 + \
             [(60, 64, 67), (57, 60, 64), (53, 57, 60), (55, 59, 65)]
    melody = [  # [拍, MIDI, 長さ（拍）]
        (4, 79, 0.5), (4.5, 76, 0.5), (5, 79, 1), (6, 81, 1.5),
        (12, 76, 0.5), (12.5, 74, 0.5), (13, 72, 1), (14, 74, 1.5),
        (20, 79, 0.5), (20.5, 81, 0.5), (21, 84, 1), (22, 83, 0.5), (22.5, 81, 1),
        (28, 79, 0.5), (28.5, 76, 0.5), (29, 74, 2),
        (36, 79, 0.5), (36.5, 76, 0.5), (37, 79, 1), (38, 81, 1.5),
        (44, 84, 0.5), (44.5, 83, 0.5), (45, 81, 1), (46, 79, 1.5),
        (52, 76, 0.5), (52.5, 79, 0.5), (53, 81, 1), (54, 84, 1.5),
        (60, 83, 0.5), (60.5, 81, 0.5), (61, 79, 1), (62, 74, 1.5),
    ]

    def parts(beat):
        for bar, chord in enumerate(chords):
            b0 = bar * 4
            root = chord[0] - 12
            for i, step in enumerate((0, 1.5, 2, 3.5)):
                yield b0 + step, bass(root if i % 2 == 0 else root + 7, beat * 0.9), 0.5
            for step in (0.5, 1.5, 2.5, 3.5):
                for n in chord:
                    yield b0 + step, marimba(n + 12, beat, 0.12), 0.11
            for step in (0, 2):
                yield b0 + step, kick(), 0.55
            for step in (1, 3):
                yield b0 + step, clap(), 0.22
            for k in range(8):
                yield b0 + k * 0.5, shaker(), 0.10 if k % 2 else 0.06
            if bar % 4 == 3:
                for k in range(4):
                    yield b0 + 3 + k * 0.25, snare(0.5 + k * 0.15), 0.12
        for at, n, length in melody:
            yield at, flute(n, length * beat * 0.95), 0.13

    return render_loop(bpm, len(chords), parts)


def bgm_funk() -> np.ndarray:
    """B: 弾むベースとハイハットが主役の 116BPM。メロディーはなく、合いの手だけ（いちばん邪魔しない）"""
    bpm = 116
    roots = [57, 57, 55, 55, 53, 53, 52, 52] * 2  # Am - G - F - E
    chord_of = {57: (69, 72, 76), 55: (67, 71, 74), 53: (65, 69, 72), 52: (64, 68, 71)}
    groove = [(0, 0, 0.6), (0.75, 0, 0.25), (1.5, 12, 0.25), (2, 0, 0.5), (2.75, 7, 0.25), (3.25, 10, 0.25), (3.5, 12, 0.4)]

    def parts(beat):
        for bar, root in enumerate(roots):
            b0 = bar * 4
            for step, iv, length in groove:
                yield b0 + step, bass(root - 24 + iv, beat * length, "punch"), 0.5
            for step in (0, 2.5):
                yield b0 + step, kick(), 0.6
            for step in (1, 3):
                yield b0 + step, snare(), 0.24
            for k in range(16):
                yield b0 + k * 0.25, hat(open_=(k % 8 == 6)), (0.09 if k % 2 else 0.05)
            for step in (0.5, 1.75, 2.5, 3.75):  # 裏で刻む和音
                for n in chord_of[root]:
                    yield b0 + step, pluck(n - 12, 0.25, 0.05, 6), 0.08
            if bar % 4 == 3:  # 4 小節ごとの合いの手
                for i, n in enumerate((76, 79, 81, 84)):
                    yield b0 + 2 + i * 0.25, marimba(n, 0.4, 0.12), 0.14
        for bar in range(0, len(roots), 2):
            yield bar * 4, pad([n - 12 for n in chord_of[roots[bar]]], 8 * 60 / bpm, 0.5), 0.35

    return render_loop(bpm, len(roots), parts)


def bgm_rush() -> np.ndarray:
    """C: 疾走感の 150BPM。4 つ打ちと 16 分のアルペジオ、8 小節目と 16 小節目で盛り上げ"""
    bpm = 150
    chords = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62)] * 4  # Am F C G

    def parts(beat):
        for bar, chord in enumerate(chords):
            b0 = bar * 4
            root = chord[0] - 24
            for k in range(8):
                yield b0 + k * 0.5, bass(root + (12 if k % 2 else 0), beat * 0.45, "punch"), 0.45
            for k in range(4):
                yield b0 + k, kick(), 0.55
            for step in (1, 3):
                yield b0 + step, clap(), 0.2
            for k in range(8):
                yield b0 + k * 0.5 + 0.5 * 0.5, hat(), 0.08
            arp = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[1] + 24]
            for k in range(16):
                yield b0 + k * 0.25, pluck(arp[k % 4], 0.18, 0.06, 5), 0.07
            if bar % 8 == 7:  # 盛り上げ：スネアの連打と上昇
                for k in range(8):
                    yield b0 + 2 + k * 0.25, snare(0.4 + k * 0.08), 0.13
            if bar % 8 == 0:
                yield b0, crash(1.2), 0.18
            if bar % 2 == 0:
                yield b0, pad(list(chord), 8 * 60 / bpm, 0.5), 0.3

    return render_loop(bpm, len(chords), parts)


# --- 書き出し ---
def write_wav(name: str, x: np.ndarray) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{name}.wav")
    data = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    stereo = np.repeat(data[:, None], 2, axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())
    return path


def write_mp3(name: str, x: np.ndarray) -> str:
    wav = write_wav(name, x)
    mp3 = wav[:-4] + ".mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libmp3lame", "-b:a", "128k", mp3], check=True)
    os.remove(wav)
    return mp3


CANDIDATES = {
    "countdown_whistle": countdown_whistle,
    "start_whistle": start_whistle,
    "countdown_beep": countdown_beep,
    "start_beep": start_beep,
    "countdown_wood": countdown_wood,
    "start_wood": start_wood,
    "goal_sparkle": goal_sparkle,
    "goal_cheer": goal_cheer,
    "goal_boom": goal_boom,
}
BGM_CANDIDATES = {
    "bgm_march": bgm_march,
    "bgm_funk": bgm_funk,
    "bgm_rush": bgm_rush,
}


# 聞こえる大きさ（LUFS）。ゲーム内の音量をかける前のファイルの大きさをそろえる
LOUDNESS = {"countdown": -22.0, "start": -19.0, "goal": -17.0, "bgm": -19.0}  # 1ch で測るので、2ch のファイルは約 3 dB 大きく出る


def loudness(x: np.ndarray) -> float:
    """ffmpeg の ebur128 で測る。短い音は無音を足して 1 秒以上にしてから測る"""
    padded = np.concatenate([x, np.zeros(max(0, SR - len(x)))])
    data = (np.clip(padded, -1, 1) * 32767).astype(np.int16).tobytes()
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-",
         "-af", "ebur128", "-f", "null", "-"],
        input=data, capture_output=True, check=True,
    )
    lines = [line for line in result.stderr.decode("utf-8", "replace").splitlines() if line.strip().startswith("I:")]
    return float(lines[-1].split()[1])


def to_loudness(x: np.ndarray, target: float) -> np.ndarray:
    for _ in range(2):  # 短い音は無音の分だけ測り方がずれるので 2 回合わせる
        x = x * 10 ** ((target - loudness(x)) / 20)
    return np.clip(x, -0.98, 0.98)


def main() -> int:
    only = set(sys.argv[1:])
    for name, make in CANDIDATES.items():
        if not only or name in only:
            target = LOUDNESS[name.split("_")[0]]
            print(write_wav(name, to_loudness(make(), target)))
    for name, make in BGM_CANDIDATES.items():
        if not only or name in only:
            print(write_mp3(name, to_loudness(normalize(soft_clip(make(), 1.1)), LOUDNESS["bgm"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
