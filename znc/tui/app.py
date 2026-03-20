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
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, Static

from znc.backends.base import BaseBackend
from znc.core.config import SESSIONS_DIR, ensure_dirs, load_settings
from znc.core.i18n import ui as _ui
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
from znc.tui.screens.confirm import ConfirmScreen
from znc.tui.screens.command_palette import CommandPaletteScreen
from znc.tui.screens.about import AboutScreen
from znc.tui.screens.message_saver import MessageSaverScreen
from znc.tui.screens.move_session import MoveSessionScreen
from znc.tui.widgets.chat_view import MessageView
from znc.tui.widgets.input_bar import InputBar
from znc.tui.widgets.process_log import ProcessLog
from znc.tui.widgets.sidebar import Sidebar
from znc.tui.widgets.status_bar import StatusBar

CSS_PATH = Path(__file__).parent / "znc.tcss"

_UNSAVED = "__unsaved__"
_TEMP    = "__temp__"


class BackgroundStream:
    """세션에 연결된 백그라운드 스트림.

    세션 전환 시 스트림을 중단하지 않고 백그라운드에서 계속 실행한다.
    UI 가 연결(attach)된 동안에는 토큰이 MessageView 에 실시간 표시되고,
    분리(detach)된 동안에는 버퍼에만 쌓인다.
    세션에 돌아오면 버퍼를 재생(replay)하고 UI 를 재연결한다.

    스레드 안전성:
      buffer, ui_active 의 읽기/쓰기는 _lock 으로 보호한다.
      call_from_thread 는 Textual 메인 스레드에서 UI 를 업데이트한다.
    """

    def __init__(self, session_key: str, ai_name: str) -> None:
        self.session_key = session_key
        self.ai_name = ai_name
        self.buffer: str = ""          # 누적 토큰
        self.completed: bool = False   # 스트림 완료
        self.cancelled: bool = False   # 사용자가 중단
        self.error: str | None = None
        self._ui_active: bool = True   # UI 연결 여부
        self._lock = threading.Lock()

    # ── 외부 제어 ────────────────────────────────────────────
    def attach_ui(self) -> None:
        with self._lock:
            self._ui_active = True

    def detach_ui(self) -> None:
        with self._lock:
            self._ui_active = False

    @property
    def ui_active(self) -> bool:
        with self._lock:
            return self._ui_active

    def get_buffer_snapshot(self) -> str:
        with self._lock:
            return self.buffer

    def add_token(self, token: str) -> None:
        """토큰 추가 — 버퍼에 쌓음. UI 업데이트는 호출자가 담당."""
        with self._lock:
            self.buffer += token


class ZncApp(App):
    """znc TUI 메인 앱."""

    CSS_PATH = CSS_PATH

    # Textual 기본 커맨드 팔레트(Ctrl+P)를 비활성화.
    # 활성 시 Ctrl+P 가 팔레트로 가로채여 persona 팝업이 열리지 않음.
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        Binding("ctrl+n", "new_session",        "새 채팅",   show=True,  priority=True),
        Binding("ctrl+t", "temp_session",       "임시 채팅", show=True,  priority=True),
        Binding("ctrl+s", "open_settings",      "설정",      show=True,  priority=True),
        Binding("ctrl+p", "open_persona",       "persona",   show=True,  priority=True),
        Binding("ctrl+e", "open_memory",        "memory",    show=True,  priority=True),
        Binding("ctrl+b", "toggle_sidebar",     "사이드바",  show=True,  priority=True),
        Binding("ctrl+l", "toggle_log",         "log",       show=True,  priority=True),
        Binding("ctrl+w", "save_message",       "save msg",  show=True,  priority=True),
        Binding("ctrl+g", "open_about",         "about",     show=True,  priority=True),
        Binding("f1",     "open_command_palette","help",     show=True,  priority=True),
        Binding("f2",     "readline_input",      "한/영입력", show=True,  priority=True),
        Binding("tab",    "focus_next",         "패널전환",  show=True),
        Binding("ctrl+q", "quit",               "종료",      show=True,  priority=True),
        Binding("escape", "escape_or_stop",        "",          show=False),
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
        self._stream_id: int = 0   # 수동 중단(Esc/Stop)에만 증가
        self._bg_streams: dict[str, BackgroundStream] = {}  # 세션별 백그라운드 스트림
        self._ps = ProcessState()
        self._title_generated = False  # 현재 세션 제목 생성 완료 여부

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        with Horizontal(id="main-layout"):
            yield Sidebar()
            with Vertical(id="chat-pane"):
                yield Static(id="chat-header")
                yield Static(id="temp-banner")
                yield MessageView()
                yield ProcessLog(self._ps)
                yield StatusBar(self._ps)
                yield InputBar()
        yield Static(id="keybind-bar")

    def on_mount(self) -> None:
        self._reload_backend()
        self._update_header()
        self._update_keybind_bar()
        # 저장된 테마 적용
        theme = self._settings.get("theme", "dark")
        self.dark = (theme == "dark")
        self.query_one(InputBar).focus_input()

    # ------------------------------------------------------------------
    # ProcessState helpers
    # ------------------------------------------------------------------
    def _step(self, stage: Stage, detail: str = "") -> None:
        self._ps.transition(stage, detail)
        self.query_one(StatusBar).refresh()
        pl = self.query_one(ProcessLog)
        pl.append_step()
        # 활성 단계 진입/이탈 시 애니메이션 상태 갱신
        pl._maybe_start_anim()

    def _step_from_thread(self, stage: Stage, detail: str = "") -> None:
        self.call_from_thread(self._step, stage, detail)

    def _add_sub(self, item: str) -> None:
        """현재 단계에 세부 항목 추가 (메인 스레드)."""
        self._ps.add_sub_to_last(item)
        self.query_one(ProcessLog).refresh_last_step()

    def _add_sub_from_thread(self, item: str) -> None:
        self.call_from_thread(self._add_sub, item)

    def _update_detail(self, detail: str) -> None:
        """현재 단계 detail 갱신."""
        self._ps.update_last_detail(detail)
        self.query_one(StatusBar).refresh()

    def _reset_process(self) -> None:
        self._ps.reset()
        self.query_one(StatusBar).refresh()
        self.query_one(ProcessLog).set_state(self._ps)

    # ------------------------------------------------------------------
    # Header / Keybind / Temp banner
    # ------------------------------------------------------------------
    def _update_temp_banner(self) -> None:
        """임시 채팅 여부에 따라 배너와 chat-pane 클래스 갱신."""
        is_temp = bool(self._session and self._session.is_temp)
        banner = self.query_one("#temp-banner", Static)
        pane = self.query_one("#chat-pane", Vertical)
        lang = self._settings.get("lang", "ko")

        if is_temp:
            msg = (
                "임시 채팅 — 이 대화는 저장되지 않습니다"
                if lang == "ko"
                else "Temporary chat — This conversation won't be saved"
            )
            banner.update(f"  ⚡  {msg}")
            pane.add_class("--temp")
        else:
            banner.update("")
            pane.remove_class("--temp")

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
        """DOS Commander 스타일 하단 키바인딩 바. 언어에 따라 형식 변경."""
        lang = self._settings.get("lang", "ko")
        K  = "bold #0d1117 on #58a6ff"
        D  = "dim #8b949e"

        def item(key: str) -> str:
            label = _ui(lang, key)
            if lang == "ko":
                # Korean: 설명(^Key) — 텍스트 강조 없이 dim
                return f"[{D}]{label}[/]"
            else:
                # English: [^Key] Desc — 키 부분 하이라이트
                parts = label.split(" ", 1)
                if len(parts) == 2:
                    return f"[{K}]{parts[0]}[/][{D}]{parts[1]}[/]"
                return f"[{D}]{label}[/]"

        SEP = f"[{D}]  [/]"

        row1 = SEP.join([
            item("kbar_save"), item("kbar_new"), item("kbar_temp"),
            item("kbar_panel"), item("kbar_settings"), item("kbar_persona"),
            item("kbar_memory"), item("kbar_log"), item("kbar_about"),
            item("kbar_help"), item("kbar_f2"), item("kbar_focus"), item("kbar_quit"),
        ])

        from znc.version import VERSION, BUILD
        ver_str = f"[dim #484f58]znc v{VERSION} #{BUILD}[/]"

        sb_items = SEP.join([
            item("kbar_sb_new"), item("kbar_sb_temp"), item("kbar_sb_proj"),
            item("kbar_sb_search"), item("kbar_sb_del"), item("kbar_sb_rename"),
            item("kbar_sb_esc"),
        ])
        row2 = f"[dim #484f58]{_ui(lang, 'kbar_sb_prefix')}[/]  {sb_items}"

        self.query_one("#keybind-bar", Static).update(
            f"{row1}  {ver_str}\n{row2}"
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
    # BackgroundStream 헬퍼
    # ------------------------------------------------------------------
    def _session_key(self, session) -> str:
        return f"{session.project or ''}:{session.name}"

    def _detach_current_stream(self) -> None:
        """현재 세션의 스트림 UI를 분리한다 (스트림은 계속 실행)."""
        if self._session:
            key = self._session_key(self._session)
            bg = self._bg_streams.get(key)
            if bg and not bg.completed and not bg.cancelled:
                bg.detach_ui()
        # UI 레벨 정리
        self._streaming = False
        self._stream_buffer = ""
        try:
            self.query_one(InputBar).streaming = False
            self.query_one(MessageView).end_streaming()
        except Exception:
            pass

    def _reattach_stream(self, session) -> bool:
        """세션에 활성 bg_stream 이 있으면 UI 를 재연결한다.
        재연결 성공 시 True, 없으면 False 반환."""
        key = self._session_key(session)
        bg = self._bg_streams.get(key)
        if not bg or bg.completed or bg.cancelled:
            if bg:
                self._bg_streams.pop(key, None)
            return False

        mv = self.query_one(MessageView)
        mv.render_history(session.messages, self._ai_name)
        mv.begin_assistant_turn(bg.ai_name)

        # 누적 버퍼 즉시 재생
        snapshot = bg.get_buffer_snapshot()
        if snapshot:
            mv.append_token(snapshot)

        bg.attach_ui()
        self._streaming = True
        self.query_one(InputBar).streaming = True
        self._step(Stage.GENERATING, "reconnecting stream...")
        return True

    def _on_bg_stream_done(self, bg, target_session) -> None:
        self._on_bg_stream_done_with_tokens(bg, target_session, 0)

    def _on_bg_stream_done_with_tokens(self, bg, target_session, token_count: int) -> None:
        """스트림 완료 콜백 — 토큰 수 포함."""
        content = bg.buffer
        key = bg.session_key
        self._bg_streams.pop(key, None)

        # 내용 저장 (수동 중단 시에는 이미 저장됨)
        if content and not bg.cancelled and target_session:
            self._save_to_session(content, target_session)

        # 현재 보고 있는 세션이면 UI 마무리
        if self._session and self._session_key(self._session) == key:
            self._streaming = False
            try:
                self.query_one(InputBar).streaming = False
            except Exception:
                pass
            # Done 단계 + sub_item 에 요약 정보
            elapsed = self._ps.total_elapsed
            self._step(Stage.DONE)
            if token_count:
                self._add_sub(f"{token_count} tokens  ·  {elapsed:.1f}s  ·  {token_count/elapsed:.0f} t/s")
            try:
                self.query_one(MessageView).end_streaming()
                self.query_one(InputBar).focus_input()
            except Exception:
                pass
            if not self._title_generated:
                self._maybe_generate_title()

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
        # 현재 스트림 UI만 분리 (스트림은 백그라운드 계속)
        self._detach_current_stream()

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
        mv.clear()
        self._reset_process()
        self._update_header()
        self._update_temp_banner()
        try:
            self.query_one(InputBar).streaming = False
        except Exception:
            pass

    def _load_session(self, name: str, project: str | None) -> None:
        # 현재 스트림 UI만 분리 (스트림은 백그라운드 계속)
        self._detach_current_stream()

        try:
            self._session = Session.load(self._sessions_dir(project), name)
            self._title_generated = bool(self._session.title)

            # 이 세션에 활성 백그라운드 스트림이 있으면 UI 재연결
            if not self._reattach_stream(self._session):
                # 스트림 없음 — 일반 히스토리 렌더링
                mv = self.query_one(MessageView)
                mv.render_history(self._session.messages, self._ai_name)

            self._reset_process()
            self._update_header()
            self._update_temp_banner()
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

        # ── 최신 정보 필요 여부 자동 감지 ──────────────────────────
        from znc.core.search_intent import detect_search_intent
        needs_search, reason = detect_search_intent(user_text)
        if needs_search:
            self._write_status(f"최신 정보 자동 검색 중 ({reason})", "cyan")
            self._do_web_search(user_text, freshness="w", auto=True)
            return
        # ────────────────────────────────────────────────────────────

        mem_items = load_all_memory()
        if mem_items:
            self._step(Stage.MEMORY, f"{len(mem_items)} items")
            for m in mem_items[:5]:   # 최대 5개 표시
                self._add_sub(f"{m.key}: {m.value}")
            if len(mem_items) > 5:
                self._add_sub(f"... +{len(mem_items)-5} more")

        prompt = self._build_prompt()
        system = self._build_system()
        self._stream_buffer = ""
        self._streaming = True

        # 이 스트림의 고유 ID — 수동 중단(Esc/Stop)에만 사용
        self._stream_id += 1
        my_stream_id = self._stream_id
        target_session = self._session

        # BackgroundStream 생성 및 등록
        key = self._session_key(target_session)
        bg = BackgroundStream(key, self._ai_name)
        bg.attach_ui()
        self._bg_streams[key] = bg

        mv = self.query_one(MessageView)
        self._step(Stage.THINKING, "waiting for first token")
        mv.begin_assistant_turn(self._ai_name)
        self.query_one(InputBar).streaming = True
        first_token = False
        token_count = 0

        def run_stream():
            nonlocal first_token, token_count
            try:
                for token in self._backend.stream(prompt, system_prompt=system):
                    if self._stream_id != my_stream_id or bg.cancelled:
                        break
                    bg.add_token(token)
                    token_count += 1
                    if not first_token:
                        first_token = True
                        self._step_from_thread(Stage.GENERATING)
                    if bg.ui_active:
                        self.call_from_thread(mv.append_token, token)
                    # 50토큰마다 생성 진행 상태 갱신
                    if token_count % 50 == 0 and bg.ui_active:
                        self.call_from_thread(
                            self._update_detail, f"{token_count} tokens"
                        )
            except Exception as e:
                bg.error = str(e)
                if bg.ui_active:
                    self._step_from_thread(Stage.ERROR, str(e))
                    self.call_from_thread(self._write_status, f"stream error: {e}", "red")
            finally:
                bg.completed = True
                self.call_from_thread(
                    self._on_bg_stream_done_with_tokens, bg, target_session, token_count
                )

        threading.Thread(target=run_stream, daemon=True).start()

    def _save_to_session(self, content: str, session) -> None:
        """AI 응답을 지정 세션에 저장하고 부가 처리를 수행한다.
        세션 전환으로 스트림이 중단된 경우에도 올바른 세션에 저장하기 위해
        _on_stream_done 과 분리된 헬퍼로 구현.
        """
        session.append(Message(role="assistant", content=content))
        if not session.is_temp:
            try:
                sd = (ProjectRepository.sessions_dir(session.project)
                      if session.project else SESSIONS_DIR)
                ensure_dirs()
                session.save(sd)
            except Exception:
                pass
        # 자동 메모리 추출 (현재 세션 응답에만 적용)
        if self._backend and session is self._session:
            def _extract():
                extract_and_save_auto(content, self._backend)
            threading.Thread(target=_extract, daemon=True).start()
        # 사이드바 갱신 (현재 세션이면)
        if session is self._session:
            try:
                self.query_one(Sidebar).refresh_lists()
            except Exception:
                pass

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
                self._write_status("usage: /search <query>  [옵션: --week --day --month]")
                return True
            # --week / --day / --month 플래그 파싱
            freshness = ""
            query = arg
            for flag, code in (("--week", "w"), ("--day", "d"), ("--month", "m")):
                if flag in query:
                    freshness = code
                    query = query.replace(flag, "").strip()
            self._do_web_search(query, freshness=freshness)
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
        if cmd == "/about":
            self.action_open_about()
            return True
        if cmd == "/delete":
            self._delete_current_session()
            return True
        if cmd in ("/save-msg", "/savemsg"):
            self.action_save_message()
            return True
        return False

    def _do_web_search(self, query: str, freshness: str = "", auto: bool = False) -> None:
        """웹 검색 + 크롤링 → 컨텍스트 삽입.

        auto=True 이면 사용자 메시지가 이미 세션에 추가된 상태.
        freshness: ""=전체  "d"=하루  "w"=1주  "m"=1달
        """
        if not self._session:
            self._start_new_session()

        if not auto:
            # /search 슬래시 명령 경로: 세션/프로세스 초기화
            self._reset_process()
            self._step(Stage.LOADING)

        engines = self._settings.get("search_engines", ["ddg", "naver"])
        serper_key = self._settings.get("google_serper_key", "")
        engine_label = "+".join(engines)
        freshness_label = {"d": "1일", "w": "1주", "m": "1달"}.get(freshness, "전체")
        self._step(Stage.SEARCH, f'"{query[:40]}"  [{engine_label}]  [{freshness_label}]')

        from datetime import datetime as _dt
        search_date = _dt.now().strftime("%Y-%m-%d %H:%M")

        def run():
            def progress(url: str, done: int, total: int) -> None:
                if url:
                    domain = url.split("/")[2] if url.count("/") >= 2 else url
                    self._step_from_thread(Stage.CRAWL, domain)
            results, context = search_and_crawl(
                query,
                engines=engines,
                google_serper_key=serper_key,
                freshness=freshness,
                progress_callback=progress,
            )
            if not context:
                self._step_from_thread(Stage.ERROR, "no results found")
                self.call_from_thread(self._write_status, "no results found", "red")
                return
            if self._session:
                # 검색 결과 제목을 SEARCH 단계 sub_item 으로 추가
                for r in results[:5]:
                    title_short = r.title[:55] if r.title else r.url[:55]
                    self.call_from_thread(self._add_sub, f"{title_short}")
                dated_context = f"[검색 날짜: {search_date}]\n{context}"
                prompt = (
                    f"[web search context]\n{dated_context}\n\n"
                    f"위 검색 결과를 바탕으로 '{query}' 에 대해 답해줘."
                )
                self.call_from_thread(self._send_message_with_context, prompt)

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
        target_session = self._session

        key = self._session_key(target_session)
        bg = BackgroundStream(key, self._ai_name)
        bg.attach_ui()
        self._bg_streams[key] = bg

        prompt = self._build_prompt() + f"\n[context]\n{text}\n{self._ai_name}:"
        system = self._build_system()
        mv = self.query_one(MessageView)

        self._step(Stage.THINKING, "waiting for first token")
        mv.begin_assistant_turn(self._ai_name)
        self.query_one(InputBar).streaming = True
        first_token = False

        def run_stream():
            nonlocal first_token
            try:
                for token in self._backend.stream(prompt, system_prompt=system):
                    if self._stream_id != my_stream_id or bg.cancelled:
                        break
                    bg.add_token(token)
                    if not first_token:
                        first_token = True
                        self._step_from_thread(Stage.GENERATING)
                    if bg.ui_active:
                        self.call_from_thread(mv.append_token, token)
            except Exception as e:
                bg.error = str(e)
                if bg.ui_active:
                    self._step_from_thread(Stage.ERROR, str(e))
                    self.call_from_thread(self._write_status, f"error: {e}", "red")
            finally:
                bg.completed = True
                self.call_from_thread(self._on_bg_stream_done, bg, target_session)

        self._step(Stage.THINKING, "waiting for first token")
        mv.begin_assistant_turn(self._ai_name)
        self.query_one(InputBar).streaming = True
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
                        self.query_one(InputBar).streaming = False
                        partial = self._stream_buffer
                        self._stream_buffer = ""
                        if partial and target_session:
                            self._save_to_session(partial, target_session)
                self.call_from_thread(on_done)

        threading.Thread(target=run_stream, daemon=True).start()

    def _delete_current_session(self) -> None:
        """현재 활성 세션 삭제 (확인 후)."""
        if not self._session or self._session.name in (_UNSAVED, _TEMP):
            self._write_status("저장된 세션이 없습니다.", "yellow")
            return
        if self._session.is_temp:
            self._write_status("임시 세션은 저장되지 않았습니다.", "yellow")
            return
        name = self._session.name

        def _do_delete(confirmed: bool) -> None:
            if not confirmed:
                return
            sd = self._sessions_dir()
            path = os.path.join(sd, f"{name}.json")
            if os.path.exists(path):
                os.remove(path)
            self._session = None
            self.query_one(MessageView).clear()
            self._update_header()
            self.query_one(Sidebar).refresh_lists()
            self._write_status(f"deleted: {name}", "green")

        self.push_screen(
            ConfirmScreen(f"'{name}' 세션을 삭제하시겠습니까?", "세션 삭제"),
            _do_delete,
        )
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

    def on_sidebar_project_delete_requested(
        self, event: Sidebar.ProjectDeleteRequested
    ) -> None:
        def _do(confirmed: bool) -> None:
            if not confirmed:
                return
            from znc.core.repository import ProjectRepository
            ProjectRepository.delete(event.name)
            if self._session and self._session.project == event.name:
                self._session = None
                self.query_one(MessageView).clear()
                self._update_header()
            self.query_one(Sidebar).refresh_lists()
        self.push_screen(
            ConfirmScreen(f"'{event.name}' 프로젝트와 모든 세션을 삭제하시겠습니까?", "프로젝트 삭제"),
            _do,
        )

    def on_sidebar_project_rename_requested(
        self, event: Sidebar.ProjectRenameRequested
    ) -> None:
        def _do(new_name: str | None) -> None:
            if not new_name:
                return
            import os, json, shutil
            from znc.core.config import get_project_dir
            old_dir = get_project_dir(event.name)
            new_dir = get_project_dir(new_name)
            if os.path.exists(new_dir):
                self._write_status(f"already exists: {new_name}", "red")
                return
            os.rename(old_dir, new_dir)
            # project.json 내 name 필드 갱신
            meta = os.path.join(new_dir, "project.json")
            if os.path.exists(meta):
                with open(meta, "r", encoding="utf-8") as f:
                    d = json.load(f)
                d["name"] = new_name
                with open(meta, "w", encoding="utf-8") as f:
                    json.dump(d, f, indent=2, ensure_ascii=False)
            if self._session and self._session.project == event.name:
                self._session.project = new_name
                self._update_header()
            self.query_one(Sidebar).refresh_lists()
        self.push_screen(RenameSessionScreen(event.name), _do)

    def on_sidebar_session_rename_requested(
        self, event: Sidebar.SessionRenameRequested,
    ) -> None:
        """세션 이름 변경 — 표시 제목(title)을 변경, 파일명은 유지."""
        lang = self._settings.get("lang", "ko")

        def callback(new_title: str | None) -> None:
            if not new_title or new_title == event.display:
                return
            sd = (ProjectRepository.sessions_dir(event.project)
                  if event.project else self._sessions_dir())
            path = os.path.join(sd, f"{event.name}.json")
            if not os.path.exists(path):
                return
            import json as _json
            with open(path, "r", encoding="utf-8") as f:
                d = _json.load(f)
            d["title"] = new_title
            with open(path, "w", encoding="utf-8") as f:
                _json.dump(d, f, indent=2, ensure_ascii=False)
            if self._session and self._session.name == event.name:
                self._session.title = new_title
                self._update_header()
            self.query_one(Sidebar).refresh_lists()
            self._write_status(_ui(lang, "renamed", name=new_title), "green")

        # 현재 표시 제목을 초기값으로 전달
        self.push_screen(RenameSessionScreen(event.display), callback)

    def on_sidebar_session_move_requested(
        self, event: Sidebar.SessionMoveRequested,
    ) -> None:
        """세션을 다른 프로젝트로 이동."""
        lang = self._settings.get("lang", "ko")

        def callback(dest: str | None) -> None:
            if dest is None:
                return  # 취소
            # 출발지 디렉터리
            src_sd = (ProjectRepository.sessions_dir(event.from_project)
                      if event.from_project else SESSIONS_DIR)
            src_path = os.path.join(src_sd, f"{event.name}.json")
            if not os.path.exists(src_path):
                self._write_status(f"session not found: {event.name}", "red")
                return
            # 목적지 디렉터리
            if dest:
                dst_sd = ProjectRepository.sessions_dir(dest)
            else:
                ensure_dirs()
                dst_sd = SESSIONS_DIR
            os.makedirs(dst_sd, exist_ok=True)
            dst_path = os.path.join(dst_sd, f"{event.name}.json")
            # 파일 이동 + project 필드 업데이트
            import json as _json, shutil
            with open(src_path, "r", encoding="utf-8") as f:
                d = _json.load(f)
            d["project"] = dest or None
            with open(dst_path, "w", encoding="utf-8") as f:
                _json.dump(d, f, indent=2, ensure_ascii=False)
            if src_path != dst_path:
                os.remove(src_path)
            # 현재 세션이면 project 업데이트
            if self._session and self._session.name == event.name:
                self._session.project = dest or None
                self._update_header()
            self.query_one(Sidebar).refresh_lists()
            self._write_status(_ui(lang, "moved", name=event.name), "green")

        self.push_screen(
            MoveSessionScreen(event.name, event.from_project, lang=lang),
            callback,
        )

    def on_sidebar_session_delete_requested(
        self, event: Sidebar.SessionDeleteRequested,
    ) -> None:
        def _do_delete(confirmed: bool) -> None:
            if not confirmed:
                return
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

        self.push_screen(
            ConfirmScreen(f"'{event.name}' 세션을 삭제하시겠습니까?", "세션 삭제"),
            _do_delete,
        )

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
                # 언어 변경 → 사이드바 레이블 갱신
                new_lang = cfg.get("lang", "ko")
                try:
                    self.query_one(Sidebar).set_lang(new_lang)
                except Exception:
                    pass
                # 테마 변경
                theme = cfg.get("theme", "dark")
                self.dark = (theme == "dark")
        self.push_screen(SettingsScreen(), callback)

    def action_open_persona(self) -> None:
        def callback(name: str | None) -> None:
            if name:
                p = load_persona(name)
                if p:
                    self._persona = p
                    self._update_header()
        self.push_screen(PersonaScreen(self._persona.name), callback)

    def action_save_message(self) -> None:
        """현재 세션의 메시지 선택 → 파일 저장 팝업."""
        if not self._session or not self._session.messages:
            self._write_status("no messages to save", "yellow")
            return
        from znc.core.config import ZNC_DIR
        save_dir = os.path.join(ZNC_DIR, "output")
        os.makedirs(save_dir, exist_ok=True)

        def callback(filepath: str | None) -> None:
            if filepath:
                self._write_status(f"saved: {filepath}", "green")

        self.push_screen(
            MessageSaverScreen(
                messages=self._session.messages,
                ai_name=self._ai_name,
                save_dir=save_dir,
                lang=self._settings.get("lang", "ko"),
            ),
            callback,
        )

    def action_open_memory(self) -> None:
        self.push_screen(MemoryScreen())

    def action_open_about(self) -> None:
        self.push_screen(AboutScreen(self._settings))

    def action_open_command_palette(self) -> None:
        self.push_screen(CommandPaletteScreen())

    async def action_readline_input(self) -> None:
        """
        F2: 시스템 readline 으로 입력 — 완전한 한국어 IME 호환.

        Textual 은 raw 모드로 키를 처리해 IME 와 충돌할 수 있다.
        run_in_terminal() 로 TUI 를 잠깐 내려놓고 cooked 모드 (readline) 에서
        입력받으면 시스템과 완전히 동일하게 동작한다.

        사용법:
          F2 → TUI 잠깐 사라짐 → 터미널에서 자유롭게 입력 (한국어 IME 완전 지원)
              → Enter 로 전송 / Ctrl+D 취소 / \\ 줄 연속
        """
        lang = self._settings.get("lang", "ko")
        if lang == "ko":
            hint = "  메시지 입력 (Enter=전송  Ctrl+D=취소  줄끝\\=줄바꿈)"
        else:
            hint = "  Type message  (Enter=send  Ctrl+D=cancel  \\=newline)"

        result: list[str | None] = []

        def _get_input() -> None:
            try:
                # readline 활성화 (방향키, 히스토리 지원)
                try:
                    import readline as _rl  # noqa
                except ImportError:
                    pass

                import sys
                sys.stdout.write("\n" + hint + "\n")
                sys.stdout.flush()

                lines: list[str] = []
                while True:
                    try:
                        line = input("> ")
                    except EOFError:
                        break
                    # 줄 연속: 끝이 \\
                    if line.endswith("\\"):
                        lines.append(line[:-1])
                        continue
                    lines.append(line)
                    break   # 단일 Enter = 전송

                text = "\n".join(lines).strip()
                result.append(text if text else None)
            except KeyboardInterrupt:
                result.append(None)

        await self.run_in_terminal(_get_input)

        text = result[0] if result else None
        if text:
            import unicodedata
            text = unicodedata.normalize("NFC", text)
            self._send_message(text)

    def on_static_click(self, event) -> None:
        """하단 바 클릭 → 커맨드 팔레트 열기."""
        widget = event.widget
        if getattr(widget, "id", "") == "keybind-bar":
            self.action_open_command_palette()

    def action_toggle_log(self) -> None:
        pl = self.query_one(ProcessLog)
        visible = pl.toggle()
        self.query_one(StatusBar).set_log_visible(visible)

    def action_toggle_sidebar(self) -> None:
        sb = self.query_one(Sidebar)
        if "--hidden" in sb.classes:
            sb.remove_class("--hidden")
        else:
            sb.add_class("--hidden")
            # 사이드바 숨김 시 채팅창으로 포커스 이동
            self.query_one(InputBar).focus_input()

    def action_focus_input(self) -> None:
        self.query_one(InputBar).focus_input()

    def action_escape_or_stop(self) -> None:
        """스트리밍 중이면 중단, 아니면 입력창 포커스."""
        if self._streaming:
            self.action_stop_streaming()
        else:
            self.query_one(InputBar).focus_input()

    def action_stop_streaming(self) -> None:
        """진행 중인 스트리밍을 즉시 중단한다."""
        if not self._streaming:
            return

        # bg_stream 취소 표시 + 즉시 부분 저장
        if self._session:
            key = self._session_key(self._session)
            bg = self._bg_streams.get(key)
            if bg:
                bg.cancelled = True
                partial = bg.get_buffer_snapshot()
                if partial:
                    self._save_to_session(partial, self._session)

        # 스트림 스레드에 중단 신호
        self._stream_id += 1
        self._streaming = False
        self._stream_buffer = ""
        self._step(Stage.DONE)
        mv = self.query_one(MessageView)
        mv.end_streaming()
        ib = self.query_one(InputBar)
        ib.streaming = False
        ib.focus_input()
        lang = self._settings.get("lang", "ko")
        self._write_status(_ui(lang, "stopped"), "yellow")

    def on_input_bar_stop_requested(self, event: InputBar.StopRequested) -> None:
        self.action_stop_streaming()

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
