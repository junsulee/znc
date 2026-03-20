"""
입력창 위젯 — /명령어 자동완성 + 전송/중단 버튼.

스트리밍 상태에 따라 버튼이 전환된다:
  대기 중: [▲]  클릭 = 전송 (Enter 와 동일)
  생성 중: [■]  클릭 = 스트리밍 중단 (Esc 와 동일)
"""
from __future__ import annotations

import unicodedata

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Label, ListItem, ListView

from znc.core.text_utils import sanitize_korean


SLASH_COMMANDS = [
    ("/search",   "<query>   웹 검색 후 결과 컨텍스트 삽입"),
    ("/remember", "<text>    기억 저장"),
    ("/forget",   "<key>     기억 삭제"),
    ("/persona",  "<name>    페르소나 전환"),
    ("/clear",    "          현재 대화 초기화"),
    ("/save",     "<name>    현재 세션 저장"),
    ("/export",   "<file>    세션 텍스트 내보내기"),
    ("/memory",   "          메모리 관리 팝업"),
    ("/settings", "          설정 팝업"),
]


def _sanitize(text: str) -> str:
    return sanitize_korean(text)


class InputBar(Widget):
    """입력창 + 전송/중단 버튼 + /명령어 자동완성."""

    BINDINGS = [
        Binding("up",  "autocomplete_up",    show=False),
        Binding("down","autocomplete_down",  show=False),
        Binding("tab", "autocomplete_select", show=False),
    ]

    # 스트리밍 중이면 True — 버튼이 ■ Stop 으로 전환
    streaming: reactive[bool] = reactive(False)

    # ── Messages ─────────────────────────────────────────────
    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class StopRequested(Message):
        """스트리밍 중단 요청."""

    # ── Init ─────────────────────────────────────────────────
    def __init__(self) -> None:
        super().__init__(id="input-bar")
        self._ac_visible = False
        self._ac_index = 0
        self._ac_items: list[tuple[str, str]] = []
        self._normalizing = False

    # ── Layout ───────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        with Horizontal(id="input-row"):
            yield Input(placeholder="> ", id="input-field")
            yield Button("▲", id="action-btn", classes="--send")
        yield ListView(id="autocomplete")

    def on_mount(self) -> None:
        self.query_one("#autocomplete").display = False

    def focus_input(self) -> None:
        self.query_one("#input-field", Input).focus()

    # ── Streaming 상태 변화 → 버튼 전환 ──────────────────────
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

    # ── 버튼 클릭 ────────────────────────────────────────────
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "action-btn":
            return
        if self.streaming:
            self.post_message(self.StopRequested())
        else:
            self._submit_current()

    # ── 한글 NFC 정규화 ───────────────────────────────────────
    def on_input_changed(self, event: Input.Changed) -> None:
        if self._normalizing:
            val = event.value
            if val.startswith("/"):
                self._show_autocomplete(val)
            else:
                self._hide_autocomplete()
            return

        val = event.value
        sanitized = _sanitize(val)

        if sanitized != val:
            self._normalizing = True
            try:
                inp = self.query_one("#input-field", Input)
                old_pos = inp.cursor_position
                inp.value = sanitized
                inp.cursor_position = min(old_pos, len(sanitized))
            finally:
                self._normalizing = False
            return

        if val.startswith("/"):
            self._show_autocomplete(val)
        else:
            self._hide_autocomplete()

    # ── Enter 제출 ────────────────────────────────────────────
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._ac_visible:
            self._apply_autocomplete()
            return
        self._hide_autocomplete()
        self._submit_current_from_value(event.value)

    def _submit_current(self) -> None:
        inp = self.query_one("#input-field", Input)
        self._submit_current_from_value(inp.value)

    def _submit_current_from_value(self, raw: str) -> None:
        text = _sanitize(raw.strip())
        if not text:
            return
        self.query_one("#input-field", Input).value = ""
        self.post_message(self.Submitted(text))

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
