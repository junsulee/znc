"""
새 프로젝트 생성 팝업.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, TextArea

from znc.core.repository import ProjectRepository


class NewProjectScreen(ModalScreen[str | None]):
    """새 프로젝트 생성. 생성된 이름 또는 None 반환."""

    BINDINGS = [Binding("escape", "dismiss", "닫기")]

    DEFAULT_CSS = """
    NewProjectScreen { align: center middle; }
    #np-box {
        background: #161b22;
        border: tall #30363d;
        padding: 1 2;
        width: 58;
        height: auto;
    }
    .np-title  { color: #58a6ff; text-style: bold; height: 1; margin-bottom: 1; }
    .np-sep    { color: #30363d; height: 1; }
    .np-label  { color: #8b949e; height: 1; margin-top: 1; }
    .np-input  { background: #0d1117; border: tall #30363d; color: #e6edf3; }
    .np-input:focus { border: tall #58a6ff; }
    .np-area   { background: #0d1117; border: tall #30363d; height: 5; }
    .np-area:focus { border: tall #58a6ff; }
    .btn-row   { align: center middle; height: 3; margin-top: 1; }
    .np-error  { color: #f85149; height: 1; }
    """

    def compose(self) -> ComposeResult:
        with Static(id="np-box"):
            yield Label("new project", classes="np-title")
            yield Label("─" * 46, classes="np-sep")
            yield Label("name", classes="np-label")
            yield Input(id="np-name", classes="np-input")
            yield Label("description", classes="np-label")
            yield Input(id="np-desc", classes="np-input")
            yield Label("system prompt (optional)", classes="np-label")
            yield TextArea(id="np-system", classes="np-area")
            yield Label("", id="np-error", classes="np-error")
            with Static(classes="btn-row"):
                yield Button("create", id="btn-create", variant="primary")
                yield Button("cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
            return
        name = self.query_one("#np-name", Input).value.strip()
        if not name:
            self.query_one("#np-error", Label).update("name is required")
            return
        if ProjectRepository.get(name):
            self.query_one("#np-error", Label).update(f"project '{name}' already exists")
            return
        desc = self.query_one("#np-desc", Input).value.strip()
        system = self.query_one("#np-system", TextArea).text.strip()
        ProjectRepository.create(name, description=desc, system_prompt=system)
        self.dismiss(name)
