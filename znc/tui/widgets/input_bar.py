"""
입력창 위젯 — 다중 줄 + /명령어 자동완성 + 전송/중단 버튼.

키 동작:
  Enter        → 전송 (단일·다중 줄 공통)
  Ctrl+Enter   → 줄바꿈 삽입
  ▲ 버튼       → 전송
  ■ 버튼       → 스트리밍 중단 (streaming=True 시)
"""
from __future__ import annotations

import unicodedata

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Label, ListItem, ListView, TextArea

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


class ChatInput(TextArea):
    """다중 줄 지원 채팅 입력창.

    Enter        → Submitted 메시지 발행 (전송)
    Ctrl+Enter   → 줄바꿈 삽입
    """

    BINDINGS = [
        Binding("enter",       "submit_text",  priority=True, show=False),
        Binding("shift+enter", "newline_text", priority=True, show=False),
        Binding("ctrl+enter",  "newline_text", priority=True, show=False),
        Binding("meta+enter",  "newline_text", priority=True, show=False),  # Alt+Enter
    ]

    DEFAULT_CSS = """
    ChatInput {
        background: #0d1117;
        border: none;
        color: #e6edf3;
        padding: 0 1;
        height: auto;
        max-height: 7;
    }
    ChatInput .text-area--cursor-line {
        background: #1c2128;
    }
    ChatInput .text-area--gutter {
        display: none;
        width: 0;
    }
    ChatInput:focus {
        border: none;
    }
    """

    class Submitted(Message):
        pass

    def action_submit_text(self) -> None:
        self.post_message(self.Submitted())

    def action_newline_text(self) -> None:
        self.insert("\n")


class InputBar(Widget):
    """입력창 컨테이너."""

    BINDINGS = [
        Binding("up",  "autocomplete_up",     show=False),
        Binding("down","autocomplete_down",   show=False),
        Binding("tab", "autocomplete_select", show=False),
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

    def compose(self) -> ComposeResult:
        with Horizontal(id="input-row"):
            yield ChatInput(
                id="input-field",
                language=None,
                show_line_numbers=False,
                soft_wrap=True,
            )
            yield Button("↵", id="newline-btn", classes="newline-btn")
            yield Button("▲", id="action-btn", classes="--send")
        yield ListView(id="autocomplete")

    def on_mount(self) -> None:
        self.query_one("#autocomplete").display = False

    def focus_input(self) -> None:
        self.query_one("#input-field", ChatInput).focus()

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
        if event.button.id == "newline-btn":
            ta = self.query_one("#input-field", ChatInput)
            ta.insert("\n")
            ta.focus()
            return
        if event.button.id != "action-btn":
            return
        if self.streaming:
            self.post_message(self.StopRequested())
        else:
            self._submit_current()

    # ── Enter 전송 (ChatInput.Submitted) ─────────────────────
    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        event.stop()
        if self._ac_visible:
            self._apply_autocomplete()
            return
        self._hide_autocomplete()
        self._submit_current()

    def _submit_current(self) -> None:
        ta = self.query_one("#input-field", ChatInput)
        text = sanitize_korean(ta.text.strip())
        if not text:
            return
        ta.clear()
        self.post_message(self.Submitted(text))

    # ── 텍스트 변경 → 자동완성 체크 ──────────────────────────
    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        text = event.text_area.text
        # 단일 줄 + /로 시작할 때만 자동완성
        if "\n" not in text and text.startswith("/"):
            self._show_autocomplete(text)
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
        ta = self.query_one("#input-field", ChatInput)
        ta.clear()
        ta.insert(cmd + " ")
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
