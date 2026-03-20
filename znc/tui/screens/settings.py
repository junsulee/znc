"""
설정 팝업 스크린 — 탭 구조 (AI 백엔드 / 일반).

AI 백엔드 탭: backend, model, server URL, OpenAI 설정
일반 탭: 언어, 테마(다크/라이트), 검색 엔진
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Checkbox, Input, Label,
    Select, Static, TabbedContent, TabPane,
)

from znc.core.config import load_settings, save_settings
from znc.core.i18n import ui as _ui

_ENGINE_OPTIONS = [
    ("DuckDuckGo  (기본, API 불필요)",         "ddg"),
    ("Naver       (한국어 최적, API 불필요)",   "naver"),
    ("Google      (Serper.dev API 키 필요)",   "google"),
]


class SettingsScreen(ModalScreen):
    """설정 오버레이 팝업 — AI / 일반 탭."""

    BINDINGS = [Binding("escape", "dismiss", "닫기")]

    DEFAULT_CSS = """
    SettingsScreen { align: center middle; }
    #settings-box {
        background: #161b22;
        border: tall #30363d;
        padding: 0;
        width: 66;
        height: 38;
    }
    #settings-tabs {
        height: 1fr;
        background: #161b22;
    }
    .tab-content {
        padding: 1 2;
        height: 1fr;
        overflow-y: auto;
        background: #161b22;
    }
    .s-sep    { color: #30363d; height: 1; margin: 1 0; }
    .s-label  { color: #8b949e; height: 1; margin-top: 1; }
    .s-input  { background: #0d1117; border: tall #30363d; color: #e6edf3; }
    .s-input:focus { border: tall #58a6ff; }
    .s-check  { height: 1; margin: 0; }
    #settings-footer {
        border-top: tall #30363d;
        height: 3;
        background: #161b22;
        align: center middle;
        padding: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        cfg = load_settings()
        lang = cfg.get("lang", "ko")
        active_engines: list[str] = cfg.get("search_engines", ["ddg", "naver"])

        with Static(id="settings-box"):
            with TabbedContent(id="settings-tabs"):
                # ── AI 백엔드 탭 ──────────────────────────────────
                with TabPane(_ui(lang, "tab_ai"), id="tab-ai"):
                    with Static(classes="tab-content"):
                        yield Label("Backend", classes="s-label")
                        yield Select(
                            options=[("ollama", "ollama"), ("openai", "openai")],
                            value=cfg.get("backend", "ollama"),
                            id="cfg-backend",
                        )

                        yield Label("Model  (Ollama)", classes="s-label")
                        yield Input(value=cfg.get("model", ""), id="cfg-model", classes="s-input")

                        yield Label("Server URL  (Ollama)", classes="s-label")
                        yield Input(value=cfg.get("server_url", ""), id="cfg-server-url", classes="s-input")

                        yield Label("─" * 50, classes="s-sep")

                        yield Label("OpenAI API Key", classes="s-label")
                        yield Input(
                            value=cfg.get("openai_api_key", ""),
                            id="cfg-openai-key",
                            password=True,
                            classes="s-input",
                        )

                        yield Label("OpenAI Model", classes="s-label")
                        yield Input(value=cfg.get("openai_model", "gpt-4o"), id="cfg-openai-model", classes="s-input")

                        yield Label("OpenAI Base URL", classes="s-label")
                        yield Input(
                            value=cfg.get("openai_base_url", "https://api.openai.com/v1"),
                            id="cfg-openai-base",
                            classes="s-input",
                        )

                        yield Label("AI Name", classes="s-label")
                        yield Input(value=cfg.get("ai_name", "znc"), id="cfg-ai-name", classes="s-input")

                # ── 일반 탭 ───────────────────────────────────────
                with TabPane(_ui(lang, "tab_general"), id="tab-general"):
                    with Static(classes="tab-content"):
                        yield Label(_ui(lang, "setting_lang"), classes="s-label")
                        yield Select(
                            options=[("한국어", "ko"), ("English", "en")],
                            value=lang,
                            id="cfg-lang",
                        )

                        yield Label("─" * 50, classes="s-sep")

                        yield Label(_ui(lang, "setting_theme"), classes="s-label")
                        yield Select(
                            options=[
                                (f"◑  {_ui(lang, 'theme_dark')}", "dark"),
                                (f"○  {_ui(lang, 'theme_light')}", "light"),
                            ],
                            value=cfg.get("theme", "dark"),
                            id="cfg-theme",
                        )

                        yield Label("─" * 50, classes="s-sep")

                        yield Label(_ui(lang, "setting_engines"), classes="s-label")
                        for label, eid in _ENGINE_OPTIONS:
                            yield Checkbox(
                                label,
                                value=(eid in active_engines),
                                id=f"eng-{eid}",
                                classes="s-check",
                            )

                        yield Label("Google Serper API Key", classes="s-label")
                        yield Input(
                            value=cfg.get("google_serper_key", ""),
                            id="cfg-serper-key",
                            password=True,
                            placeholder="serper.dev  (무료 2500회/월)",
                            classes="s-input",
                        )

            # ── 고정 푸터 ─────────────────────────────────────────
            with Static(id="settings-footer"):
                yield Button(_ui(lang, "btn_save"), id="btn-save", variant="primary")
                yield Button(_ui(lang, "btn_cancel"), id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
            return
        if event.button.id == "btn-save":
            self._do_save()

    def _do_save(self) -> None:
        cfg = load_settings()

        # ── AI 백엔드 ──────────────────────────────────────────────
        backend_sel = self.query_one("#cfg-backend", Select)
        if backend_sel.value and backend_sel.value != Select.BLANK:
            cfg["backend"] = str(backend_sel.value)
        cfg["model"] = self.query_one("#cfg-model", Input).value
        cfg["server_url"] = self.query_one("#cfg-server-url", Input).value
        cfg["openai_api_key"] = self.query_one("#cfg-openai-key", Input).value
        cfg["openai_model"] = self.query_one("#cfg-openai-model", Input).value
        cfg["openai_base_url"] = self.query_one("#cfg-openai-base", Input).value
        cfg["ai_name"] = self.query_one("#cfg-ai-name", Input).value

        # ── 일반 ──────────────────────────────────────────────────
        lang_sel = self.query_one("#cfg-lang", Select)
        if lang_sel.value and lang_sel.value != Select.BLANK:
            cfg["lang"] = str(lang_sel.value)

        theme_sel = self.query_one("#cfg-theme", Select)
        if theme_sel.value and theme_sel.value != Select.BLANK:
            cfg["theme"] = str(theme_sel.value)

        engines = []
        for _, eid in _ENGINE_OPTIONS:
            cb = self.query_one(f"#eng-{eid}", Checkbox)
            if cb.value:
                engines.append(eid)
        cfg["search_engines"] = engines if engines else ["ddg"]
        cfg["google_serper_key"] = self.query_one("#cfg-serper-key", Input).value

        save_settings(cfg)
        self.dismiss(cfg)
