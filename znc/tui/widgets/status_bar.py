"""
StatusBar — 레이어1.

스피너 옆에 현재 단계를 shimmer 애니메이션으로 표시.
언어 설정(ko/en)에 따라 단계 레이블 한/영 전환.

IDLE 상태에서도 [^L] 힌트를 표시해 상태 바가 항상 보임.
"""
from __future__ import annotations

from rich.text import Text
from textual.timer import Timer
from textual.widget import Widget

from znc.tui.animation import shimmer, SHIMMER_STAGES
from znc.tui.process_state import ProcessState, Stage, STAGE_STYLE

_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_ACTIVE_STAGES = {
    Stage.LOADING, Stage.MEMORY, Stage.SEARCH,
    Stage.CRAWL, Stage.THINKING, Stage.GENERATING,
}

# 단계 레이블: lang → Stage → label
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

# 브레드크럼 축약 레이블
_CRUMB_LABEL: dict[str, dict[Stage, str]] = {
    "ko": {
        Stage.LOADING:    "준비",
        Stage.MEMORY:     "메모리",
        Stage.SEARCH:     "검색",
        Stage.CRAWL:      "크롤",
        Stage.THINKING:   "생각",
        Stage.GENERATING: "생성",
        Stage.DONE:       "완료",
        Stage.ERROR:      "오류",
    },
    "en": {
        Stage.LOADING:    "prep",
        Stage.MEMORY:     "mem",
        Stage.SEARCH:     "search",
        Stage.CRAWL:      "crawl",
        Stage.THINKING:   "think",
        Stage.GENERATING: "gen",
        Stage.DONE:       "done",
        Stage.ERROR:      "err",
    },
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
        self._lang: str = "ko"

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.1, self._on_tick)
        # 설정에서 현재 언어 읽기
        try:
            from znc.core.config import load_settings
            self._lang = load_settings().get("lang", "ko")
        except Exception:
            pass

    def _on_tick(self) -> None:
        self._tick = (self._tick + 1) % len(_SPINNER)
        self.refresh()

    def set_state(self, process_state: ProcessState) -> None:
        self._ps = process_state
        self.refresh()

    def set_log_visible(self, visible: bool) -> None:
        self._log_visible = visible
        self.refresh()

    def set_lang(self, lang: str) -> None:
        self._lang = lang
        self.refresh()

    def render(self) -> Text:
        ps = self._ps
        stage = ps.stage
        lang = self._lang

        log_marker = (
            "[dim #484f58][^L]▼[/]"
            if not self._log_visible
            else "[#58a6ff][^L]▲[/]"
        )

        # IDLE: 힌트만 표시
        if stage == Stage.IDLE:
            t = Text()
            t.append_text(Text.from_markup(log_marker))
            return t

        label = _STAGE_LABEL.get(lang, _STAGE_LABEL["en"]).get(stage, stage.value)
        style = STAGE_STYLE.get(stage, "")
        active = stage in _ACTIVE_STAGES

        t = Text()

        # 스피너
        if active:
            t.append(_SPINNER[self._tick] + "  ", style=style)
        else:
            t.append("   ")

        # 단계 레이블 — 활성이면 shimmer, 완료/오류는 정적
        # shimmer 는 가장 어두운 글자도 dim base_style 로 항상 가시
        if stage in SHIMMER_STAGES:
            shim = shimmer(label, self._tick, style)
            if shim.plain:
                t.append_text(shim)
            else:
                t.append(label, style=f"bold {style}")
        else:
            t.append(label, style=f"bold {style}")

        # 세부 내용
        if ps.detail:
            detail = ps.detail[:55] + "..." if len(ps.detail) > 55 else ps.detail
            t.append(f"  {detail}", style="#484f58")

        # 브레드크럼: 로그 패널 닫혀있을 때 최근 단계 요약
        if not self._log_visible and ps.steps:
            crumb_map = _CRUMB_LABEL.get(lang, _CRUMB_LABEL["en"])
            crumbs = [
                crumb_map.get(s.stage, "")
                for s in ps.steps
                if s.stage not in {Stage.IDLE} and crumb_map.get(s.stage)
            ]
            deduped: list[str] = []
            for c in crumbs:
                if not deduped or deduped[-1] != c:
                    deduped.append(c)
            if deduped:
                crumb_str = " → ".join(deduped[-4:])
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
