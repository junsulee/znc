"""
세션 삭제 확인 팝업.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class ConfirmScreen(ModalScreen[bool]):
    """단순 확인/취소 팝업. True(확인) 또는 False(취소)를 dismiss 값으로 반환."""

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("enter",  "confirm", show=False),
    ]

    DEFAULT_CSS = """
    ConfirmScreen { align: center middle; }
    #confirm-box {
        background: #161b22;
        border: tall #f85149;
        padding: 1 2;
        width: 52;
        height: auto;
    }
    .cf-title  { color: #f85149; text-style: bold; height: 1; margin-bottom: 1; }
    .cf-msg    { color: #e6edf3; margin-bottom: 1; }
    .cf-hint   { color: #484f58; height: 1; }
    .btn-row   { align: center middle; height: 3; margin-top: 1; }
    """

    def __init__(self, message: str, title: str = "확인") -> None:
        super().__init__()
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Static(id="confirm-box"):
            yield Label(self._title, classes="cf-title")
            yield Label(self._message, classes="cf-msg")
            yield Label("Enter 확인  /  Esc 취소", classes="cf-hint")
            with Static(classes="btn-row"):
                yield Button("삭제", id="btn-yes", variant="error")
                yield Button("취소", id="btn-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-yes")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
