"""
사이드바 위젯 — 프로젝트 목록 + 세션 목록.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView, Static

from znc.core.config import SESSIONS_DIR, ensure_dirs
from znc.core.models import Session
from znc.core.repository import ProjectRepository


class Sidebar(Widget):
    """왼쪽 사이드바: 프로젝트 + 세션 목록."""

    BINDINGS = [
        Binding("n", "new_session", "새 세션", show=False),
        Binding("p", "new_project", "새 프로젝트", show=False),
    ]

    class SessionSelected(Message):
        def __init__(self, name: str, project: str | None) -> None:
            super().__init__()
            self.name = name
            self.project = project

    class NewSessionRequested(Message):
        def __init__(self, project: str | None) -> None:
            super().__init__()
            self.project = project

    class NewProjectRequested(Message):
        pass

    def __init__(self) -> None:
        super().__init__(id="sidebar")
        self._current_project: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("znc", id="sidebar-title")
        yield Static("PROJECTS", classes="section-label")
        yield ListView(id="project-list")
        yield Static("SESSIONS", classes="section-label")
        yield ListView(id="session-list")
        yield Static("[n]ew  [p]roject  [/]search", id="sidebar-footer")

    def on_mount(self) -> None:
        self.refresh_lists()

    def refresh_lists(self) -> None:
        self._refresh_projects()
        self._refresh_sessions()

    def _refresh_projects(self) -> None:
        lv = self.query_one("#project-list", ListView)
        lv.clear()
        lv.append(ListItem(Label("[all]"), id="proj-__all__"))
        for proj in ProjectRepository.list_all():
            lv.append(ListItem(Label(proj.name), id=f"proj-{proj.name}"))

    def _refresh_sessions(self) -> None:
        lv = self.query_one("#session-list", ListView)
        lv.clear()
        ensure_dirs()
        if self._current_project:
            sessions_dir = ProjectRepository.sessions_dir(self._current_project)
        else:
            sessions_dir = SESSIONS_DIR
        for name in Session.list_names(sessions_dir):
            lv.append(ListItem(Label(name), id=f"sess-{name}"))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        item_id = event.item.id or ""
        if item_id.startswith("proj-"):
            project = None if item_id == "proj-__all__" else item_id[5:]
            self._current_project = project
            self._refresh_sessions()
        elif item_id.startswith("sess-"):
            name = item_id[5:]
            self.post_message(self.SessionSelected(name, self._current_project))

    def action_new_session(self) -> None:
        self.post_message(self.NewSessionRequested(self._current_project))

    def action_new_project(self) -> None:
        self.post_message(self.NewProjectRequested())
