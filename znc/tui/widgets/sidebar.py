"""
사이드바 위젯 — 프로젝트 목록 + 세션 목록.

단축키 (사이드바 포커스 시):
  n     새 세션
  t     임시 채팅
  p     새 프로젝트
  /     세션 검색 (인라인 필터)
  d     선택 세션 삭제
  r     선택 세션 이름 변경
  Esc   검색 취소 / 포커스 해제
"""
from __future__ import annotations

import os

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Label, ListItem, ListView, Static

from znc.core.config import SESSIONS_DIR, ensure_dirs
from znc.core.models import Session
from znc.core.repository import ProjectRepository


class Sidebar(Widget):
    """왼쪽 사이드바: 프로젝트 + 세션 목록."""

    BINDINGS = [
        Binding("n",      "new_session",   "new",    show=False),
        Binding("t",      "temp_session",  "temp",   show=False),
        Binding("p",      "new_project",   "project",show=False),
        Binding("slash",  "focus_search",  "search", show=False),
        Binding("d",      "delete_session","delete", show=False),
        Binding("r",      "rename_session","rename", show=False),
        Binding("escape", "clear_search",  "esc",    show=False),
    ]

    # ── Messages ──────────────────────────────────────────────
    class SessionSelected(Message):
        def __init__(self, name: str, project: str | None) -> None:
            super().__init__()
            self.name = name
            self.project = project

    class NewSessionRequested(Message):
        def __init__(self, project: str | None, temp: bool = False) -> None:
            super().__init__()
            self.project = project
            self.temp = temp

    class NewProjectRequested(Message):
        pass

    class SessionDeleteRequested(Message):
        def __init__(self, name: str, project: str | None) -> None:
            super().__init__()
            self.name = name
            self.project = project

    class SessionRenameRequested(Message):
        def __init__(self, name: str, project: str | None) -> None:
            super().__init__()
            self.name = name
            self.project = project

    # ──────────────────────────────────────────────────────────
    def __init__(self) -> None:
        super().__init__(id="sidebar")
        self._current_project: str | None = None
        self._filter: str = ""
        self._sessions: list[Session] = []   # 경량 세션 메타 캐시
        self._selected_name: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("znc", id="sidebar-title")
        yield Static("PROJECTS", classes="section-label")
        yield ListView(id="project-list")
        yield Static("SESSIONS", classes="section-label")
        yield Input(placeholder="filter...", id="session-search")
        yield ListView(id="session-list")
        yield Static(
            "[n]ew [t]emp [p]roj  [/]search  [d]el [r]ename",
            id="sidebar-footer",
        )

    def on_mount(self) -> None:
        self.query_one("#session-search").display = False
        self.refresh_lists()

    # ── Public API ─────────────────────────────────────────────
    def refresh_lists(self) -> None:
        self._refresh_projects()
        self._refresh_sessions()

    def update_session_title(self, name: str, title: str) -> None:
        """세션 제목이 바뀌면 목록 레이블만 갱신."""
        for s in self._sessions:
            if s.name == name:
                s.title = title
                break
        self._render_session_list()

    # ── Refresh internals ──────────────────────────────────────
    def _refresh_projects(self) -> None:
        lv = self.query_one("#project-list", ListView)
        lv.clear()
        lv.append(ListItem(Label("[all]"), id="proj-__all__"))
        for proj in ProjectRepository.list_all():
            lv.append(ListItem(Label(proj.name), id=f"proj-{proj.name}"))

    def _refresh_sessions(self) -> None:
        ensure_dirs()
        sd = (ProjectRepository.sessions_dir(self._current_project)
              if self._current_project else SESSIONS_DIR)
        self._sessions = Session.list_sessions(sd)
        self._render_session_list()

    def _render_session_list(self) -> None:
        lv = self.query_one("#session-list", ListView)
        lv.clear()
        q = self._filter.lower()
        for s in self._sessions:
            label_text = s.display_title
            if q and q not in label_text.lower():
                continue
            # 현재 선택 항목 강조
            classes = "sidebar-item--active" if s.name == self._selected_name else ""
            lv.append(ListItem(
                Label(label_text, classes=classes),
                id=f"sess-{s.name}",
            ))

    # ── Events ────────────────────────────────────────────────
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        item_id = event.item.id or ""
        if item_id.startswith("proj-"):
            project = None if item_id == "proj-__all__" else item_id[5:]
            self._current_project = project
            self._filter = ""
            self._refresh_sessions()
        elif item_id.startswith("sess-"):
            name = item_id[5:]
            self._selected_name = name
            self.post_message(self.SessionSelected(name, self._current_project))

    def on_input_changed(self, event: Input.Changed) -> None:
        self._filter = event.value
        self._render_session_list()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Enter 로 검색창 닫고 첫 번째 결과 선택
        self._close_search()
        lv = self.query_one("#session-list", ListView)
        if lv.children:
            lv.focus()

    # ── Actions ───────────────────────────────────────────────
    def action_new_session(self) -> None:
        self.post_message(self.NewSessionRequested(self._current_project, temp=False))

    def action_temp_session(self) -> None:
        self.post_message(self.NewSessionRequested(self._current_project, temp=True))

    def action_new_project(self) -> None:
        self.post_message(self.NewProjectRequested())

    def action_focus_search(self) -> None:
        search = self.query_one("#session-search", Input)
        search.display = True
        search.focus()

    def action_clear_search(self) -> None:
        self._close_search()

    def action_delete_session(self) -> None:
        if self._selected_name:
            self.post_message(
                self.SessionDeleteRequested(self._selected_name, self._current_project)
            )

    def action_rename_session(self) -> None:
        if self._selected_name:
            self.post_message(
                self.SessionRenameRequested(self._selected_name, self._current_project)
            )

    def _close_search(self) -> None:
        search = self.query_one("#session-search", Input)
        search.display = False
        self._filter = ""
        self._render_session_list()
        self.query_one("#session-list", ListView).focus()
