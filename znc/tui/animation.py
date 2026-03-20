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

    밝은 점(phase % len)이 텍스트를 좌→우로 스캔.
    최소 밝기를 base_style 의 dim 으로 유지해 항상 읽힘.

      dist 0  → bold #e6edf3 (흰색 하이라이트)
      dist 1  → bold base_style
      dist 2+ → base_style / dim base_style
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
        elif dist <= 3:
            t.append(char, style=base_style)
        else:
            # 최소 밝기: dim base_style — 항상 읽히도록 (dim #484f58 는 사용 안 함)
            t.append(char, style=f"dim {base_style}")
    return t
