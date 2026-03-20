"""
znc TUI 메인 앱.

레이아웃:
┌─────────────┬────────────────────────────────────────┐
│  Sidebar    │  Header                                │
│  (projects  │  MessageView (스크롤 채팅)              │
│   sessions) │  ProcessLog  (Ctrl+L 토글, 기본 hidden)│
│             │  StatusBar   (1줄 고정 상태 바)         │
│             │  InputBar                              │
└─────────────┴────────────────────────────────────────┘
              KeybindBar (dock=bottom)

단축키:
  Ctrl+N   새 채팅
  Ctrl+T   임시 채팅 (저장 안 함)
  Ctrl+S   설정
  Ctrl+P   Persona  (ENABLE_COMMAND_PALETTE=False 로 Textual 팔레트 비활성화)
  Ctrl+E   메모리   (Ctrl+M = Enter 이므로 사용 불가)
  Ctrl+L   프로세스 로그 토글
  Tab      사이드바 ↔ 채팅창
  Ctrl+Q   종료
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Label, Static

from znc.backends.base import BaseBackend
from znc.core.config import SESSIONS_DIR, ensure_dirs, load_settings
from znc.core.memory import (
    add_manual, build_memory_context,
    extract_and_save_auto, load_all as load_all_memory, remove_manual,
)
from znc.core.models import Message, Session
from znc.core.persona import load_default_persona, load_persona, Persona
from znc.core.repository import ProjectRepository
from znc.core.web_search import search_and_crawl
from znc.tui.process_state import ProcessState, Stage
from znc.tui.screens.memory import MemoryScreen
from znc.tui.screens.new_project import NewProjectScreen
from znc.tui.screens.persona import PersonaScreen
from znc.tui.screens.rename_session import RenameSessionScreen
from znc.tui.screens.settings import SettingsScreen
from znc.tui.widgets.chat_view import MessageView
from znc.tui.widgets.input_bar import InputBar
from znc.tui.widgets.process_log import ProcessLog
from znc.tui.widgets.sidebar import Sidebar
from znc.tui.widgets.status_bar import StatusBar

CSS_PATH = Path(__file__).parent / "znc.tcss"

_UNSAVED = "__unsaved__"
_TEMP    = "__temp__"


class ZncApp(App):
    """znc TUI 메인 앱."""

    CSS_PATH = CSS_PATH

    # Textual 기본 커맨드 팔레트(Ctrl+P)를 비활성화.
    # 활성 시 Ctrl+P 가 팔레트로 가로채여 persona 팝업이 열리지 않음.
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        Binding("ctrl+n", "new_session",   "새 채팅",   show=True,  priority=True),
        Binding("ctrl+t", "temp_session",  "임시 채팅", show=True,  priority=True),
        Binding("ctrl+s", "open_settings", "설정",      show=True,  priority=True),
        Binding("ctrl+p", "open_persona",  "persona",   show=True,  priority=True),
        Binding("ctrl+e", "open_memory",   "memory",    show=True,  priority=True),
        Binding("ctrl+l", "toggle_log",    "log",       show=True,  priority=True),
        Binding("tab",    "focus_next",    "패널전환",  show=True),
        Binding("ctrl+q", "quit",          "종료",      show=True,  priority=True),
        Binding("escape", "focus_input",   "",          show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._settings = load_settings()
        self._session: Optional[Session] = None
        self._backend: Optional[BaseBackend] = None
        self._persona: Persona = load_default_persona()
        self._ai_name: str = self._settings.get("ai_name", "znc")
        self._streaming = False
        self._stream_buffer = ""
        self._stream_id: int = 0   # 세션 전환 시 증가 → 구 스트림 콜백 무효화
        self._ps = ProcessState()
        self._title_generated = False  # 현재 세션 제목 생성 완료 여부

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Sidebar()
        with Vertical(id="chat-pane"):
            yield Static(id="chat-header")
            yield MessageView()
            yield ProcessLog(self._ps)
            yield StatusBar(self._ps)
            yield InputBar()
        yield Static(id="keybind-bar")

    def on_mount(self) -> None:
        self._reload_backend()
        self._update_header()
        self._update_keybind_bar()
        self.query_one(InputBar).focus_input()

    # ------------------------------------------------------------------
    # ProcessState helpers
    # ------------------------------------------------------------------
    def _step(self, stage: Stage, detail: str = "") -> None:
        self._ps.transition(stage, detail)
        self.query_one(StatusBar).refresh()
        self.query_one(ProcessLog).append_step()

    def _step_from_thread(self, stage: Stage, detail: str = "") -> None:
        self.call_from_thread(self._step, stage, detail)

    def _reset_process(self) -> None:
        self._ps.reset()
        self.query_one(StatusBar).refresh()
        self.query_one(ProcessLog).set_state(self._ps)

    # ------------------------------------------------------------------
    # Header / Keybind
    # ------------------------------------------------------------------
    def _update_header(self) -> None:
        cfg = self._settings
        backend = cfg.get("backend", "ollama")
        model = cfg.get("openai_model") if backend == "openai" else cfg.get("model", "")
        model_short = (model or "")[:24]
        persona_name = self._persona.name

        if self._session:
            if self._session.is_temp:
                sess_label = "[dim #d29922][temp][/]"
            elif self._session.name in (_UNSAVED, _TEMP):
                lang = self._settings.get("lang", "ko")
                sess_label = "[dim]새 채팅[/]" if lang == "ko" else "[dim]new chat[/]"
            else:
                title = self._session.display_title
                sess_label = f"[dim]{title[:40]}[/]"
        else:
            sess_label = "[dim]—[/]"

        self.query_one("#chat-header", Static).update(
            f"znc  [dim]|[/]  [bold #58a6ff]{persona_name}[/]  "
            f"[dim]|[/]  [dim]{backend}:{model_short}[/]  "
            f"[dim]|[/]  {sess_label}"
        )

    def _update_keybind_bar(self) -> None:
        self.query_one("#keybind-bar", Static).update(
            "[bold #58a6ff]^N[/] new  "
            "[bold #58a6ff]^T[/] temp  "
            "[bold #58a6ff]^S[/] settings  "
            "[bold #58a6ff]^P[/] persona  "
            "[bold #58a6ff]^E[/] memory  "
            "[bold #58a6ff]^L[/] log  "
            "[bold #58a6ff]Tab[/] panel  "
            "[bold #58a6ff]^Q[/] quit"
        )

    # ------------------------------------------------------------------
    # Backend
    # ------------------------------------------------------------------
    def _reload_backend(self) -> None:
        self._settings = load_settings()
        self._ai_name = self._settings.get("ai_name", "znc")
        try:
            self._backend = BaseBackend.from_settings(self._settings)
        except Exception as e:
            self._backend = None
            self._write_status(f"backend error: {e}", "red")

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------
    def _sessions_dir(self, project: str | None = None) -> str:
        p = project if project is not None else (
            self._session.project if self._session else None
        )
        if p:
            return ProjectRepository.sessions_dir(p)
        ensure_dirs()
        return SESSIONS_DIR

    def _start_new_session(self, project: str | None = None, temp: bool = False) -> None:
        # 진행 중인 스트림 무효화 — 임시 세션 등에서 전환 시 내용 누수 방지
        self._stream_id += 1
        self._streaming = False
        self._stream_buffer = ""

        system = None
        if project:
            proj = ProjectRepository.get(project)
            system = proj.system_prompt if proj else None
        self._session = Session(
            name=_TEMP if temp else _UNSAVED,
            project=project,
            system_prompt=system,
            is_temp=temp,
        )
        self._title_generated = False
        mv = self.query_one(MessageView)
        mv.end_streaming()
        mv.clear()
        self._reset_process()
        self._update_header()

    def _load_session(self, name: str, project: str | None) -> None:
        # 진행 중인 스트림 무효화
        self._stream_id += 1
        self._streaming = False
        self._stream_buffer = ""

        try:
            self._session = Session.load(self._sessions_dir(project), name)
            self._title_generated = bool(self._session.title)
            mv = self.query_one(MessageView)
            mv.end_streaming()
            mv.render_history(self._session.messages, self._ai_name)
            self._reset_process()
            self._update_header()
        except FileNotFoundError:
            self._write_status(f"session not found: {name}", "red")

    def _save_session(self, name: str | None = None) -> None:
        if not self._session or self._session.is_temp:
            return
        if name:
            self._session.name = name
        elif self._session.name in (_UNSAVED, _TEMP):
            from znc.cli.utils import generate_default_session_name
            self._session.name = generate_default_session_name()

        sd = self._sessions_dir()
        path = self._session.save(sd)
        self._write_status(f"saved: {path}", "green")
        self._update_header()
        self.query_one(Sidebar).refresh_lists()

    def _rename_session_file(self, old_name: str, new_name: str) -> None:
        """파일을 rename 하고 Session.name + title 갱신."""
        sd = self._sessions_dir()
        old_path = os.path.join(sd, f"{old_name}.json")
        new_path = os.path.join(sd, f"{new_name}.json")
        if not os.path.exists(old_path):
            return
        os.rename(old_path, new_path)
        # 파일 내부 name 필드도 갱신
        try:
            import json
            with open(new_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            d["name"] = new_name
            with open(new_path, "w", encoding="utf-8") as f:
                json.dump(d, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        if self._session and self._session.name == old_name:
            self._session.name = new_name
            self._update_header()
        self.query_one(Sidebar).refresh_lists()

    # ------------------------------------------------------------------
    # Auto-title
    # ------------------------------------------------------------------
    def _maybe_generate_title(self) -> None:
        """
        첫 응답 완료 후 백그라운드에서 제목 생성.
        이미 제목이 있거나 메시지가 부족하면 스킵.
        """
        if not self._session:
            return
        if self._title_generated:
            return
        if self._session.is_temp:
            return
        if self._session.name in (_UNSAVED, _TEMP):
            return
        if len(self._session.messages) < 2:
            return
        if not self._backend:
            return

        session_snapshot = self._session
        backend_snapshot = self._backend

        def run():
            from znc.cli.utils import generate_session_title
            title = generate_session_title(session_snapshot, backend_snapshot)
            if title and title != session_snapshot.name:
                session_snapshot.title = title
                # 파일에 title 필드 저장
                try:
                    sd = self._sessions_dir(session_snapshot.project)
                    session_snapshot.save(sd)
                except Exception:
                    pass
                self.call_from_thread(self._on_title_generated, session_snapshot.name, title)

        threading.Thread(target=run, daemon=True).start()

    def _on_title_generated(self, session_name: str, title: str) -> None:
        self._title_generated = True
        self._update_header()
        self.query_one(Sidebar).update_session_title(session_name, title)

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------
    def _build_prompt(self) -> str:
        if not self._session:
            return ""
        ai = self._ai_name
        prompt = ""
        for m in self._session.messages:
            if m.role == "user":
                prompt += f"User: {m.content}\n"
            elif m.role == "assistant":
                prompt += f"{ai}: {m.content}\n"
        prompt += f"{ai}:"
        return prompt

    def _build_system(self, extra: str = "") -> str:
        mem_ctx = build_memory_context()
        effective = self._persona.build_system_prompt(
            extra_context="\n".join(filter(None, [mem_ctx, extra]))
        )
        parts = []
        if self._session and self._session.system_prompt:
            parts.append(self._session.system_prompt)
        parts.append(effective)
        return "\n".join(parts)

    def _send_message(self, user_text: str) -> None:
        if not self._backend:
            self._write_status("backend not configured. press ^S to open settings.", "red")
            return
        if self._streaming:
            return
        if not self._session:
            self._start_new_session()

        # 첫 메시지라면 세션 파일을 미리 생성 (제목 생성 전 저장 기반)
        if (not self._session.is_temp
                and self._session.name in (_UNSAVED, _TEMP)
                and not self._session.messages):
            from znc.cli.utils import generate_default_session_name
            self._session.name = generate_default_session_name()
            sd = self._sessions_dir()
            self._session.save(sd)
            self._update_header()
            self.query_one(Sidebar).refresh_lists()

        self._reset_process()
        self._step(Stage.LOADING)

        msg = Message(role="user", content=user_text)
        self._session.append(msg)
        self.query_one(MessageView).append_message(msg, self._ai_name)

        mem_items = load_all_memory()
        if mem_items:
            self._step(Stage.MEMORY, f"{len(mem_items)} items")

        prompt = self._build_prompt()
        system = self._build_system()
        self._stream_buffer = ""
        self._streaming = True

        # 이 스트림의 고유 ID — 세션 전환 시 _stream_id 가 증가하면 콜백 무시
        self._stream_id += 1
        my_stream_id = self._stream_id

        mv = self.query_one(MessageView)
        self._step(Stage.THINKING, "waiting for first token")
        mv.begin_assistant_turn(self._ai_name)
        first_token = False

        def run_stream():
            nonlocal first_token
            try:
                for token in self._backend.stream(prompt, system_prompt=system):
                    if self._stream_id != my_stream_id:
                        return  # 세션이 전환됨 — 이 스트림 폐기
                    if not first_token:
                        first_token = True
                        self._step_from_thread(Stage.GENERATING)
                    self._stream_buffer += token
                    self.call_from_thread(mv.append_token, token)
            except Exception as e:
                if self._stream_id == my_stream_id:
                    self._step_from_thread(Stage.ERROR, str(e))
                    self.call_from_thread(self._write_status, f"stream error: {e}", "red")
            finally:
                def on_done():
                    if self._stream_id == my_stream_id:
                        self._on_stream_done()
                    else:
                        self._streaming = False
                self.call_from_thread(on_done)

        threading.Thread(target=run_stream, daemon=True).start()

    def _on_stream_done(self) -> None:
        self._streaming = False
        content = self._stream_buffer
        self._stream_buffer = ""
        if self._session and content:
            self._session.append(Message(role="assistant", content=content))
            # 세션 저장 (임시 채팅 제외)
            if not self._session.is_temp:
                try:
                    self._session.save(self._sessions_dir())
                except Exception:
                    pass
            # auto 메모리 추출
            if self._backend:
                def _extract():
                    extract_and_save_auto(content, self._backend)
                threading.Thread(target=_extract, daemon=True).start()
            # auto-title: 첫 응답 완료 후 1회만 실행
            if not self._title_generated:
                self._maybe_generate_title()

        self._step(Stage.DONE)
        self.query_one(MessageView).end_streaming()
        self.query_one(InputBar).focus_input()

    def _write_status(self, text: str, style: str = "yellow") -> None:
        self.query_one(MessageView).write_status(text, style)

    # ------------------------------------------------------------------
    # Slash commands
    # ------------------------------------------------------------------
    def _handle_slash(self, text: str) -> bool:
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/search":
            if not arg:
                self._write_status("usage: /search <query>")
                return True
            self._do_web_search(arg)
            return True
        if cmd == "/remember":
            k, _, v = arg.partition(":") if ":" in arg else (arg, "", arg)
            add_manual(k.strip(), v.strip())
            self._write_status(f"remembered: {k.strip()}", "green")
            return True
        if cmd == "/forget":
            removed = remove_manual(arg.strip())
            self._write_status(
                f"forgotten: {arg.strip()}" if removed else f"not found: {arg.strip()}",
                "green" if removed else "yellow",
            )
            return True
        if cmd == "/persona":
            if arg:
                p = load_persona(arg.strip())
                if p:
                    self._persona = p
                    self._write_status(f"persona: {p.name}", "green")
                    self._update_header()
                else:
                    self._write_status(f"persona not found: {arg}", "red")
            else:
                self.action_open_persona()
            return True
        if cmd == "/clear":
            if self._session:
                self._session.messages.clear()
            self.query_one(MessageView).clear()
            self._reset_process()
            return True
        if cmd == "/save":
            self._save_session(arg.strip() or None)
            return True
        if cmd == "/export":
            if not arg:
                self._write_status("usage: /export <filepath>")
                return True
            self._do_export(arg.strip())
            return True
        if cmd == "/memory":
            self.action_open_memory()
            return True
        if cmd == "/settings":
            self.action_open_settings()
            return True
        return False

    def _do_web_search(self, query: str) -> None:
        if not self._session:
            self._start_new_session()

        self._reset_process()
        self._step(Stage.LOADING)

        engines = self._settings.get("search_engines", ["ddg", "naver"])
        serper_key = self._settings.get("google_serper_key", "")
        engine_label = "+".join(engines)
        self._step(Stage.SEARCH, f'"{query}"  [{engine_label}]')

        def run():
            def progress(url: str, done: int, total: int) -> None:
                if url:
                    domain = url.split("/")[2] if url.count("/") >= 2 else url
                    self._step_from_thread(Stage.CRAWL, domain)

            results, context = search_and_crawl(
                query,
                engines=engines,
                google_serper_key=serper_key,
                progress_callback=progress,
            )
            if not context:
                self._step_from_thread(Stage.ERROR, "no results found")
                self.call_from_thread(self._write_status, "no results found", "red")
                return
            if self._session:
                self.call_from_thread(
                    self._send_message_with_context,
                    f"[web search context]\n{context}\n\n위 내용을 참고해서 '{query}' 에 대해 답해줘.",
                )

        threading.Thread(target=run, daemon=True).start()

    def _send_message_with_context(self, text: str) -> None:
        if not self._backend or not self._session:
            return
        # 사용자 질문을 히스토리에 남김 (검색 쿼리 기반)
        if (not self._session.is_temp
                and self._session.name in (_UNSAVED, _TEMP)
                and not self._session.messages):
            from znc.cli.utils import generate_default_session_name
            self._session.name = generate_default_session_name()
            self._session.save(self._sessions_dir())
            self._update_header()
            self.query_one(Sidebar).refresh_lists()

        self._stream_buffer = ""
        self._streaming = True
        self._stream_id += 1
        my_stream_id = self._stream_id
        prompt = self._build_prompt() + f"\n[context]\n{text}\n{self._ai_name}:"
        system = self._build_system()
        mv = self.query_one(MessageView)

        self._step(Stage.THINKING, "waiting for first token")
        mv.begin_assistant_turn(self._ai_name)
        first_token = False

        def run_stream():
            nonlocal first_token
            try:
                for token in self._backend.stream(prompt, system_prompt=system):
                    if self._stream_id != my_stream_id:
                        return
                    if not first_token:
                        first_token = True
                        self._step_from_thread(Stage.GENERATING)
                    self._stream_buffer += token
                    self.call_from_thread(mv.append_token, token)
            except Exception as e:
                if self._stream_id == my_stream_id:
                    self._step_from_thread(Stage.ERROR, str(e))
                    self.call_from_thread(self._write_status, f"error: {e}", "red")
            finally:
                def on_done():
                    if self._stream_id == my_stream_id:
                        self._on_stream_done()
                    else:
                        self._streaming = False
                self.call_from_thread(on_done)

        threading.Thread(target=run_stream, daemon=True).start()

    def _do_export(self, filepath: str) -> None:
        if not self._session:
            self._write_status("no active session", "red")
            return
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"znc — Chat Export\n{'─' * 44}\n")
                f.write(f"Session : {self._session.display_title}\n\n")
                for m in self._session.messages:
                    if m.role == "user":
                        f.write(f"you:\n{m.content}\n\n")
                    elif m.role == "assistant":
                        f.write(f"{self._ai_name}:\n{m.content}\n\n")
            self._write_status(f"exported: {filepath}", "green")
        except Exception as e:
            self._write_status(f"export error: {e}", "red")

    # ------------------------------------------------------------------
    # Input handler
    # ------------------------------------------------------------------
    def on_input_bar_submitted(self, event: InputBar.Submitted) -> None:
        text = event.text.strip()
        if not text:
            return
        if text.startswith("/"):
            handled = self._handle_slash(text)
            if not handled:
                self._write_status(f"unknown command: {text.split()[0]}", "yellow")
            return
        self._send_message(text)

    # ------------------------------------------------------------------
    # Sidebar events
    # ------------------------------------------------------------------
    def on_sidebar_session_selected(self, event: Sidebar.SessionSelected) -> None:
        self._load_session(event.name, event.project)

    def on_sidebar_new_session_requested(self, event: Sidebar.NewSessionRequested) -> None:
        self._start_new_session(event.project, temp=event.temp)

    def on_sidebar_new_project_requested(self, event: Sidebar.NewProjectRequested) -> None:
        self.action_new_project()

    def on_sidebar_session_delete_requested(
        self, event: Sidebar.SessionDeleteRequested
    ) -> None:
        sd = self._sessions_dir(event.project)
        path = os.path.join(sd, f"{event.name}.json")
        if os.path.exists(path):
            os.remove(path)
            self._write_status(f"deleted: {event.name}", "green")
            if self._session and self._session.name == event.name:
                self._session = None
                self.query_one(MessageView).clear()
                self._update_header()
        self.query_one(Sidebar).refresh_lists()

    def on_sidebar_session_rename_requested(
        self, event: Sidebar.SessionRenameRequested
    ) -> None:
        def callback(new_name: str | None) -> None:
            if new_name:
                self._rename_session_file(event.name, new_name)
        self.push_screen(RenameSessionScreen(event.name), callback)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_new_session(self) -> None:
        self._start_new_session()
        self.query_one(InputBar).focus_input()

    def action_temp_session(self) -> None:
        self._start_new_session(temp=True)
        self.query_one(InputBar).focus_input()

    def action_new_project(self) -> None:
        def callback(name: str | None) -> None:
            if name:
                self.query_one(Sidebar).refresh_lists()
        self.push_screen(NewProjectScreen(), callback)

    def action_open_settings(self) -> None:
        def callback(cfg) -> None:
            if cfg:
                self._settings = cfg
                self._reload_backend()
                self._update_header()
        self.push_screen(SettingsScreen(), callback)

    def action_open_persona(self) -> None:
        def callback(name: str | None) -> None:
            if name:
                p = load_persona(name)
                if p:
                    self._persona = p
                    self._update_header()
        self.push_screen(PersonaScreen(self._persona.name), callback)

    def action_open_memory(self) -> None:
        self.push_screen(MemoryScreen())

    def action_toggle_log(self) -> None:
        pl = self.query_one(ProcessLog)
        visible = pl.toggle()
        self.query_one(StatusBar).set_log_visible(visible)

    def action_focus_input(self) -> None:
        self.query_one(InputBar).focus_input()

    def action_quit(self) -> None:
        # 임시 채팅이 아닌 경우 자동 저장
        if (self._session
                and not self._session.is_temp
                and self._session.messages
                and self._session.name not in (_UNSAVED, _TEMP)):
            try:
                self._session.save(self._sessions_dir())
            except Exception:
                pass
        self.exit()
