"""
설정 팝업 스크린.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from znc.core.config import load_settings, save_settings

_ENGINE_OPTIONS = [
    ("DuckDuckGo  (기본, API 불필요)", "ddg"),
    ("Naver       (한국어 최적, API 불필요)", "naver"),
    ("Google      (Serper.dev API 키 필요)", "google"),
]


class SettingsScreen(ModalScreen):
    """설정 오버레이 팝업."""

    BINDINGS = [Binding("escape", "dismiss", "닫기")]

    DEFAULT_CSS = """
    SettingsScreen { align: center middle; }
    #settings-box {
        background: #161b22;
        border: tall #30363d;
        padding: 1 2;
        width: 64;
        height: auto;
        max-height: 38;
    }
    .s-title { color: #58a6ff; text-style: bold; height: 1; margin-bottom: 1; }
    .s-sep   { color: #30363d; height: 1; margin: 1 0; }
    .s-label { color: #8b949e; height: 1; margin-top: 1; }
    .s-input { background: #0d1117; border: tall #30363d; color: #e6edf3; margin-bottom: 0; }
    .s-input:focus { border: tall #58a6ff; }
    .s-check { margin: 0; height: 1; }
    .btn-row { align: center middle; height: 3; margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        cfg = load_settings()
        active_engines: list[str] = cfg.get("search_engines", ["ddg", "naver"])

        with Static(id="settings-box"):
            yield Label("settings", classes="s-title")

            # ── AI 백엔드 ──────────────────────────────────
            yield Label("─── AI backend ──────────────────────────────────", classes="s-sep")

            yield Label("backend", classes="s-label")
            yield Select(
                options=[("ollama", "ollama"), ("openai", "openai")],
                value=cfg.get("backend", "ollama"),
                id="cfg-backend",
            )

            yield Label("model  (ollama)", classes="s-label")
            yield Input(value=cfg.get("model", ""), id="cfg-model", classes="s-input")

            yield Label("server url  (ollama)", classes="s-label")
            yield Input(value=cfg.get("server_url", ""), id="cfg-server-url", classes="s-input")

            yield Label("openai api key", classes="s-label")
            yield Input(
                value=cfg.get("openai_api_key", ""),
                id="cfg-openai-key",
                password=True,
                classes="s-input",
            )

            yield Label("openai model", classes="s-label")
            yield Input(value=cfg.get("openai_model", "gpt-4o"), id="cfg-openai-model", classes="s-input")

            yield Label("openai base url", classes="s-label")
            yield Input(
                value=cfg.get("openai_base_url", "https://api.openai.com/v1"),
                id="cfg-openai-base",
                classes="s-input",
            )

            # ── 검색 엔진 ──────────────────────────────────
            yield Label("─── search engines ──────────────────────────────", classes="s-sep")
            yield Label("active engines  (복수 선택 가능, 중복 URL 자동 제거)", classes="s-label")

            for label, engine_id in _ENGINE_OPTIONS:
                yield Checkbox(
                    label,
                    value=(engine_id in active_engines),
                    id=f"eng-{engine_id}",
                    classes="s-check",
                )

            yield Label("google serper api key  (google 체크 시 필요)", classes="s-label")
            yield Input(
                value=cfg.get("google_serper_key", ""),
                id="cfg-serper-key",
                password=True,
                classes="s-input",
                placeholder="serper.dev 무료 2500회/월",
            )

            # ── 기타 ───────────────────────────────────────
            yield Label("─── general ─────────────────────────────────────", classes="s-sep")

            yield Label("ai name", classes="s-label")
            yield Input(value=cfg.get("ai_name", "znc"), id="cfg-ai-name", classes="s-input")

            yield Label("language", classes="s-label")
            yield Select(
                options=[("ko", "ko"), ("en", "en")],
                value=cfg.get("lang", "ko"),
                id="cfg-lang",
            )

            with Static(classes="btn-row"):
                yield Button("save", id="btn-save", variant="primary")
                yield Button("cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
            return

        cfg = load_settings()

        # AI 백엔드
        backend_sel = self.query_one("#cfg-backend", Select)
        if backend_sel.value and backend_sel.value != Select.BLANK:
            cfg["backend"] = str(backend_sel.value)
        cfg["model"] = self.query_one("#cfg-model", Input).value
        cfg["server_url"] = self.query_one("#cfg-server-url", Input).value
        cfg["openai_api_key"] = self.query_one("#cfg-openai-key", Input).value
        cfg["openai_model"] = self.query_one("#cfg-openai-model", Input).value
        cfg["openai_base_url"] = self.query_one("#cfg-openai-base", Input).value

        # 검색 엔진
        engines = []
        for _, engine_id in _ENGINE_OPTIONS:
            cb = self.query_one(f"#eng-{engine_id}", Checkbox)
            if cb.value:
                engines.append(engine_id)
        cfg["search_engines"] = engines if engines else ["ddg"]
        cfg["google_serper_key"] = self.query_one("#cfg-serper-key", Input).value

        # 기타
        cfg["ai_name"] = self.query_one("#cfg-ai-name", Input).value
        lang_sel = self.query_one("#cfg-lang", Select)
        if lang_sel.value and lang_sel.value != Select.BLANK:
            cfg["lang"] = str(lang_sel.value)

        save_settings(cfg)
        self.dismiss(cfg)
