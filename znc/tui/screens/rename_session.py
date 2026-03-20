"""세션/프로젝트 이름 변경 팝업 — i18n 적용."""
from __future__ import annotations
import re
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static
from znc.core.config import load_settings
from znc.core.i18n import ui as _ui


class RenameSessionScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "dismiss", "닫기")]

    DEFAULT_CSS = """
    RenameSessionScreen { align: center middle; }
    #rename-box {
        background: #161b22;
        border: tall #30363d;
        padding: 1 2;
        width: 52;
        height: auto;
    }
    .rn-title  { color: #58a6ff; text-style: bold; height: 1; margin-bottom: 1; }
    .rn-label  { color: #8b949e; height: 1; margin-top: 1; }
    .rn-input  { background: #0d1117; border: tall #30363d; color: #e6edf3; }
    .rn-input:focus { border: tall #58a6ff; }
    .rn-error  { color: #f85149; height: 1; }
    .btn-row   { align: center middle; height: 3; margin-top: 1; }
    """

    def __init__(self, current_name: str) -> None:
        super().__init__()
        self._current = current_name
        self._lang = load_settings().get("lang", "ko")

    def compose(self) -> ComposeResult:
        L = self._lang
        with Static(id="rename-box"):
            yield Label(_ui(L, "rename_title"), classes="rn-title")
            yield Label(_ui(L, "rename_current", name=self._current), classes="rn-label")
            yield Label(_ui(L, "rename_new"), classes="rn-label")
            yield Input(value=self._current, id="rn-input", classes="rn-input")
            yield Label("", id="rn-error", classes="rn-error")
            with Static(classes="btn-row"):
                yield Button(_ui(L, "btn_rename"),  id="btn-ok",     variant="primary")
                yield Button(_ui(L, "btn_cancel"),  id="btn-cancel")

    def on_mount(self) -> None:
        inp = self.query_one("#rn-input", Input)
        inp.focus()
        inp.cursor_position = len(inp.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        else:
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        name = self.query_one("#rn-input", Input).value.strip()
        if not name:
            self.query_one("#rn-error", Label).update(
                _ui(self._lang, "np_error_required")
            )
            return
        # 파일명 안전화 (표시 제목이므로 제한 완화)
        self.dismiss(name)
