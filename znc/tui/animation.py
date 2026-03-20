"""
Cursor 스타일 shimmer 애니메이션 유틸리티.

밝은 점이 왼쪽→오른쪽으로 스캔하며 각 글자의 밝기가 변한다.
StatusBar 단계 레이블과 ProcessLog 활성 스텝에 적용.
"""
from __future__ import annotations

from rich.text import Text

# 활성(애니메이션) 단계
from znc.tui.process_state import Stage

SHIMMER_STAGES = {
    Stage.LOADING, Stage.MEMORY, Stage.SEARCH,
    Stage.CRAWL, Stage.THINKING, Stage.GENERATING,
}


def shimmer(text: str, phase: int, base_style: str) -> Text:
    """
    Cursor 스타일 shimmer.

    밝은 점(phase % len)이 텍스트를 좌→우로 스캔한다.
    각 글자는 밝은 점과의 거리에 따라 밝기가 결정된다:
      dist 0  → bold 흰색 하이라이트
      dist 1  → bold base_style
      dist 2  → base_style
      dist 3-4 → dim base_style
      그 외   → 매우 dim
    """
    t = Text()
    n = len(text)
    if n == 0:
        return t

    pos = phase % n
    for i, char in enumerate(text):
        dist = min(abs(i - pos), n - abs(i - pos))
        if dist == 0:
            t.append(char, style="bold #e6edf3")
        elif dist == 1:
            t.append(char, style=f"bold {base_style}")
        elif dist == 2:
            t.append(char, style=base_style)
        elif dist <= 4:
            t.append(char, style=f"dim {base_style}")
        else:
            t.append(char, style="dim #484f58")
    return t
