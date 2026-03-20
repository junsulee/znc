"""
사이드바 위젯 — 프로젝트/세션 탐색 (Windows Explorer 스타일).

탐색 구조:
  PROJECTS
    (no project)   ← 프로젝트 없는 세션들 (기본)
    > work         ← 클릭 시 진입
    > personal

  SESSIONS [work]  ← 현재 위치
    ..             ← 상위로 돌아가기
    session1

단축키:
  n / t / p   새 세션 / 임시 / 새 프로젝트
  d / r       삭제 / 이름변경  (세션 또는 프로젝트)
  /           세션 검색
  Esc         검색 닫기
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Label, ListItem, ListView, Static

from znc.core.config import SESSIONS_DIR, ensure_dirs
from znc.core.i18n import ui as _ui
from znc.core.models import Session
from znc.core.repository import ProjectRepository


class Sidebar(Widget):
    BINDINGS = [
        Binding("n",      "new_session",    "new",    show=False),
        Binding("t",      "temp_session",   "temp",   show=False),
        Binding("p",      "new_project",    "project",show=False),
        Binding("slash",  "focus_search",   "search", show=False),
        Binding("d",      "delete_item",    "delete", show=False),
        Binding("r",      "rename_item",    "rename", show=False),
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

    class ProjectDeleteRequested(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    class ProjectRenameRequested(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    # ──────────────────────────────────────────────────────────
    def __init__(self) -> None:
        super().__init__(id="sidebar")
        self._current_project: str | None = None
        self._filter: str = ""
        self._sessions: list[Session] = []
        self._selected_name: str | None = None
        self._project_highlight: int = 0
        self._lang: str = "ko"

    def compose(self) -> ComposeResult:
        yield Static("znc", id="sidebar-title")
        yield Static("PROJECTS", classes="section-label", id="label-projects")
        yield ListView(id="project-list")
        yield Static("SESSIONS", classes="section-label", id="label-sessions")
        yield Input(placeholder="filter...", id="session-search")
        yield ListView(id="session-list")

    def on_mount(self) -> None:
        self.query_one("#session-search").display = False
        from znc.core.config import load_settings
        self._lang = load_settings().get("lang", "ko")
        self._apply_lang()
        self.refresh_lists()

    def _apply_lang(self) -> None:
        try:
            self.query_one("#label-projects", Static).update(_ui(self._lang, "projects"))
            self.query_one("#label-sessions", Static).update(_ui(self._lang, "sessions"))
            inp = self.query_one("#session-search", Input)
            inp.placeholder = _ui(self._lang, "filter_hint")
        except Exception:
            pass

    def set_lang(self, lang: str) -> None:
        self._lang = lang
        self._apply_lang()
        self._reload_sessions()

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

    # ── 내부 ──────────────────────────────────────────────────
    def _fill_project_list(self) -> None:
        lv = self.query_one("#project-list", ListView)
        lv.clear()
        # inbox: 프로젝트에 속하지 않은 세션들의 기본 공간
        lv.append(ListItem(Label("  inbox", markup=False)))
        for proj in ProjectRepository.list_all():
            lv.append(ListItem(Label(f"  > {proj.name}", markup=False)))

    def _reload_sessions(self) -> None:
        ensure_dirs()
        sd = (ProjectRepository.sessions_dir(self._current_project)
              if self._current_project else SESSIONS_DIR)
        self._sessions = Session.list_sessions(sd)
        self._fill_session_list()
        # SESSIONS 헤더 업데이트
        label = (
            f"{_ui(self._lang, 'sessions')}  [{self._current_project}]"
            if self._current_project else _ui(self._lang, "sessions")
        )
        try:
            labels = self.query("Static.section-label")
            if len(labels) >= 2:
                labels[1].update(label)
        except Exception:
            pass

    def _fill_session_list(self) -> None:
        lv = self.query_one("#session-list", ListView)
        lv.clear()
        if self._current_project:
            lv.append(ListItem(Label("  ..", markup=False)))
        q = self._filter.lower()
        for s in self._sessions:
            text = s.display_title
            if q and q not in text.lower():
                continue
            cls = "sidebar-item--active" if s.name == self._selected_name else ""
            lv.append(ListItem(Label(f"  {text}", markup=False, classes=cls)))

    def _visible_sessions(self) -> list[Session]:
        q = self._filter.lower()
        return [
            s for s in self._sessions
            if not q or q in s.display_title.lower()
        ]

    # ── Events ────────────────────────────────────────────────
    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """하이라이트 변경 시 프로젝트 인덱스 추적."""
        if event.list_view.id == "project-list":
            self._project_highlight = event.list_view.index or 0

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        lv = event.list_view
        idx = event.list_view.index

        if lv.id == "project-list":
            projects = ProjectRepository.list_all()
            if idx == 0:
                self._current_project = None
            elif idx is not None and idx - 1 < len(projects):
                self._current_project = projects[idx - 1].name
            self._filter = ""
            self._reload_sessions()

        elif lv.id == "session-list":
            base = 1 if self._current_project else 0
            if self._current_project and idx == 0:
                # ".." → 상위로
                self._current_project = None
                self._filter = ""
                self._reload_sessions()
                return
            visible = self._visible_sessions()
            real = (idx or 0) - base
            if real >= 0 and real < len(visible):
                name = visible[real].name
                self._selected_name = name
                self.post_message(self.SessionSelected(name, self._current_project))

    def on_input_changed(self, event: Input.Changed) -> None:
        self._filter = event.value
        self._fill_session_list()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._close_search()

    # ── Actions ───────────────────────────────────────────────
    def action_new_session(self) -> None:
        self.post_message(self.NewSessionRequested(self._current_project, temp=False))

    def action_temp_session(self) -> None:
        self.post_message(self.NewSessionRequested(self._current_project, temp=True))

    def action_new_project(self) -> None:
        self.post_message(self.NewProjectRequested())

    def action_focus_search(self) -> None:
        inp = self.query_one("#session-search", Input)
        inp.display = True
        inp.focus()

    def action_clear_search(self) -> None:
        self._close_search()

    def action_delete_item(self) -> None:
        """포커스 위치에 따라 세션 또는 프로젝트 삭제."""
        focused = self.app.focused
        if focused and getattr(focused, "id", "") == "project-list":
            # 프로젝트 삭제 (index 0 = no-project 는 삭제 불가)
            projects = ProjectRepository.list_all()
            idx = self._project_highlight
            if idx >= 1 and idx - 1 < len(projects):
                self.post_message(self.ProjectDeleteRequested(projects[idx - 1].name))
        else:
            # 세션 삭제
            if self._selected_name:
                self.post_message(
                    self.SessionDeleteRequested(self._selected_name, self._current_project)
                )

    def action_rename_item(self) -> None:
        """포커스 위치에 따라 세션 또는 프로젝트 이름변경."""
        focused = self.app.focused
        if focused and getattr(focused, "id", "") == "project-list":
            projects = ProjectRepository.list_all()
            idx = self._project_highlight
            if idx >= 1 and idx - 1 < len(projects):
                self.post_message(self.ProjectRenameRequested(projects[idx - 1].name))
        else:
            if self._selected_name:
                self.post_message(
                    self.SessionRenameRequested(self._selected_name, self._current_project)
                )

    def _close_search(self) -> None:
        inp = self.query_one("#session-search", Input)
        inp.display = False
        self._filter = ""
        self._fill_session_list()
