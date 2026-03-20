"""
입력창 위젯 — Input 위젯 기반 (한국어 IME 호환성 최대화).

TextArea 는 Textual 내부에서 모든 키를 raw 처리하므로
시스템 IME 조합 과정과 충돌해 한국어가 깨진다.
Input 위젯은 터미널 IME 와 호환성이 훨씬 높다.

다중 줄 지원:
  이전 줄들을 별도 Static 에 표시하고 Input 에서 현재 줄 입력.
  Shift+Enter / Ctrl+Enter / Alt+Enter → 현재 줄을 버퍼에 추가
  Enter → 버퍼 + 현재 줄 합쳐서 제출
  ↵ 버튼 → 줄바꿈 (Shift/Ctrl+Enter 안 되는 터미널용 fallback)
"""
from __future__ import annotations

import unicodedata

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from znc.core.text_utils import sanitize_korean


SLASH_COMMANDS = [
    ("/search",   "<query>   웹 검색 후 결과 컨텍스트 삽입"),
    ("/remember", "<text>    기억 저장"),
    ("/forget",   "<key>     기억 삭제"),
    ("/persona",  "<name>    페르소나 전환"),
    ("/clear",    "          현재 대화 초기화"),
    ("/save",     "<name>    현재 세션 저장"),
    ("/export",   "<file>    세션 텍스트 내보내기"),
    ("/save-msg", "          메시지 선택 → 파일 저장"),
    ("/memory",   "          메모리 관리 팝업"),
    ("/settings", "          설정 팝업"),
]


def _sanitize(text: str) -> str:
    """제출 시점 최종 정리 — NFC + case1/2 ghost 제거."""
    return sanitize_korean(text)


class InputBar(Widget):
    """입력창 — Input 기반 다중 줄 지원."""

    BINDINGS = [
        Binding("shift+enter", "newline",           priority=True, show=False),
        Binding("ctrl+enter",  "newline",           priority=True, show=False),
        Binding("meta+enter",  "newline",           priority=True, show=False),
        Binding("up",          "autocomplete_up",   show=False),
        Binding("down",        "autocomplete_down", show=False),
        Binding("tab",         "autocomplete_select", show=False),
    ]

    streaming: reactive[bool] = reactive(False)

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class StopRequested(Message):
        pass

    def __init__(self) -> None:
        super().__init__(id="input-bar")
        self._ac_visible = False
        self._ac_index = 0
        self._ac_items: list[tuple[str, str]] = []
        self._prev_lines: list[str] = []   # 누적된 이전 줄들

    def compose(self) -> ComposeResult:
        yield Static("", id="multiline-preview")
        with Horizontal(id="input-row"):
            yield Input(placeholder="> ", id="input-field")
            yield Button("↵", id="newline-btn", classes="newline-btn")
            yield Button("▲", id="action-btn", classes="--send")
        yield ListView(id="autocomplete")

    def on_mount(self) -> None:
        self.query_one("#autocomplete").display = False
        self.query_one("#multiline-preview").display = False

    def focus_input(self) -> None:
        self.query_one("#input-field", Input).focus()

    # ── 스트리밍 상태 → 버튼 전환 ────────────────────────────
    def watch_streaming(self, value: bool) -> None:
        try:
            btn = self.query_one("#action-btn", Button)
            if value:
                btn.label = "■"
                btn.add_class("--stop")
                btn.remove_class("--send")
            else:
                btn.label = "▲"
                btn.remove_class("--stop")
                btn.add_class("--send")
        except Exception:
            pass

    # ── 버튼 클릭 ─────────────────────────────────────────────
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "newline-btn":
            self._add_line()
        elif bid == "action-btn":
            if self.streaming:
                self.post_message(self.StopRequested())
            else:
                self._submit_current()

    # ── 줄바꿈 (Shift/Ctrl/Alt+Enter, ↵ 버튼) ────────────────
    def action_newline(self) -> None:
        self._add_line()

    def _add_line(self) -> None:
        inp = self.query_one("#input-field", Input)
        current = inp.value
        # 빈 줄도 허용 (의도적 빈 줄 삽입)
        self._prev_lines.append(current)
        inp.value = ""
        self._update_preview()

    def _update_preview(self) -> None:
        preview = self.query_one("#multiline-preview", Static)
        if self._prev_lines:
            lines = "\n".join(
                f"  {l}" if l else ""
                for l in self._prev_lines
            )
            preview.update(lines)
            preview.display = True
        else:
            preview.display = False

    # ── Enter 제출 ────────────────────────────────────────────
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._ac_visible:
            self._apply_autocomplete()
            return
        self._hide_autocomplete()
        self._submit_current()

    def _submit_current(self) -> None:
        inp = self.query_one("#input-field", Input)
        current = inp.value
        all_lines = self._prev_lines + [current]
        # 최소 한 줄 이상 내용 있어야 제출
        full_raw = "\n".join(all_lines)
        text = _sanitize(full_raw.strip())
        if not text:
            return
        inp.value = ""
        self._prev_lines = []
        self._update_preview()
        self.post_message(self.Submitted(text))

    # ── 입력 변경 → 자동완성 (NFC는 제출 시에만) ─────────────
    def on_input_changed(self, event: Input.Changed) -> None:
        val = event.value
        # 단일 줄에서 /로 시작할 때만 자동완성
        if not self._prev_lines and val.startswith("/"):
            self._show_autocomplete(val)
        else:
            self._hide_autocomplete()

    # ── 자동완성 ──────────────────────────────────────────────
    def _show_autocomplete(self, val: str) -> None:
        prefix = val.lower()
        matches = [(cmd, desc) for cmd, desc in SLASH_COMMANDS if cmd.startswith(prefix)]
        if not matches:
            self._hide_autocomplete()
            return
        self._ac_items = matches
        self._ac_index = 0
        lv = self.query_one("#autocomplete", ListView)
        lv.clear()
        for cmd, desc in matches:
            lv.append(ListItem(
                Label(f"[bold]{cmd}[/] [dim]{desc}[/]", markup=True)
            ))
        lv.display = True
        self._ac_visible = True

    def _hide_autocomplete(self) -> None:
        try:
            self.query_one("#autocomplete", ListView).display = False
        except Exception:
            pass
        self._ac_visible = False
        self._ac_items = []
        self._ac_index = 0

    def _apply_autocomplete(self) -> None:
        if not self._ac_items:
            return
        cmd, _ = self._ac_items[self._ac_index]
        self.query_one("#input-field", Input).value = cmd + " "
        self._hide_autocomplete()

    # ── Actions ───────────────────────────────────────────────
    def action_autocomplete_up(self) -> None:
        if not self._ac_visible:
            return
        self._ac_index = max(0, self._ac_index - 1)
        try:
            self.query_one("#autocomplete", ListView).index = self._ac_index
        except Exception:
            pass

    def action_autocomplete_down(self) -> None:
        if not self._ac_visible:
            return
        self._ac_index = min(len(self._ac_items) - 1, self._ac_index + 1)
        try:
            self.query_one("#autocomplete", ListView).index = self._ac_index
        except Exception:
            pass

    def action_autocomplete_select(self) -> None:
        self._apply_autocomplete()
