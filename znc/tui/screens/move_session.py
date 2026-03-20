"""
세션 이동 팝업 — 세션을 다른 프로젝트로 이동하거나 전역으로 꺼냄.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListItem, ListView, Static

from znc.core.i18n import ui as _ui
from znc.core.repository import ProjectRepository


class MoveSessionScreen(ModalScreen[str | None]):
    """세션 이동. 이동 대상 project 이름 반환 (빈 문자열 = 전역, None = 취소)."""

    BINDINGS = [Binding("escape", "dismiss", "닫기")]

    DEFAULT_CSS = """
    MoveSessionScreen { align: center middle; }
    #move-box {
        background: #161b22;
        border: tall #30363d;
        padding: 1 2;
        width: 52;
        height: auto;
        max-height: 28;
    }
    .mv-title  { color: #58a6ff; text-style: bold; height: 1; margin-bottom: 1; }
    .mv-sep    { color: #30363d; height: 1; margin: 1 0; }
    .mv-sub    { color: #8b949e; height: 1; margin-top: 1; }
    #dest-list { height: auto; max-height: 12; background: #0d1117; border: tall #30363d; }
    .dest-row  { padding: 0 1; height: 1; color: #8b949e; }
    .dest-row.--current { color: #484f58; }
    .btn-row   { align: center middle; height: 3; margin-top: 1; }
    """

    def __init__(self, session_name: str, current_project: str | None, lang: str = "ko") -> None:
        super().__init__()
        self._session_name = session_name
        self._current_project = current_project
        self._lang = lang
        self._dest: str | None = None   # 선택된 목적지 project 이름 (빈 문자열=전역)

    def compose(self) -> ComposeResult:
        L = self._lang
        with Static(id="move-box"):
            yield Label(_ui(L, "move_session_title"), classes="mv-title")
            yield Label(f'  {self._session_name}', classes="mv-sub", markup=False)
            yield Label("─" * 42, classes="mv-sep")
            yield Label(_ui(L, "move_dest_label"), classes="mv-sub")
            yield ListView(id="dest-list")
            with Static(classes="btn-row"):
                yield Button(_ui(L, "btn_move"),   id="btn-move",   variant="primary")
                yield Button(_ui(L, "btn_cancel"), id="btn-cancel")

    def on_mount(self) -> None:
        lv = self.query_one("#dest-list", ListView)
        L = self._lang
        # 전역(inbox)
        cls = "dest-row--current" if self._current_project is None else "dest-row"
        lv.append(ListItem(Label(f"  {_ui(L, 'move_global')}", markup=False, classes=cls)))
        # 각 프로젝트
        for proj in ProjectRepository.list_all():
            cls2 = "dest-row --current" if proj.name == self._current_project else "dest-row"
            lv.append(ListItem(Label(f"  > {proj.name}", markup=False, classes=cls2)))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        idx = event.list_view.index
        if idx is None:
            return
        if idx == 0:
            self._dest = ""   # 전역
        else:
            projects = ProjectRepository.list_all()
            if idx - 1 < len(projects):
                self._dest = projects[idx - 1].name

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        # Enter 로 선택 → 즉시 이동
        if self._dest is not None:
            self._do_move()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-move":
            self._do_move()

    def _do_move(self) -> None:
        if self._dest is None:
            return
        # 현재 위치와 같은 곳으로 이동 시 취소
        current = self._current_project or ""
        if self._dest == current:
            self.dismiss(None)
            return
        self.dismiss(self._dest)
