"""
ProcessLog — 레이어2.

Ctrl+L 로 토글하는 슬라이딩 패널.
기본 접힘(height:0), 열면 CSS transition 으로 부드럽게 슬라이드인.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import RichLog

from znc.tui.process_state import ProcessState, Stage, STAGE_LABEL, STAGE_STYLE

_PANEL_HEIGHT = 7


class ProcessLog(Widget):
    """단계 타임라인 슬라이딩 패널."""

    DEFAULT_CSS = """
    ProcessLog {
        height: 0;
        background: #0d1117;
        overflow-y: hidden;
    }
    ProcessLog.--visible {
        height: 7;
    }
    #proc-log {
        background: #0d1117;
        padding: 0 1;
        scrollbar-background: #0d1117;
        scrollbar-color: #21262d;
    }
    """

    def __init__(self, process_state: ProcessState) -> None:
        super().__init__(id="process-log")
        self._ps = process_state

    def compose(self) -> ComposeResult:
        yield RichLog(id="proc-log", wrap=False, highlight=False, markup=False)

    # ── Public API ─────────────────────────────────────────────
    def show(self) -> None:
        self.add_class("--visible")
        self._redraw()

    def hide(self) -> None:
        self.remove_class("--visible")

    def toggle(self) -> bool:
        if "--visible" in self.classes:
            self.hide()
            return False
        self.show()
        return True

    def set_state(self, process_state: ProcessState) -> None:
        self._ps = process_state
        if "--visible" in self.classes:
            self._redraw()

    def append_step(self) -> None:
        if "--visible" in self.classes and self._ps.steps:
            log = self.query_one("#proc-log", RichLog)
            log.write(self._format_step(self._ps.steps[-1]))

    # ── Internal ────────────────────────────────────────────────
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
            detail = step.detail if len(step.detail) <= 60 else step.detail[:57] + "..."
            t.append(detail, style="#8b949e")
        return t
