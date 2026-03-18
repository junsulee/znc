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
        Binding("n",      "new_session",    "new",    show=False),
        Binding("t",      "temp_session",   "temp",   show=False),
        Binding("p",      "new_project",    "project",show=False),
        Binding("slash",  "focus_search",   "search", show=False),
        Binding("d",      "delete_session", "delete", show=False),
        Binding("r",      "rename_session", "rename", show=False),
        Binding("escape", "clear_search",   "esc",    show=False),
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
        self._sessions: list[Session] = []
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
        self._rebuild_project_list()
        self._reload_sessions()

    def update_session_title(self, name: str, title: str) -> None:
        for s in self._sessions:
            if s.name == name:
                s.title = title
                break
        self._rebuild_session_list()

    # ── 내부: ListView 전체 교체 ────────────────────────────────
    # Textual의 ListView.clear() + append() 패턴은 clear()가 비동기이므로
    # await 없이 호출하면 DOM 정리 전에 중복 ID 삽입 오류가 발생한다.
    # ListView 위젯 자체를 remove → mount 로 교체해 이 문제를 회피한다.

    def _rebuild_project_list(self) -> None:
        try:
            old = self.query_one("#project-list", ListView)
            old.remove()
        except Exception:
            pass
        items: list[ListItem] = [ListItem(Label("[all]"))]
        for proj in ProjectRepository.list_all():
            items.append(ListItem(Label(proj.name)))
        new_lv = ListView(*items, id="project-list")
        # sidebar-title 아래, 첫 번째 section-label 바로 뒤에 삽입
        try:
            anchor = self.query("Static.section-label")[0]
            self.mount(new_lv, after=anchor)
        except Exception:
            self.mount(new_lv)

    def _reload_sessions(self) -> None:
        ensure_dirs()
        sd = (ProjectRepository.sessions_dir(self._current_project)
              if self._current_project else SESSIONS_DIR)
        self._sessions = Session.list_sessions(sd)
        self._rebuild_session_list()

    def _rebuild_session_list(self) -> None:
        try:
            old = self.query_one("#session-list", ListView)
            old.remove()
        except Exception:
            pass
        q = self._filter.lower()
        items: list[ListItem] = []
        for s in self._sessions:
            label_text = s.display_title
            if q and q not in label_text.lower():
                continue
            lbl_cls = "sidebar-item--active" if s.name == self._selected_name else ""
            items.append(ListItem(Label(label_text, classes=lbl_cls)))
        new_lv = ListView(*items, id="session-list")
        try:
            anchor = self.query_one("#session-search", Input)
            self.mount(new_lv, after=anchor)
        except Exception:
            self.mount(new_lv)

    # ── Events ────────────────────────────────────────────────
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        lv = event.list_view
        idx = event.list_view.index
        if lv.id == "project-list":
            # 인덱스 0 = [all], 나머지는 프로젝트 순서
            projects = ProjectRepository.list_all()
            if idx == 0:
                self._current_project = None
            elif idx is not None and idx - 1 < len(projects):
                self._current_project = projects[idx - 1].name
            self._filter = ""
            self._reload_sessions()
        elif lv.id == "session-list":
            visible = [
                s for s in self._sessions
                if not self._filter or self._filter.lower() in s.display_title.lower()
            ]
            if idx is not None and idx < len(visible):
                name = visible[idx].name
                self._selected_name = name
                self.post_message(self.SessionSelected(name, self._current_project))

    def on_input_changed(self, event: Input.Changed) -> None:
        self._filter = event.value
        self._rebuild_session_list()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._close_search()
        try:
            lv = self.query_one("#session-list", ListView)
            if lv.children:
                lv.focus()
        except Exception:
            pass

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
        self._rebuild_session_list()
        try:
            self.query_one("#session-list", ListView).focus()
        except Exception:
            pass
