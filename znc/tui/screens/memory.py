"""
메모리 관리 팝업 스크린.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static
from textual.message import Message

import znc.core.memory as mem


class MemoryScreen(ModalScreen):
    """메모리 관리 오버레이."""

    BINDINGS = [Binding("escape", "dismiss", "닫기")]

    DEFAULT_CSS = """
    MemoryScreen { align: center middle; }
    #memory-box {
        background: #161b22;
        border: tall #30363d;
        padding: 1 2;
        width: 64;
        height: 28;
    }
    .m-title  { color: #58a6ff; text-style: bold; height: 1; margin-bottom: 1; }
    .m-sep    { color: #30363d; height: 1; }
    .m-label  { color: #8b949e; height: 1; margin-top: 1; }
    .m-input  { background: #0d1117; border: tall #30363d; color: #e6edf3; width: 1fr; }
    .m-input:focus { border: tall #58a6ff; }
    #memory-list { height: 12; background: #0d1117; border: tall #30363d; }
    .mem-row  { padding: 0 1; height: 1; color: #8b949e; }
    .mem-manual { color: #58a6ff; }
    .mem-auto   { color: #d29922; }
    .btn-row  { align: center middle; height: 3; margin-top: 1; }
    #add-row  { height: 3; }
    """

    def compose(self) -> ComposeResult:
        with Static(id="memory-box"):
            yield Label("memory", classes="m-title")
            yield Label("─" * 52, classes="m-sep")

            yield Label("add (key: value)", classes="m-label")
            with Static(id="add-row"):
                yield Input(placeholder="key: value", id="mem-input", classes="m-input")
                yield Button("add", id="btn-add-mem")

            yield Label(
                "stored memories  (m=manual:blue  a=auto:yellow)",
                classes="m-label",
                markup=False,
            )
            yield ListView(id="memory-list")

            with Static(classes="btn-row"):
                yield Button("clear all", id="btn-clear", variant="error")
                yield Button("close", id="btn-close")

    def on_mount(self) -> None:
        self._refresh_list()

    def _refresh_list(self) -> None:
        lv = self.query_one("#memory-list", ListView)
        lv.clear()
        for item in mem.load_all():
            source_style = "mem-manual" if item.source == "manual" else "mem-auto"
            label = Label(
                f"[{item.source[0]}] {item.key}: {item.value}",
                classes=f"mem-row {source_style}",
            )
            # ID 미사용: 한글·공백 등 특수문자 포함 시 BadIdentifier 발생
            lv.append(ListItem(label))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss()
        elif event.button.id == "btn-add-mem":
            self._add_item()
        elif event.button.id == "btn-clear":
            mem.clear_all()
            self._refresh_list()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._add_item()

    def _add_item(self) -> None:
        raw = self.query_one("#mem-input", Input).value.strip()
        if not raw:
            return
        if ":" in raw:
            key, _, value = raw.partition(":")
        else:
            key, value = raw, raw
        mem.add_manual(key.strip(), value.strip())
        self.query_one("#mem-input", Input).value = ""
        self._refresh_list()
