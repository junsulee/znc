"""
커맨드 팔레트 (F1).

znc 의 모든 단축키와 슬래시 명령어를 한눈에 볼 수 있는 팝업.
검색 필터링 지원.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

_HOTKEYS = [
    ("Ctrl+N",   "새 채팅 시작"),
    ("Ctrl+T",   "임시 채팅 (저장 안 함)"),
    ("Ctrl+B",   "사이드바 숨기기/보이기 토글"),
    ("Ctrl+S",   "설정 팝업"),
    ("Ctrl+P",   "Persona 관리"),
    ("Ctrl+E",   "메모리 관리"),
    ("Ctrl+L",   "프로세스 로그 토글"),
    ("Ctrl+G",   "znc 정보 (About)"),
    ("F1",       "커맨드 팔레트 (이 화면)"),
    ("Tab",      "사이드바 ↔ 채팅창 전환"),
    ("Ctrl+Q",   "종료"),
    ("", ""),
    ("── 사이드바 포커스 시 ──", ""),
    ("n",        "새 세션"),
    ("t",        "임시 세션"),
    ("p",        "새 프로젝트"),
    ("/",        "세션 검색 필터"),
    ("d",        "선택 세션 삭제"),
    ("r",        "선택 세션 이름 변경"),
    ("Esc",      "검색 닫기"),
]

_SLASH = [
    ("/search <query>",         "웹 검색 (옵션: --week --day --month)"),
    ("/search <q> --week",      "최근 1주일 결과만 검색"),
    ("/remember <k>:<v>",       "장기 메모리 저장"),
    ("/forget <key>",           "장기 메모리 삭제"),
    ("/memory",                 "메모리 관리 팝업 열기"),
    ("/persona <name>",         "페르소나 즉시 전환"),
    ("/clear",                  "현재 대화 초기화"),
    ("/save <name>",            "세션 저장"),
    ("/export <file>",          "세션 텍스트 내보내기"),
    ("/settings",               "설정 팝업 열기"),
    ("/about",                  "znc 정보 팝업"),
    ("/delete",                 "현재 세션 삭제"),
]


class CommandPaletteScreen(ModalScreen):
    """F1 커맨드 팔레트."""

    BINDINGS = [Binding("escape", "dismiss", "닫기")]

    DEFAULT_CSS = """
    CommandPaletteScreen { align: center middle; }
    #cp-box {
        background: #161b22;
        border: tall #30363d;
        padding: 1 2;
        width: 80;
        height: 36;
    }
    .cp-title  { color: #58a6ff; text-style: bold; height: 1; }
    .cp-sep    { color: #30363d; height: 1; margin: 1 0; }
    #cp-search { background: #0d1117; border: tall #30363d; color: #e6edf3; margin-bottom: 1; }
    #cp-search:focus { border: tall #58a6ff; }
    #cp-content { height: 1fr; overflow-y: auto; background: #0d1117; padding: 1; }
    .cp-section { color: #58a6ff; text-style: bold; height: 1; margin-top: 1; }
    .cp-row    { height: 1; color: #8b949e; }
    .cp-key    { color: #79c0ff; }
    .cp-desc   { color: #8b949e; }
    .cp-sep-row { color: #30363d; height: 1; }
    .btn-row   { align: center middle; height: 3; margin-top: 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._filter = ""

    def compose(self) -> ComposeResult:
        with Static(id="cp-box"):
            yield Label("커맨드 팔레트  —  F1", classes="cp-title")
            yield Label("─" * 68, classes="cp-sep")
            yield Input(placeholder="검색...", id="cp-search")
            with Static(id="cp-content"):
                yield Label("KEYBOARD SHORTCUTS", classes="cp-section")
                for key, desc in _HOTKEYS:
                    if not key and not desc:
                        yield Label("", classes="cp-sep-row")
                        continue
                    if desc == "":
                        yield Label(key, classes="cp-sep-row")
                        continue
                    # ID 미사용: / 등 특수문자가 포함되면 BadIdentifier 발생
                    yield Label(
                        f"  {key:<16}  {desc}",
                        classes="cp-row",
                    )
                yield Label("", classes="cp-sep-row")
                yield Label("SLASH COMMANDS", classes="cp-section")
                for cmd, desc in _SLASH:
                    yield Label(
                        f"  {cmd:<22}  {desc}",
                        classes="cp-row",
                    )
            with Static(classes="btn-row"):
                yield Button("닫기", id="btn-close")

    def on_mount(self) -> None:
        self.query_one("#cp-search", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        q = event.value.lower()
        for lbl in self.query(".cp-row"):
            text = lbl.renderable if hasattr(lbl, "renderable") else str(lbl._label)
            lbl.display = not q or q in str(text).lower()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss()
