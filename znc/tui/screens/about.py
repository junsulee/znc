"""
About 팝업 (Ctrl+I / /about).

znc 버전, 빌드, 백엔드 설정, 기능 목록을 보여준다.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from znc.version import VERSION, BUILD


class AboutScreen(ModalScreen):
    """znc 정보 팝업."""

    BINDINGS = [Binding("escape", "dismiss", "닫기")]

    DEFAULT_CSS = """
    AboutScreen { align: center middle; }
    #about-box {
        background: #161b22;
        border: tall #30363d;
        padding: 1 2;
        width: 58;
        height: auto;
    }
    .ab-logo   { color: #58a6ff; text-style: bold; }
    .ab-ver    { color: #3fb950; }
    .ab-sep    { color: #30363d; height: 1; margin: 1 0; }
    .ab-label  { color: #8b949e; height: 1; }
    .ab-val    { color: #e6edf3; }
    .ab-feat   { color: #8b949e; height: 1; }
    .ab-feat-ok { color: #3fb950; height: 1; }
    .btn-row   { align: center middle; height: 3; margin-top: 1; }
    """

    def __init__(self, settings: dict) -> None:
        super().__init__()
        self._settings = settings

    def compose(self) -> ComposeResult:
        cfg = self._settings
        backend = cfg.get("backend", "ollama")
        if backend == "openai":
            model = cfg.get("openai_model", "gpt-4o")
            server = cfg.get("openai_base_url", "https://api.openai.com/v1")
        else:
            model = cfg.get("model", "—")
            server = cfg.get("server_url", "—")
        engines = "+".join(cfg.get("search_engines", ["ddg", "naver"]))

        with Static(id="about-box"):
            yield Label("znc — 개인용 AI CLI", classes="ab-logo")
            yield Label(
                f"버전 {VERSION}   빌드 #{BUILD}",
                classes="ab-ver",
            )
            yield Label("─" * 46, classes="ab-sep")

            yield Label("BACKEND", classes="ab-label")
            yield Label(f"  {backend}  /  {model}", classes="ab-val")
            yield Label(f"  {server}", classes="ab-val")

            yield Label("─" * 46, classes="ab-sep")

            yield Label("SEARCH", classes="ab-label")
            yield Label(f"  {engines}", classes="ab-val")

            yield Label("─" * 46, classes="ab-sep")

            yield Label("FEATURES", classes="ab-label")
            for feat in [
                "대화 저장 및 프로젝트 단위 관리",
                "Persona 세미튜닝 (시스템 프롬프트 + Few-shot)",
                "장기 메모리 (수동 / AI 자동 추출)",
                "웹 검색 + 크롤링 (DuckDuckGo · Naver · Google)",
                "스트리밍 출력 + 프로세스 상태 표시",
                "임시 채팅 모드",
            ]:
                yield Label(f"  ✓  {feat}", classes="ab-feat-ok")

            yield Label("─" * 46, classes="ab-sep")

            yield Label(
                "F1 커맨드 팔레트  |  Ctrl+G About  |  github.com/junsulee/znc",
                classes="ab-label",
            )

            with Static(classes="btn-row"):
                yield Button("닫기", id="btn-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()
