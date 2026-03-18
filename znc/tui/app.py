"""
znc TUI 메인 앱.

레이아웃:
┌─────────────┬────────────────────────────────────────┐
│  Sidebar    │  Header                                │
│  (projects  │  MessageView (스크롤 채팅)              │
│   sessions) │  ProcessLog  (L 키 토글, 기본 hidden)  │
│             │  StatusBar   (1줄 고정 상태 바)         │
│             │  InputBar                              │
└─────────────┴────────────────────────────────────────┘
              KeybindBar (dock=bottom)
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
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
from znc.tui.screens.settings import SettingsScreen
from znc.tui.widgets.chat_view import MessageView
from znc.tui.widgets.input_bar import InputBar
from znc.tui.widgets.process_log import ProcessLog
from znc.tui.widgets.sidebar import Sidebar
from znc.tui.widgets.status_bar import StatusBar

CSS_PATH = Path(__file__).parent / "znc.tcss"


class ZncApp(App):
    """znc TUI 메인 앱."""

    CSS_PATH = CSS_PATH

    BINDINGS = [
        Binding("ctrl+q", "quit",          "종료",    show=True),
        Binding("ctrl+s", "open_settings", "설정",    show=True),
        Binding("ctrl+p", "open_persona",  "persona", show=True),
        Binding("ctrl+m", "open_memory",   "memory",  show=True),
        Binding("ctrl+n", "new_session",   "새 세션", show=True),
        Binding("l",      "toggle_log",    "log",     show=True),
        Binding("tab",    "focus_next",    "패널전환", show=True),
        Binding("escape", "focus_input",   "",        show=False),
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
        self._ps = ProcessState()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Sidebar()
        with Static(id="chat-pane"):
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
        """단계 전환 — 메인 스레드에서 호출."""
        self._ps.transition(stage, detail)
        self.query_one(StatusBar).refresh()
        self.query_one(ProcessLog).append_step()

    def _step_from_thread(self, stage: Stage, detail: str = "") -> None:
        """백그라운드 스레드에서 단계 전환."""
        self.call_from_thread(self._step, stage, detail)

    def _reset_process(self) -> None:
        self._ps.reset()
        self.query_one(StatusBar).refresh()
        pl = self.query_one(ProcessLog)
        pl.set_state(self._ps)

    # ------------------------------------------------------------------
    # Header / Keybind
    # ------------------------------------------------------------------
    def _update_header(self) -> None:
        cfg = self._settings
        backend = cfg.get("backend", "ollama")
        model = cfg.get("openai_model") if backend == "openai" else cfg.get("model", "")
        model_short = (model or "")[:24]
        persona_name = self._persona.name
        hdr = self.query_one("#chat-header", Static)
        hdr.update(
            f"znc  "
            f"[dim]|[/]  [bold #58a6ff]{persona_name}[/]  "
            f"[dim]|[/]  [dim]{backend}:{model_short}[/]  "
            f"[dim]|[/]  "
            f"session: [dim]{self._session.name if self._session else 'none'}[/]"
        )

    def _update_keybind_bar(self) -> None:
        bar = self.query_one("#keybind-bar", Static)
        bar.update(
            "[bold #58a6ff]^N[/] new  "
            "[bold #58a6ff]^S[/] settings  "
            "[bold #58a6ff]^P[/] persona  "
            "[bold #58a6ff]^M[/] memory  "
            "[bold #58a6ff]L[/] log  "
            "[bold #58a6ff]Tab[/] panel  "
            "[bold #58a6ff]^Q[/] quit  "
            "  /search /remember /forget /persona /clear /save /export"
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
    def _start_new_session(self, project: str | None = None) -> None:
        system = None
        if project:
            proj = ProjectRepository.get(project)
            system = proj.system_prompt if proj else None
        self._session = Session(
            name="__unsaved__",
            project=project,
            system_prompt=system,
        )
        self.query_one(MessageView).clear()
        self._reset_process()
        self._update_header()

    def _load_session(self, name: str, project: str | None) -> None:
        if project:
            sd = ProjectRepository.sessions_dir(project)
        else:
            ensure_dirs()
            sd = SESSIONS_DIR
        try:
            self._session = Session.load(sd, name)
            mv = self.query_one(MessageView)
            mv.render_history(self._session.messages, self._ai_name)
            self._reset_process()
            self._update_header()
        except FileNotFoundError:
            self._write_status(f"session not found: {name}", "red")

    def _save_session(self, name: str | None = None) -> None:
        if not self._session:
            return
        if name:
            self._session.name = name
        elif self._session.name == "__unsaved__":
            from znc.cli.utils import generate_default_session_name
            self._session.name = generate_default_session_name()

        if self._session.project:
            sd = ProjectRepository.sessions_dir(self._session.project)
        else:
            ensure_dirs()
            sd = SESSIONS_DIR
        path = self._session.save(sd)
        self._write_status(f"saved: {path}", "green")
        self._update_header()
        self.query_one(Sidebar).refresh_lists()

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
        parts = []
        mem_ctx = build_memory_context()
        effective = self._persona.build_system_prompt(
            extra_context="\n".join(filter(None, [mem_ctx, extra]))
        )
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

        self._reset_process()
        self._step(Stage.LOADING)

        msg = Message(role="user", content=user_text)
        self._session.append(msg)
        self.query_one(MessageView).append_message(msg, self._ai_name)

        # 메모리 컨텍스트 조회
        mem_items = load_all_memory()
        if mem_items:
            self._step(Stage.MEMORY, f"{len(mem_items)} items")

        prompt = self._build_prompt()
        system = self._build_system()
        self._stream_buffer = ""
        self._streaming = True

        mv = self.query_one(MessageView)

        self._step(Stage.THINKING, "waiting for first token")
        mv.begin_assistant_turn(self._ai_name)

        first_token_received = False

        def run_stream():
            nonlocal first_token_received
            try:
                for token in self._backend.stream(prompt, system_prompt=system):
                    if not first_token_received:
                        first_token_received = True
                        self._step_from_thread(Stage.GENERATING)
                    self._stream_buffer += token
                    self.call_from_thread(mv.append_token, token)
            except Exception as e:
                self._step_from_thread(Stage.ERROR, str(e))
                self.call_from_thread(self._write_status, f"stream error: {e}", "red")
            finally:
                self.call_from_thread(self._on_stream_done)

        threading.Thread(target=run_stream, daemon=True).start()

    def _on_stream_done(self) -> None:
        self._streaming = False
        content = self._stream_buffer
        self._stream_buffer = ""
        if self._session and content:
            self._session.append(Message(role="assistant", content=content))
            if self._backend:
                def _extract():
                    extract_and_save_auto(content, self._backend)
                threading.Thread(target=_extract, daemon=True).start()
        self._step(Stage.DONE)
        self.query_one(MessageView).write("")
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
        self._stream_buffer = ""
        self._streaming = True
        prompt = self._build_prompt() + f"\n[context]\n{text}\n{self._ai_name}:"
        system = self._build_system()
        mv = self.query_one(MessageView)

        self._step(Stage.THINKING, "waiting for first token")
        mv.begin_assistant_turn(self._ai_name)

        first_token_received = False

        def run_stream():
            nonlocal first_token_received
            try:
                for token in self._backend.stream(prompt, system_prompt=system):
                    if not first_token_received:
                        first_token_received = True
                        self._step_from_thread(Stage.GENERATING)
                    self._stream_buffer += token
                    self.call_from_thread(mv.append_token, token)
            except Exception as e:
                self._step_from_thread(Stage.ERROR, str(e))
                self.call_from_thread(self._write_status, f"error: {e}", "red")
            finally:
                self.call_from_thread(self._on_stream_done)

        threading.Thread(target=run_stream, daemon=True).start()

    def _do_export(self, filepath: str) -> None:
        if not self._session:
            self._write_status("no active session", "red")
            return
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"znc — Chat Export\n{'─' * 44}\n")
                f.write(f"Session : {self._session.name}\n\n")
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
        self._start_new_session(event.project)

    def on_sidebar_new_project_requested(self, event: Sidebar.NewProjectRequested) -> None:
        self.action_new_project()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_new_session(self) -> None:
        self._start_new_session()

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
        if self._session and self._session.messages and self._session.name != "__unsaved__":
            self._save_session()
        self.exit()
