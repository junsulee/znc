"""
StatusBar — 스피너 + 단계 레이블 + shimmer 상태 바.

render() 직접 오버라이드 대신 내부 Static 위젯에 update() 를 사용.
Textual 0.80+ 에서 render() 직접 오버라이드는 렌더링이 불안정함.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Static

from znc.tui.animation import shimmer, SHIMMER_STAGES
from znc.tui.process_state import ProcessState, Stage, STAGE_STYLE

_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_ACTIVE_STAGES = {
    Stage.LOADING, Stage.MEMORY, Stage.SEARCH,
    Stage.CRAWL, Stage.THINKING, Stage.GENERATING,
}

_STAGE_LABEL: dict[str, dict[Stage, str]] = {
    "ko": {
        Stage.IDLE:       "",
        Stage.LOADING:    "준비 중",
        Stage.MEMORY:     "메모리",
        Stage.SEARCH:     "검색 중",
        Stage.CRAWL:      "크롤링",
        Stage.THINKING:   "생각 중",
        Stage.GENERATING: "생성 중",
        Stage.DONE:       "완료",
        Stage.ERROR:      "오류",
    },
    "en": {
        Stage.IDLE:       "",
        Stage.LOADING:    "preparing",
        Stage.MEMORY:     "memory",
        Stage.SEARCH:     "searching",
        Stage.CRAWL:      "crawling",
        Stage.THINKING:   "thinking",
        Stage.GENERATING: "generating",
        Stage.DONE:       "done",
        Stage.ERROR:      "error",
    },
}

_CRUMB_LABEL: dict[str, dict[Stage, str]] = {
    "ko": {
        Stage.LOADING: "준비", Stage.MEMORY: "메모리", Stage.SEARCH: "검색",
        Stage.CRAWL: "크롤", Stage.THINKING: "생각", Stage.GENERATING: "생성",
        Stage.DONE: "완료", Stage.ERROR: "오류",
    },
    "en": {
        Stage.LOADING: "prep", Stage.MEMORY: "mem", Stage.SEARCH: "search",
        Stage.CRAWL: "crawl", Stage.THINKING: "think", Stage.GENERATING: "gen",
        Stage.DONE: "done", Stage.ERROR: "err",
    },
}


class StatusBar(Widget):
    """1줄 상태 바 — 내부 Static 위젯 update() 방식."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: #0d1117;
        border-top: tall #21262d;
        padding: 0 1;
        color: #8b949e;
    }
    #_sb_content {
        height: 1fr;
        background: #0d1117;
        color: #8b949e;
    }
    """

    def __init__(self, process_state: ProcessState) -> None:
        super().__init__(id="status-bar")
        self._ps = process_state
        self._timer: Timer | None = None
        self._log_visible = False
        self._lang: str = "ko"
        self._tick: int = 0

    def compose(self) -> ComposeResult:
        yield Static("", id="_sb_content", markup=False)

    def on_mount(self) -> None:
        try:
            from znc.core.config import load_settings
            self._lang = load_settings().get("lang", "ko")
        except Exception:
            pass
        self._timer = self.set_interval(0.1, self._on_tick)

    def _on_tick(self) -> None:
        self._tick = (self._tick + 1) % len(_SPINNER)
        self._refresh_content()

    # ── 외부 API ───────────────────────────────────────────────
    def set_state(self, process_state: ProcessState) -> None:
        self._ps = process_state
        self._refresh_content()

    def set_log_visible(self, visible: bool) -> None:
        self._log_visible = visible
        self._refresh_content()

    def set_lang(self, lang: str) -> None:
        self._lang = lang
        self._refresh_content()

    def refresh(self, *args, **kwargs):
        self._refresh_content()
        return super().refresh(*args, **kwargs)

    # ── 내부 ──────────────────────────────────────────────────
    def _refresh_content(self) -> None:
        try:
            content = self._build_text()
            self.query_one("#_sb_content", Static).update(content)
        except Exception:
            pass

    def _build_text(self) -> Text:
        ps = self._ps
        stage = ps.stage
        lang = self._lang

        log_label = "[^L]▼" if not self._log_visible else "[^L]▲"

        if stage == Stage.IDLE:
            t = Text()
            t.append(log_label, style="dim #484f58")
            return t

        label = _STAGE_LABEL.get(lang, _STAGE_LABEL["en"]).get(stage, stage.value)
        style = STAGE_STYLE.get(stage, "#8b949e")
        active = stage in _ACTIVE_STAGES

        t = Text()

        # 스피너
        if active:
            t.append(_SPINNER[self._tick] + "  ", style=style)
        else:
            t.append("   ")

        # 단계 레이블 — 활성 단계는 shimmer, 완료/오류는 bold
        if label:
            if stage in SHIMMER_STAGES:
                t.append_text(shimmer(label, self._tick, style))
            else:
                t.append(label, style=f"bold {style}")

        # 세부 내용
        if ps.detail:
            detail = ps.detail[:50] + "..." if len(ps.detail) > 50 else ps.detail
            t.append(f"  {detail}", style="dim #8b949e")

        # 브레드크럼 (로그 닫혔을 때)
        if not self._log_visible and ps.steps:
            crumb_map = _CRUMB_LABEL.get(lang, _CRUMB_LABEL["en"])
            crumbs = [
                crumb_map[s.stage]
                for s in ps.steps
                if s.stage in crumb_map and crumb_map[s.stage]
            ]
            deduped: list[str] = []
            for c in crumbs:
                if not deduped or deduped[-1] != c:
                    deduped.append(c)
            if deduped:
                t.append(f"   {' → '.join(deduped[-4:])}", style="dim #484f58")

        # 경과 시간
        elapsed = f"{ps.total_elapsed:.1f}s"
        pad = max(1, 72 - len(t.plain) - len(elapsed))
        t.append(" " * pad)
        t.append(elapsed, style="dim #484f58")

        # 로그 토글 힌트
        t.append(f"  {log_label}", style="dim #484f58" if not self._log_visible else "#58a6ff")

        # 스트리밍 중 중단 힌트
        if stage in {Stage.THINKING, Stage.GENERATING, Stage.SEARCH, Stage.CRAWL}:
            t.append("  [Esc]stop", style="bold #f85149")

        return t
