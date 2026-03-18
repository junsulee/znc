"""
설정 팝업 스크린.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from znc.core.config import load_settings, save_settings


class SettingsScreen(ModalScreen):
    """설정 오버레이 팝업."""

    BINDINGS = [Binding("escape", "dismiss", "닫기")]

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }
    #settings-box {
        background: #161b22;
        border: tall #30363d;
        padding: 1 2;
        width: 60;
        height: auto;
        max-height: 32;
    }
    .s-title { color: #58a6ff; text-style: bold; height: 1; margin-bottom: 1; }
    .s-sep   { color: #30363d; height: 1; }
    .s-label { color: #8b949e; height: 1; margin-top: 1; }
    .s-input { background: #0d1117; border: tall #30363d; color: #e6edf3; margin-bottom: 0; }
    .s-input:focus { border: tall #58a6ff; }
    .btn-row { align: center middle; height: 3; margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        cfg = load_settings()
        with Static(id="settings-box"):
            yield Label("settings", classes="s-title")
            yield Label("─" * 48, classes="s-sep")

            yield Label("backend", classes="s-label")
            yield Select(
                options=[("ollama", "ollama"), ("openai", "openai")],
                value=cfg.get("backend", "ollama"),
                id="cfg-backend",
            )

            yield Label("model (ollama)", classes="s-label")
            yield Input(value=cfg.get("model", ""), id="cfg-model", classes="s-input")

            yield Label("server url (ollama)", classes="s-label")
            yield Input(value=cfg.get("server_url", ""), id="cfg-server-url", classes="s-input")

            yield Label("─" * 48, classes="s-sep")

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
            yield Input(value=cfg.get("openai_base_url", "https://api.openai.com/v1"), id="cfg-openai-base", classes="s-input")

            yield Label("─" * 48, classes="s-sep")

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
        backend_sel = self.query_one("#cfg-backend", Select)
        if backend_sel.value and backend_sel.value != Select.BLANK:
            cfg["backend"] = backend_sel.value
        cfg["model"] = self.query_one("#cfg-model", Input).value
        cfg["server_url"] = self.query_one("#cfg-server-url", Input).value
        cfg["openai_api_key"] = self.query_one("#cfg-openai-key", Input).value
        cfg["openai_model"] = self.query_one("#cfg-openai-model", Input).value
        cfg["openai_base_url"] = self.query_one("#cfg-openai-base", Input).value
        cfg["ai_name"] = self.query_one("#cfg-ai-name", Input).value
        lang_sel = self.query_one("#cfg-lang", Select)
        if lang_sel.value and lang_sel.value != Select.BLANK:
            cfg["lang"] = lang_sel.value
        save_settings(cfg)
        self.dismiss(cfg)
