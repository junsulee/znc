"""
사이드바 위젯 — 프로젝트/세션 탐색 (Windows Explorer 스타일).

탐색 구조:
  PROJECTS
    [unorganized]   ← 프로젝트 없는 세션들 (기본 뷰)
    > work          ← 클릭 시 해당 프로젝트 진입
    > personal

  SESSIONS (현재 위치에 따라 표시)
    ..              ← 프로젝트 진입 후 상위로 돌아가기
    session1
    session2

단축키 (사이드바 포커스 시):
  n   새 세션
  t   임시 채팅
  p   새 프로젝트
  /   세션 검색
  d   선택 세션 삭제
  r   선택 세션 이름 변경
  Esc 검색 닫기
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
    """왼쪽 사이드바: 프로젝트 + 세션 탐색."""

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
        self._current_project: str | None = None  # None = unorganized root
        self._filter: str = ""
        self._sessions: list[Session] = []
        self._selected_name: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("znc / AI CLI", id="sidebar-title")
        yield Static("PROJECTS", classes="section-label")
        yield ListView(id="project-list")
        yield Static("SESSIONS", classes="section-label")
        yield Input(placeholder="filter...", id="session-search")
        yield ListView(id="session-list")

    def on_mount(self) -> None:
        self.query_one("#session-search").display = False
        self.refresh_lists()

    # ── Public API ─────────────────────────────────────────────
    def refresh_lists(self) -> None:
        self._fill_project_list()
        self._reload_sessions()

    def update_session_title(self, name: str, title: str) -> None:
        for s in self._sessions:
            if s.name == name:
                s.title = title
                break
        self._fill_session_list()

    # ── 내부: ListView 갱신 ────────────────────────────────────
    def _fill_project_list(self) -> None:
        lv = self.query_one("#project-list", ListView)
        lv.clear()
        # [unorganized] — 프로젝트 없는 세션 루트
        lv.append(ListItem(Label("[unorganized]")))
        # 각 프로젝트
        for proj in ProjectRepository.list_all():
            lv.append(ListItem(Label(f"> {proj.name}")))

    def _reload_sessions(self) -> None:
        ensure_dirs()
        sd = (ProjectRepository.sessions_dir(self._current_project)
              if self._current_project else SESSIONS_DIR)
        self._sessions = Session.list_sessions(sd)
        self._fill_session_list()
        # 현재 위치 헤더 업데이트
        label_text = (
            f"SESSIONS  [{self._current_project}]"
            if self._current_project
            else "SESSIONS"
        )
        try:
            labels = self.query("Static.section-label")
            if len(labels) >= 2:
                labels[1].update(label_text)
        except Exception:
            pass

    def _fill_session_list(self) -> None:
        lv = self.query_one("#session-list", ListView)
        lv.clear()
        # 프로젝트 진입 상태 → ".." 상위 이동 항목
        if self._current_project:
            lv.append(ListItem(Label("..")))
        # 세션 목록
        q = self._filter.lower()
        for s in self._sessions:
            label_text = s.display_title
            if q and q not in label_text.lower():
                continue
            cls = "sidebar-item--active" if s.name == self._selected_name else ""
            lv.append(ListItem(Label(label_text, classes=cls)))

    # ── Events ────────────────────────────────────────────────
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        lv = event.list_view
        idx = event.list_view.index

        if lv.id == "project-list":
            projects = ProjectRepository.list_all()
            if idx == 0:
                # [unorganized] 선택 → 프로젝트 없는 세션으로 이동
                self._current_project = None
            elif idx is not None and idx - 1 < len(projects):
                # 프로젝트 진입
                self._current_project = projects[idx - 1].name
            self._filter = ""
            self._reload_sessions()

        elif lv.id == "session-list":
            # ".." = 상위로 이동
            base_idx = 0
            if self._current_project:
                if idx == 0:
                    self._current_project = None
                    self._filter = ""
                    self._reload_sessions()
                    return
                base_idx = 1  # ".." 항목 건너뜀

            visible = [
                s for s in self._sessions
                if not self._filter
                or self._filter.lower() in s.display_title.lower()
            ]
            real_idx = idx - base_idx if self._current_project else idx
            if idx is not None and real_idx is not None and real_idx < len(visible):
                name = visible[real_idx].name
                self._selected_name = name
                self.post_message(
                    self.SessionSelected(name, self._current_project)
                )

    def on_input_changed(self, event: Input.Changed) -> None:
        self._filter = event.value
        self._fill_session_list()

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
        self._fill_session_list()
        try:
            self.query_one("#session-list", ListView).focus()
        except Exception:
            pass
