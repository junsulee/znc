"""
입력창 위젯 — /명령어 자동완성 포함.

한글 입력 처리:
  - on_input_changed: NFC 정규화 후 값 교체 (_normalizing 플래그로 재귀 방지)
  - on_input_submitted: 제출 직전 NFC + 중복 자모 제거
  - 자동완성 ListView: clear()+append() 대신 remove()+mount() 패턴 사용
    (Textual 비동기 clear() 의 DuplicateIds 경쟁조건 방지)
"""
from __future__ import annotations

import unicodedata

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Label, ListItem, ListView

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


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _sanitize(text: str) -> str:
    """NFC 정규화 + IME ghost 제거."""
    return sanitize_korean(text)


class InputBar(Widget):
    """입력창 + /명령어 자동완성."""

    BINDINGS = [
        Binding("escape", "close_autocomplete", show=False),
        Binding("up",     "autocomplete_up",    show=False),
        Binding("down",   "autocomplete_down",  show=False),
        Binding("tab",    "autocomplete_select", show=False),
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
        self._normalizing = False   # NFC 재귀 방지 플래그

    def compose(self) -> ComposeResult:
        yield Input(placeholder="> ", id="input-field")
        yield ListView(id="autocomplete")

    def on_mount(self) -> None:
        self.query_one("#autocomplete").display = False

    def focus_input(self) -> None:
        self.query_one("#input-field", Input).focus()

    # ── 한글 NFC 정규화 (입력 중 실시간) ──────────────────────────
    def on_input_changed(self, event: Input.Changed) -> None:
        if self._normalizing:
            # 값 교체로 인한 재귀 호출 — 자동완성만 처리
            val = event.value
            if val.startswith("/"):
                self._show_autocomplete(val)
            else:
                self._hide_autocomplete()
            return

        val = event.value
        sanitized = _sanitize(val)

        if sanitized != val:
            # NFC 정규화 또는 중복 자모 제거가 필요한 경우 값 교체
            self._normalizing = True
            try:
                inp = self.query_one("#input-field", Input)
                # 커서 위치를 비율로 유지 (조합으로 길이가 달라질 수 있음)
                old_pos = inp.cursor_position
                inp.value = sanitized
                new_pos = min(old_pos, len(sanitized))
                inp.cursor_position = new_pos
            finally:
                self._normalizing = False
            # on_input_changed 가 sanitized 값으로 다시 호출되므로 여기서 return
            return

        if val.startswith("/"):
            self._show_autocomplete(val)
        else:
            self._hide_autocomplete()

    # ── 제출 (Enter) ───────────────────────────────────────────────
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._ac_visible:
            self._apply_autocomplete()
            return
        self._hide_autocomplete()

        # 제출 직전 한 번 더 정규화 (on_input_changed 가 놓친 경우 대비)
        text = _sanitize(event.value.strip())
        if not text:
            return

        self.query_one("#input-field", Input).value = ""
        self.post_message(self.Submitted(text))

    # ── 자동완성 (clear+append 패턴 — ListItem에 ID 없음) ────────────
    def _show_autocomplete(self, val: str) -> None:
        prefix = val.lower()
        matches = [(cmd, desc) for cmd, desc in SLASH_COMMANDS if cmd.startswith(prefix)]
        if not matches:
            self._hide_autocomplete()
            return

        self._ac_items = matches
        self._ac_index = 0

        # 기존 ListView 를 재사용하고 clear()+append() 로 내용만 교체.
        # remove()+mount() 는 remove() 가 비동기라 구 위젯 제거 전에
        # id='autocomplete' 를 가진 신 위젯이 등록되어 DuplicateIds 발생.
        # ListItem 에 ID 를 부여하지 않으면 _ensure_unique_id 를 건너뛰므로 안전.
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
            lv = self.query_one("#autocomplete", ListView)
            lv.display = False
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

    # ── Actions ───────────────────────────────────────────────────
    def action_close_autocomplete(self) -> None:
        self._hide_autocomplete()

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
