"""
StatusBar — 레이어1.

채팅창 하단, 입력창 위에 고정된 1줄짜리 상태 바.
현재 단계 + 경과 시간 + 스피너 애니메이션을 표시한다.
idle 상태에서는 완전히 비워진다.

레이아웃:
  [단계]  detail text                     0.0s  [L] log
          ↑ STAGE_STYLE 색상              ↑ dim  ↑ 토글 힌트
"""
from __future__ import annotations

from time import monotonic

from rich.text import Text
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget

from znc.tui.process_state import ProcessState, Stage, STAGE_LABEL, STAGE_STYLE

_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_ACTIVE_STAGES = {
    Stage.LOADING, Stage.MEMORY, Stage.SEARCH,
    Stage.CRAWL, Stage.THINKING, Stage.GENERATING,
}


class StatusBar(Widget):
    """1줄 상태 바 위젯."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: #0d1117;
        border-top: tall #21262d;
        padding: 0 1;
        color: #8b949e;
    }
    """

    _tick: int = 0

    def __init__(self, process_state: ProcessState) -> None:
        super().__init__(id="status-bar")
        self._ps = process_state
        self._timer: Timer | None = None
        self._log_visible = False

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.1, self._on_tick)

    def _on_tick(self) -> None:
        self._tick = (self._tick + 1) % len(_SPINNER)
        self.refresh()

    # 외부에서 호출
    def set_state(self, process_state: ProcessState) -> None:
        self._ps = process_state
        self.refresh()

    def set_log_visible(self, visible: bool) -> None:
        self._log_visible = visible
        self.refresh()

    def render(self) -> Text:
        ps = self._ps
        stage = ps.stage

        if stage == Stage.IDLE:
            return Text("")

        label = STAGE_LABEL.get(stage, stage.value)
        style = STAGE_STYLE.get(stage, "")
        active = stage in _ACTIVE_STAGES

        t = Text()

        # 스피너 (활성 단계에만)
        if active:
            t.append(_SPINNER[self._tick] + "  ", style=style)
        else:
            t.append("   ")

        # 단계 레이블
        t.append(f"{label}", style=f"bold {style}")

        # 세부 내용
        if ps.detail:
            detail = ps.detail
            # 너비에 맞게 자르기 (대략 터미널 폭 - 20 정도)
            if len(detail) > 60:
                detail = detail[:57] + "..."
            t.append(f"  {detail}", style="#484f58")

        # 경과 시간 (오른쪽 정렬 흉내 — 패딩으로 밀기)
        elapsed = f"{ps.total_elapsed:.1f}s"
        pad = max(1, 72 - len(t.plain) - len(elapsed))
        t.append(" " * pad)
        t.append(elapsed, style="dim #484f58")

        # 로그 토글 힌트 + 스트리밍 중이면 Esc 중단 힌트
        log_marker = "[dim][^L] log[/dim]" if not self._log_visible else "[dim #58a6ff][^L] log ▲[/]"
        t.append("  ")
        t.append_text(Text.from_markup(log_marker))

        if stage in {Stage.THINKING, Stage.GENERATING, Stage.SEARCH, Stage.CRAWL}:
            t.append("  ")
            t.append_text(Text.from_markup("[bold #f85149][Esc] stop[/]"))

        return t
