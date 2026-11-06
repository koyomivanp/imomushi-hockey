"""試合結果を X に投稿する画面を開く（ブラウザ版の結果画面から）"""

from __future__ import annotations

import sys
from urllib.parse import quote

from ai import CPU_DIFFICULTY_ORDER, DIFFICULTIES
from constants import CPU_LABEL

GAME_URL = "https://koyomivanp.github.io/imomushi-hockey/play/"
HASHTAG = "#芋虫ホッケー"


def result_post_text(match) -> str:
    a, b = match.scores[0], match.scores[1]
    if match.vs_cpu:
        diff = DIFFICULTIES[CPU_DIFFICULTY_ORDER[match.cpu_diff_index]].label
        rival = f"{CPU_LABEL}（{diff}）"
        if match.winner == 0:
            line = f"芋虫ホッケーで{rival}に {a}-{b} で勝った！🐛"
        elif match.winner == 1:
            line = f"芋虫ホッケーで{rival}に {a}-{b} で負けた…次は勝つ🐛"
        else:
            line = f"芋虫ホッケーで{rival}と {a}-{b} で引き分け🐛"
    elif match.winner is None:
        line = f"芋虫ホッケーで2匹対戦！ {a}-{b} で引き分け🐛"
    else:
        line = f"芋虫ホッケーで2匹対戦！ P1 {a}-{b} P2 でP{match.winner + 1}の勝ち🐛"
    return f"{line}\n{HASHTAG}"


def post_url(text: str) -> str:
    return f"https://x.com/intent/post?text={quote(text, safe='')}&url={quote(GAME_URL, safe='')}"


def open_url(url: str) -> None:
    if sys.platform == "emscripten":
        import platform

        try:
            opened = platform.window.open(url, "_blank")
        except Exception:
            opened = None
        # ポップアップが止められたら、このタブで開く
        if not opened:
            platform.window.location.href = url
        return
    import webbrowser

    webbrowser.open(url)
