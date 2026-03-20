"""
ProcessLog — 레이어2.

Ctrl+L 로 토글하는 슬라이딩 패널.
활성 단계의 레이블에 Cursor 스타일 shimmer 애니메이션 적용.
완료된 단계는 정적으로 표시.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import RichLog

from znc.tui.animation import shimmer, SHIMMER_STAGES
from znc.tui.process_state import ProcessState, Stage, STAGE_LABEL, STAGE_STYLE

_PANEL_HEIGHT = 10


class ProcessLog(Widget):
    """단계 타임라인 슬라이딩 패널."""

    DEFAULT_CSS = """
    ProcessLog {
        height: 0;
        background: #0d1117;
        overflow-y: hidden;
    }
    ProcessLog.--visible {
        height: 10;
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
        self._anim_tick: int = 0
        self._anim_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield RichLog(id="proc-log", wrap=False, highlight=False, markup=False)

    # ── Public API ─────────────────────────────────────────────
    def show(self) -> None:
        self.add_class("--visible")
        self._redraw()
        self._maybe_start_anim()

    def hide(self) -> None:
        self.remove_class("--visible")
        self._stop_anim()

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
        if "--visible" in self.classes:
            self._redraw()
        self._maybe_start_anim()

    def refresh_last_step(self) -> None:
        if "--visible" in self.classes:
            self._redraw()

    # ── 애니메이션 ─────────────────────────────────────────────
    def _maybe_start_anim(self) -> None:
        if self._ps.stage in SHIMMER_STAGES and "--visible" in self.classes:
            if self._anim_timer is None:
                self._anim_timer = self.set_interval(0.08, self._on_anim_tick)
        else:
            self._stop_anim()

    def _stop_anim(self) -> None:
        if self._anim_timer is not None:
            self._anim_timer.stop()
            self._anim_timer = None

    def _on_anim_tick(self) -> None:
        self._anim_tick += 1
        if self._ps.stage not in SHIMMER_STAGES:
            self._stop_anim()
            self._redraw()  # 최종 정적 렌더
        elif "--visible" in self.classes:
            self._redraw()

    # ── Internal ────────────────────────────────────────────────
    def _redraw(self) -> None:
        log = self.query_one("#proc-log", RichLog)
        log.clear()
        n = len(self._ps.steps)
        active_stage = self._ps.stage
        for i, step in enumerate(self._ps.steps):
            is_last = i == n - 1
            is_active = is_last and step.stage in SHIMMER_STAGES and step.stage == active_stage
            log.write(self._format_step(step, is_active))

    def _format_step(self, step, is_active: bool = False) -> Text:
        style = STAGE_STYLE.get(step.stage, "")
        label = STAGE_LABEL.get(step.stage, step.stage.value)

        t = Text()
        t.append(f"  {step.elapsed:5.2f}s", style="dim #484f58")
        t.append("  ")

        # 레이블: 활성 스텝은 shimmer, 완료 스텝은 정적
        if is_active:
            t.append_text(shimmer(f"{label:<12}", self._anim_tick, style))
        else:
            t.append(f"{label:<12}", style=f"bold {style}")

        if step.detail:
            detail = step.detail if len(step.detail) <= 60 else step.detail[:57] + "..."
            t.append(detail, style="#8b949e")

        # sub_items (Cursor 스타일 세부 항목)
        for sub in step.sub_items:
            t.append(f"\n          ▸ ", style="dim #484f58")
            t.append(sub[:72] if len(sub) > 72 else sub, style="dim #8b949e")

        return t
