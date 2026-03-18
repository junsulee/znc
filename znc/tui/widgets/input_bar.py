"""
입력창 위젯 — /명령어 자동완성 포함.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Label, ListItem, ListView


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


class InputBar(Widget):
    """입력창 + /명령어 자동완성."""

    BINDINGS = [
        Binding("escape", "close_autocomplete", show=False),
        Binding("up", "autocomplete_up", show=False),
        Binding("down", "autocomplete_down", show=False),
        Binding("tab", "autocomplete_select", show=False),
    ]

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(self) -> None:
        super().__init__(id="input-bar")
        self._ac_visible = False
        self._ac_index = 0
        self._ac_items: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        yield Input(placeholder="> ", id="input-field")
        yield ListView(id="autocomplete")

    def on_mount(self) -> None:
        self.query_one("#autocomplete").display = False

    def focus_input(self) -> None:
        self.query_one("#input-field", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        val = event.value
        if val.startswith("/"):
            self._show_autocomplete(val)
        else:
            self._hide_autocomplete()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        if self._ac_visible:
            self._apply_autocomplete()
            return
        self._hide_autocomplete()
        self.query_one("#input-field", Input).value = ""
        self.post_message(self.Submitted(text))

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
                Label(f"[bold]{cmd}[/] [dim]{desc}[/]", markup=True),
                id=f"ac-{cmd.lstrip('/')}",
            ))
        lv.display = True
        self._ac_visible = True

    def _hide_autocomplete(self) -> None:
        self.query_one("#autocomplete").display = False
        self._ac_visible = False
        self._ac_items = []
        self._ac_index = 0

    def _apply_autocomplete(self) -> None:
        if not self._ac_items:
            return
        cmd, _ = self._ac_items[self._ac_index]
        self.query_one("#input-field", Input).value = cmd + " "
        self._hide_autocomplete()

    def action_close_autocomplete(self) -> None:
        self._hide_autocomplete()

    def action_autocomplete_up(self) -> None:
        if not self._ac_visible:
            return
        self._ac_index = max(0, self._ac_index - 1)
        self.query_one("#autocomplete", ListView).index = self._ac_index

    def action_autocomplete_down(self) -> None:
        if not self._ac_visible:
            return
        self._ac_index = min(len(self._ac_items) - 1, self._ac_index + 1)
        self.query_one("#autocomplete", ListView).index = self._ac_index

    def action_autocomplete_select(self) -> None:
        self._apply_autocomplete()
