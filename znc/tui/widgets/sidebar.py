"""
사이드바 위젯 개선.

- inbox 제거: 프로젝트 목록에는 실제 프로젝트만
- 기본 뷰: 전체 세션 (전역 + 모든 프로젝트) 합산
- 프로젝트 진입 시: 해당 프로젝트의 세션만
- rename 버그 수정: on_list_view_highlighted 에서 _selected_name 동기화
- 세션 이동(m) 기능 추가
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
        Binding("m",      "move_item",      "move",   show=False),
        Binding("escape", "clear_search",   "esc",    show=False),
    ]

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
        def __init__(self, name: str, project: str | None, display: str) -> None:
            super().__init__()
            self.name = name
            self.project = project
            self.display = display   # 현재 표시 제목

    class SessionMoveRequested(Message):
        def __init__(self, name: str, from_project: str | None) -> None:
            super().__init__()
            self.name = name
            self.from_project = from_project

    class ProjectDeleteRequested(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    class ProjectRenameRequested(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    def __init__(self) -> None:
        super().__init__(id="sidebar")
        self._current_project: str | None = None
        self._filter: str = ""
        self._sessions: list[Session] = []
        self._selected_name: str | None = None
        self._selected_project: str | None = None  # 선택된 세션의 실제 프로젝트
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
        # inbox 없음 — 실제 프로젝트만 표시
        for proj in ProjectRepository.list_all():
            lv.append(ListItem(Label(f"  > {proj.name}", markup=False)))

    def _reload_sessions(self) -> None:
        ensure_dirs()
        if self._current_project:
            # 프로젝트 진입: 해당 프로젝트 세션만
            sd = ProjectRepository.sessions_dir(self._current_project)
            self._sessions = Session.list_sessions(sd)
        else:
            # 전체 뷰: 전역 + 모든 프로젝트 합산
            all_sessions: list[Session] = []
            all_sessions += Session.list_sessions(SESSIONS_DIR)
            for proj in ProjectRepository.list_all():
                sd = ProjectRepository.sessions_dir(proj.name)
                all_sessions += Session.list_sessions(sd)
            # updated_at 기준 최신순 정렬
            all_sessions.sort(key=lambda s: s.updated_at or "", reverse=True)
            self._sessions = all_sessions

        self._fill_session_list()
        self._update_sessions_header()

    def _update_sessions_header(self) -> None:
        lang = self._lang
        label = (
            f"{_ui(lang, 'sessions')}  [{self._current_project}]"
            if self._current_project else _ui(lang, "sessions")
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
            # 전체 뷰에서 프로젝트 소속 세션에 레이블 표시
            if not self._current_project and s.project:
                text = f"[{s.project}]  {text}"
            if q and q not in text.lower():
                continue
            cls = "sidebar-item--active" if s.name == self._selected_name else ""
            lv.append(ListItem(Label(f"  {text}", markup=False, classes=cls)))

    def _visible_sessions(self) -> list[Session]:
        q = self._filter.lower()
        return [
            s for s in self._sessions
            if not q or q in (
                f"[{s.project}]  {s.display_title}" if (not self._current_project and s.project)
                else s.display_title
            ).lower()
        ]

    def _get_selected_session(self) -> Session | None:
        if self._selected_name is None:
            return None
        for s in self._sessions:
            if s.name == self._selected_name:
                return s
        return None

    # ── Events ────────────────────────────────────────────────
    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        lv = event.list_view
        idx = event.list_view.index
        if lv.id == "project-list":
            self._project_highlight = idx or 0
        elif lv.id == "session-list":
            self._sync_selected_from_idx(idx)

    def _sync_selected_from_idx(self, idx: int | None) -> None:
        if idx is None:
            return
        base = 1 if self._current_project else 0
        if self._current_project and idx == 0:
            self._selected_name = None
            self._selected_project = None
            return
        visible = self._visible_sessions()
        real = idx - base
        if 0 <= real < len(visible):
            s = visible[real]
            self._selected_name = s.name
            self._selected_project = s.project

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        lv = event.list_view
        idx = event.list_view.index

        if lv.id == "project-list":
            projects = ProjectRepository.list_all()
            if idx is not None and idx < len(projects):
                self._current_project = projects[idx].name
            self._filter = ""
            self._reload_sessions()

        elif lv.id == "session-list":
            base = 1 if self._current_project else 0
            if self._current_project and idx == 0:
                self._current_project = None
                self._filter = ""
                self._reload_sessions()
                return
            visible = self._visible_sessions()
            real = (idx or 0) - base
            if 0 <= real < len(visible):
                s = visible[real]
                self._selected_name = s.name
                self._selected_project = s.project
                self.post_message(self.SessionSelected(s.name, s.project))

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
        focused = self.app.focused
        if focused and getattr(focused, "id", "") == "project-list":
            projects = ProjectRepository.list_all()
            idx = self._project_highlight
            if idx < len(projects):
                self.post_message(self.ProjectDeleteRequested(projects[idx].name))
        else:
            s = self._get_selected_session()
            if s:
                self.post_message(self.SessionDeleteRequested(s.name, s.project))

    def action_rename_item(self) -> None:
        focused = self.app.focused
        if focused and getattr(focused, "id", "") == "project-list":
            projects = ProjectRepository.list_all()
            idx = self._project_highlight
            if idx < len(projects):
                self.post_message(self.ProjectRenameRequested(projects[idx].name))
        else:
            s = self._get_selected_session()
            if s:
                self.post_message(
                    self.SessionRenameRequested(s.name, s.project, s.display_title)
                )

    def action_move_item(self) -> None:
        s = self._get_selected_session()
        if s:
            self.post_message(self.SessionMoveRequested(s.name, s.project))

    def _close_search(self) -> None:
        inp = self.query_one("#session-search", Input)
        inp.display = False
        self._filter = ""
        self._fill_session_list()
