"""
StatusBar — 레이어1.

채팅창 하단, 입력창 위에 고정된 1줄짜리 상태 바.

레이아웃 (활성 시):
  ⠸  thinking  detail...   prep → mem → thinking    2.1s  [^L]▼  [Esc] stop
  ^   ^         ^           ^ 최근 3단계 브레드크럼  ^              ^
  스피너        현재단계     (LogPanel 접힘 시만 표시)

LogPanel 펼침 시 브레드크럼 숨김 (이미 상세 로그가 보이므로).
"""
from __future__ import annotations

from rich.text import Text
from textual.timer import Timer
from textual.widget import Widget

from znc.tui.process_state import ProcessState, Stage, STAGE_LABEL, STAGE_STYLE

_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_ACTIVE_STAGES = {
    Stage.LOADING, Stage.MEMORY, Stage.SEARCH,
    Stage.CRAWL, Stage.THINKING, Stage.GENERATING,
}
# 브레드크럼에 표시할 축약 레이블
_CRUMB_LABEL: dict[Stage, str] = {
    Stage.LOADING:    "prep",
    Stage.MEMORY:     "mem",
    Stage.SEARCH:     "search",
    Stage.CRAWL:      "crawl",
    Stage.THINKING:   "think",
    Stage.GENERATING: "gen",
    Stage.DONE:       "done",
    Stage.ERROR:      "err",
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

    def set_state(self, process_state: ProcessState) -> None:
        self._ps = process_state
        self.refresh()

    def set_log_visible(self, visible: bool) -> None:
        self._log_visible = visible
        self.refresh()

    def render(self) -> Text:
        ps = self._ps
        stage = ps.stage
        log_marker = (
            "[dim #484f58][^L]▼[/]"
            if not self._log_visible
            else "[#58a6ff][^L]▲[/]"
        )

        if stage == Stage.IDLE:
            t = Text()
            t.append_text(Text.from_markup(log_marker))
            return t

        label = STAGE_LABEL.get(stage, stage.value)
        style = STAGE_STYLE.get(stage, "")
        active = stage in _ACTIVE_STAGES

        t = Text()

        # 스피너
        if active:
            t.append(_SPINNER[self._tick] + "  ", style=style)
        else:
            t.append("   ")

        # 현재 단계
        t.append(f"{label}", style=f"bold {style}")

        # 세부 내용
        if ps.detail:
            detail = ps.detail[:55] + "..." if len(ps.detail) > 55 else ps.detail
            t.append(f"  {detail}", style="#484f58")

        # 브레드크럼: 로그 접힌 상태에서만 최근 단계 요약 표시
        if not self._log_visible and ps.steps:
            crumbs = [
                _CRUMB_LABEL.get(s.stage, "")
                for s in ps.steps
                if s.stage not in {Stage.IDLE} and _CRUMB_LABEL.get(s.stage)
            ]
            # 중복 제거 (연속 동일 단계)
            deduped = []
            for c in crumbs:
                if not deduped or deduped[-1] != c:
                    deduped.append(c)
            if deduped:
                crumb_str = " → ".join(deduped[-4:])   # 최대 4단계
                t.append(f"   {crumb_str}", style="dim #30363d")

        # 경과 시간
        elapsed = f"{ps.total_elapsed:.1f}s"
        pad = max(1, 74 - len(t.plain) - len(elapsed))
        t.append(" " * pad)
        t.append(elapsed, style="dim #484f58")

        # 로그 토글 힌트
        t.append("  ")
        t.append_text(Text.from_markup(log_marker))

        # 스트리밍 중 중단 힌트
        if stage in {Stage.THINKING, Stage.GENERATING, Stage.SEARCH, Stage.CRAWL}:
            t.append("  ")
            t.append_text(Text.from_markup("[bold #f85149][Esc]stop[/]"))

        return t
