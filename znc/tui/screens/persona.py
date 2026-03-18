"""
Persona 관리 팝업 스크린.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static, TextArea

from znc.core.persona import (
    FewShot, Persona,
    delete_persona, list_personas, load_persona,
)


class PersonaScreen(ModalScreen[str | None]):
    """Persona 관리 오버레이. 선택된 persona 이름을 dismiss 값으로 반환."""

    BINDINGS = [Binding("escape", "dismiss", "닫기")]

    DEFAULT_CSS = """
    PersonaScreen { align: center middle; }
    #persona-box {
        background: #161b22;
        border: tall #30363d;
        padding: 1 2;
        width: 70;
        height: 32;
    }
    .p-title  { color: #58a6ff; text-style: bold; height: 1; margin-bottom: 1; }
    .p-sep    { color: #30363d; height: 1; }
    .p-label  { color: #8b949e; height: 1; margin-top: 1; }
    .p-input  { background: #0d1117; border: tall #30363d; color: #e6edf3; margin-bottom: 0; }
    .p-input:focus { border: tall #58a6ff; }
    .p-textarea { background: #0d1117; border: tall #30363d; height: 5; margin-bottom: 0; }
    .p-textarea:focus { border: tall #58a6ff; }
    #persona-list { height: 6; background: #0d1117; border: tall #30363d; }
    .pr-row   { padding: 0 1; height: 1; color: #8b949e; }
    .pr-active { color: #3fb950; text-style: bold; }
    .btn-row  { align: center middle; height: 3; margin-top: 1; }
    #edit-section { height: auto; }
    """

    def __init__(self, active_persona: str = "default") -> None:
        super().__init__()
        self._active = active_persona
        self._editing: str | None = None

    def compose(self) -> ComposeResult:
        with Static(id="persona-box"):
            yield Label("persona", classes="p-title")
            yield Label("─" * 58, classes="p-sep")

            yield Label("saved personas", classes="p-label")
            yield ListView(id="persona-list")

            yield Label("─" * 58, classes="p-sep")
            yield Label("edit / create", classes="p-label")

            with Static(id="edit-section"):
                yield Label("name", classes="p-label")
                yield Input(id="p-name", classes="p-input")
                yield Label("description", classes="p-label")
                yield Input(id="p-desc", classes="p-input")
                yield Label("system prompt", classes="p-label")
                yield TextArea(id="p-system", classes="p-textarea")

            with Static(classes="btn-row"):
                yield Button("use",    id="btn-use",    variant="primary")
                yield Button("save",   id="btn-save")
                yield Button("delete", id="btn-delete", variant="error")
                yield Button("cancel", id="btn-cancel")

    def on_mount(self) -> None:
        self._refresh_list()

    def _refresh_list(self) -> None:
        lv = self.query_one("#persona-list", ListView)
        lv.clear()
        for p in list_personas():
            marker = "*" if p.name == self._active else " "
            label = Label(
                f"{marker} {p.name}  [{p.description}]",
                classes="pr-row" + (" pr-active" if p.name == self._active else ""),
            )
            lv.append(ListItem(label, id=f"pr-{p.name}"))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = (event.item.id or "")
        if item_id.startswith("pr-"):
            name = item_id[3:]
            self._editing = name
            p = load_persona(name)
            if p:
                self.query_one("#p-name", Input).value = p.name
                self.query_one("#p-desc", Input).value = p.description
                self.query_one("#p-system", TextArea).load_text(p.system_prompt)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-cancel":
            self.dismiss(None)
        elif bid == "btn-use":
            if self._editing:
                self._active = self._editing
            self.dismiss(self._active)
        elif bid == "btn-save":
            self._save_current()
        elif bid == "btn-delete":
            if self._editing and self._editing != "default":
                delete_persona(self._editing)
                self._editing = None
                self._refresh_list()

    def _save_current(self) -> None:
        name = self.query_one("#p-name", Input).value.strip()
        if not name:
            return
        desc = self.query_one("#p-desc", Input).value.strip()
        system = self.query_one("#p-system", TextArea).text
        p = Persona(name=name, description=desc, system_prompt=system)
        p.save()
        self._editing = name
        self._refresh_list()
