"""
ProcessLog — 레이어2.

L 키로 토글하는 콜랩서블 패널.
현재 응답 생성의 전체 단계 타임라인을 표시한다.

열린 상태 예시:
┌──────────────────────────────────────────────────────────────────┐
│  0.00s  preparing                                                │
│  0.01s  memory     3 items loaded                               │
│  0.12s  searching  "python 3.13"  [ddg+naver]                   │
│  0.44s  crawling   docs.python.org                              │
│  1.23s  crawling   realpython.com                               │
│  2.01s  thinking   waiting for first token                      │
│  2.34s  generating streaming...                                  │
│  5.11s  done                                                    │
└──────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import RichLog

from znc.tui.process_state import ProcessState, Stage, STAGE_LABEL, STAGE_STYLE

_PANEL_HEIGHT = 8   # 열렸을 때 줄 수


class ProcessLog(Widget):
    """단계 타임라인 콜랩서블 패널."""

    DEFAULT_CSS = f"""
    ProcessLog {{
        height: {_PANEL_HEIGHT};
        background: #0d1117;
        border-top: tall #21262d;
        border-bottom: tall #21262d;
        display: none;
    }}
    ProcessLog.--visible {{
        display: block;
    }}
    #proc-log {{
        background: #0d1117;
        padding: 0 1;
        scrollbar-background: #0d1117;
        scrollbar-color: #21262d;
    }}
    """

    def __init__(self, process_state: ProcessState) -> None:
        super().__init__(id="process-log")
        self._ps = process_state

    def compose(self) -> ComposeResult:
        yield RichLog(id="proc-log", wrap=False, highlight=False, markup=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self) -> None:
        self.add_class("--visible")
        self._redraw()

    def hide(self) -> None:
        self.remove_class("--visible")

    def toggle(self) -> bool:
        """토글. 열린 상태면 True 반환."""
        if "--visible" in self.classes:
            self.hide()
            return False
        else:
            self.show()
            return True

    def set_state(self, process_state: ProcessState) -> None:
        self._ps = process_state
        if "--visible" in self.classes:
            self._redraw()

    def append_step(self) -> None:
        """마지막 step 하나를 로그에 추가 (증분 업데이트)."""
        if not self._ps.steps:
            return
        log = self.query_one("#proc-log", RichLog)
        step = self._ps.steps[-1]
        log.write(self._format_step(step))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _redraw(self) -> None:
        log = self.query_one("#proc-log", RichLog)
        log.clear()
        for step in self._ps.steps:
            log.write(self._format_step(step))

    def _format_step(self, step) -> Text:
        style = STAGE_STYLE.get(step.stage, "")
        label = STAGE_LABEL.get(step.stage, step.stage.value)

        t = Text()
        t.append(f"  {step.elapsed:5.2f}s", style="dim #484f58")
        t.append("  ")
        t.append(f"{label:<12}", style=f"bold {style}")
        if step.detail:
            detail = step.detail if len(step.detail) <= 64 else step.detail[:61] + "..."
            t.append(detail, style="#8b949e")
        return t
