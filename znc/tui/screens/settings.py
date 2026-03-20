"""
설정 팝업 — 탭 구조 (AI 백엔드 / 일반).
Google 검색 제거 (API 키 필요). i18n 전면 적용.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Input, Label,
    Select, SelectionList, Static,
    TabbedContent, TabPane,
)

from znc.core.config import load_settings, save_settings
from znc.core.i18n import ui as _ui

# Google 제거: API 키 필요한 서비스는 기본 엔진 목록에서 제외
_ENGINE_OPTIONS = [
    ("DuckDuckGo  (API 불필요)", "ddg"),
    ("Naver       (한국어 최적, API 불필요)", "naver"),
]


def _get_lang() -> str:
    return load_settings().get("lang", "ko")


class SettingsScreen(ModalScreen):
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
    #settings-tabs { height: 1fr; background: #161b22; }
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
    #settings-footer {
        border-top: tall #30363d;
        height: 3;
        background: #161b22;
        align: center middle;
        padding: 0 2;
    }
    /* SelectionList 스타일 */
    SelectionList {
        background: #0d1117;
        border: tall #30363d;
        height: 5;
        padding: 0 1;
    }
    SelectionList > .option-list--option {
        color: #8b949e;
    }
    SelectionList > .option-list--option-highlighted {
        background: #1c2128;
        color: #e6edf3;
    }
    SelectionList > .option-list--option-selected {
        color: #58a6ff;
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
                        yield Label(_ui(lang, "setting_backend"), classes="s-label")
                        yield Select(
                            options=[("ollama", "ollama"), ("openai", "openai")],
                            value=cfg.get("backend", "ollama"),
                            id="cfg-backend",
                        )
                        yield Label(_ui(lang, "setting_model_ollama"), classes="s-label")
                        yield Input(value=cfg.get("model", ""), id="cfg-model", classes="s-input")
                        yield Label(_ui(lang, "setting_server_url"), classes="s-label")
                        yield Input(value=cfg.get("server_url", ""), id="cfg-server-url", classes="s-input")
                        yield Label("─" * 50, classes="s-sep")
                        yield Label(_ui(lang, "setting_oai_key"), classes="s-label")
                        yield Input(
                            value=cfg.get("openai_api_key", ""),
                            id="cfg-openai-key", password=True, classes="s-input",
                        )
                        yield Label(_ui(lang, "setting_oai_model"), classes="s-label")
                        yield Input(value=cfg.get("openai_model", "gpt-4o"), id="cfg-openai-model", classes="s-input")
                        yield Label(_ui(lang, "setting_oai_base"), classes="s-label")
                        yield Input(
                            value=cfg.get("openai_base_url", "https://api.openai.com/v1"),
                            id="cfg-openai-base", classes="s-input",
                        )
                        yield Label(_ui(lang, "setting_ai_name"), classes="s-label")
                        yield Input(value=cfg.get("ai_name", "znc"), id="cfg-ai-name", classes="s-input")

                # ── 일반 탭 ───────────────────────────────────────
                with TabPane(_ui(lang, "tab_general"), id="tab-general"):
                    with Static(classes="tab-content"):
                        yield Label(_ui(lang, "setting_lang"), classes="s-label")
                        yield Select(
                            options=[("한국어", "ko"), ("English", "en")],
                            value=lang, id="cfg-lang",
                        )
                        yield Label("─" * 50, classes="s-sep")
                        yield Label(_ui(lang, "setting_theme"), classes="s-label")
                        yield Select(
                            options=[
                                (_ui(lang, "theme_dark"),  "dark"),
                                (_ui(lang, "theme_light"), "light"),
                            ],
                            value=cfg.get("theme", "dark"), id="cfg-theme",
                        )
                        yield Label("─" * 50, classes="s-sep")
                        yield Label(_ui(lang, "setting_engines"), classes="s-label")
                        # SelectionList: Checkbox 대신 사용 (스타일 안정성)
                        yield SelectionList(
                            *[
                                (label, eid, eid in active_engines)
                                for label, eid in _ENGINE_OPTIONS
                            ],
                            id="engine-select",
                        )

            with Static(id="settings-footer"):
                yield Button(_ui(lang, "btn_save"),   id="btn-save",   variant="primary")
                yield Button(_ui(lang, "btn_cancel"), id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-save":
            self._do_save()

    def _do_save(self) -> None:
        cfg = load_settings()

        # AI 백엔드
        def _sel(wid):
            s = self.query_one(wid, Select)
            return str(s.value) if s.value and s.value != Select.BLANK else None

        if v := _sel("#cfg-backend"):  cfg["backend"] = v
        cfg["model"]           = self.query_one("#cfg-model", Input).value
        cfg["server_url"]      = self.query_one("#cfg-server-url", Input).value
        cfg["openai_api_key"]  = self.query_one("#cfg-openai-key", Input).value
        cfg["openai_model"]    = self.query_one("#cfg-openai-model", Input).value
        cfg["openai_base_url"] = self.query_one("#cfg-openai-base", Input).value
        cfg["ai_name"]         = self.query_one("#cfg-ai-name", Input).value

        # 일반
        if v := _sel("#cfg-lang"):  cfg["lang"] = v
        if v := _sel("#cfg-theme"): cfg["theme"] = v

        # 검색 엔진 (SelectionList)
        sel_list = self.query_one("#engine-select", SelectionList)
        engines = list(sel_list.selected)
        cfg["search_engines"] = engines if engines else ["ddg"]

        save_settings(cfg)
        self.dismiss(cfg)
