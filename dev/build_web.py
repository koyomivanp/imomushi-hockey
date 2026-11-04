"""スマホ向け Web 版をビルドする（pygbag）

配布に要るものだけを一時フォルダへ集め、mobile_main.py を main.py として置く。
音声は pygbag が扱える ogg に変換する（要 ffmpeg）。出力先は dist-web/。

    python -m pip install -r requirements-build.txt
    python dev/build_web.py          # ビルドのみ
    python dev/build_web.py --serve  # ローカルサーバーも起動（http://localhost:8000）
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "dist-web"
TEMPLATE = ROOT / "dev" / "web_template.tmpl"
BGM_TRACKS = ("bgm_title", "bgm_battle")
AUDIO_BITRATE = "96k"
EXCLUDED_PY = {"main.py", "mobile_main.py"}


def _stage(stage: Path) -> None:
    for path in ROOT.glob("*.py"):
        if path.name not in EXCLUDED_PY:
            shutil.copy2(path, stage / path.name)
    shutil.copy2(ROOT / "mobile_main.py", stage / "main.py")
    shutil.copytree(
        ROOT / "assets",
        stage / "assets",
        ignore=lambda _dir, names: [n for n in names if n.lower().endswith((".md", ".txt", ".wav", ".mp3"))],
    )
    sounds = ROOT / "assets" / "sounds"
    sources = [sounds / f"{track}.mp3" for track in BGM_TRACKS]
    sources += [path for path in sorted(sounds.glob("*.wav")) if path.stem not in BGM_TRACKS]
    for source in sources:
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error", "-i", str(source),
                "-c:a", "libvorbis", "-b:a", AUDIO_BITRATE, "-ac", "2",
                str(stage / "assets" / "sounds" / f"{source.stem}.ogg"),
            ],
            check=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="imomushi-web-") as tmp:
        stage = Path(tmp) / "imomushi-hockey"
        stage.mkdir()
        _stage(stage)
        subprocess.run(
            [
                sys.executable, "-m", "pygbag", "--build", "--no_opt",
                "--title", "芋虫ホッケー", "--app_name", "imomushi-hockey",
                "--width", "540", "--height", "960",
                "--template", str(TEMPLATE),
                str(stage / "main.py"),
            ],
            check=True,
            cwd=tmp,
        )
        # 確認用サーバーが開いていてもよいよう、フォルダ自体は消さず中身だけ入れ替える
        OUT_DIR.mkdir(exist_ok=True)
        for old in OUT_DIR.iterdir():
            old.unlink()
        shutil.copytree(stage / "build" / "web", OUT_DIR, dirs_exist_ok=True)

    size = sum(p.stat().st_size for p in OUT_DIR.rglob("*") if p.is_file())
    print(f"built: {OUT_DIR} ({size / 1024 / 1024:.1f} MB)")
    if args.serve:
        subprocess.run([sys.executable, "-m", "http.server", "8000", "--directory", str(OUT_DIR)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
