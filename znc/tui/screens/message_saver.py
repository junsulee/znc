"""
MessageSaverScreen — 메시지 선택 후 파일 저장 팝업.

사용자가 대화 내 특정 메시지를 선택하면:
  1. 콘텐츠 타입 자동 감지 (Python, JSON, CSV, Markdown 등)
  2. 저장 포맷 버튼으로 빠른 전환
  3. 파일명 편집 후 저장
"""
from __future__ import annotations

import os
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from znc.core.content_detector import (
    QUICK_FORMATS, EXT_DISPLAY,
    detect_and_extract, clean_content_for_ext,
)
from znc.core.models import Message


class MessageSaverScreen(ModalScreen):
    """메시지 선택 → 타입 감지 → 파일 저장."""

    BINDINGS = [Binding("escape", "dismiss", "닫기")]

    DEFAULT_CSS = """
    MessageSaverScreen { align: center middle; }
    #saver-box {
        background: #161b22;
        border: tall #30363d;
        padding: 1 2;
        width: 72;
        height: 36;
    }
    .sv-title  { color: #58a6ff; text-style: bold; height: 1; }
    .sv-sep    { color: #30363d; height: 1; margin: 1 0; }
    .sv-label  { color: #8b949e; height: 1; margin-top: 1; }
    .sv-detect { color: #3fb950; height: 1; margin-top: 1; }
    .sv-detect.--warn { color: #d29922; }
    #msg-list  { height: 10; background: #0d1117; border: tall #30363d; }
    .msg-user  { color: #79c0ff; height: 1; padding: 0 1; }
    .msg-ai    { color: #3fb950; height: 1; padding: 0 1; }
    #fmt-row   { height: 3; margin-top: 1; }
    .fmt-btn   { width: 7; min-width: 7; height: 3; margin: 0; border: tall #30363d; color: #8b949e; }
    .fmt-btn.--active { border: tall #58a6ff; color: #58a6ff; text-style: bold; }
    #sv-filename { background: #0d1117; border: tall #30363d; color: #e6edf3; margin-top: 1; }
    #sv-filename:focus { border: tall #58a6ff; }
    .btn-row   { align: center middle; height: 3; margin-top: 1; }
    .sv-path   { color: #484f58; height: 1; margin-top: 1; }
    """

    def __init__(self, messages: list[Message], ai_name: str,
                 save_dir: str = "") -> None:
        super().__init__()
        self._messages = messages
        self._ai_name = ai_name
        self._save_dir = save_dir or str(Path.home())
        self._selected_idx: int = -1
        self._current_ext: str = "md"
        self._current_content: str = ""

    def compose(self) -> ComposeResult:
        with Static(id="saver-box"):
            yield Label("Save Message", classes="sv-title")
            yield Label("─" * 60, classes="sv-sep")

            yield Label("Select a message:", classes="sv-label")
            yield ListView(id="msg-list")

            yield Label("", id="sv-detect", classes="sv-detect")
            yield Label("─" * 60, classes="sv-sep")

            yield Label("Format:", classes="sv-label")
            with Static(id="fmt-row"):
                for fmt in QUICK_FORMATS:
                    label = f".{fmt}"
                    yield Button(label, id=f"fmt-{fmt}", classes="fmt-btn")

            yield Label("Filename:", classes="sv-label")
            yield Input(id="sv-filename", placeholder="filename.ext")
            yield Label("", id="sv-path", classes="sv-path")

            with Static(classes="btn-row"):
                yield Button("Save", id="btn-save", variant="primary")
                yield Button("Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        lv = self.query_one("#msg-list", ListView)
        for m in self._messages:
            if m.role == "user":
                preview = m.content.replace("\n", " ")[:62]
                lv.append(ListItem(Label(f"  you  {preview}", markup=False, classes="msg-user")))
            elif m.role == "assistant":
                preview = m.content.replace("\n", " ")[:62]
                lv.append(ListItem(Label(f"  {self._ai_name}  {preview}", markup=False, classes="msg-ai")))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        idx = event.list_view.index
        if idx is None:
            return
        # 실제 Message 인덱스 (role 필터 없이 순서대로 대응)
        visible = [m for m in self._messages if m.role in ("user", "assistant")]
        if idx < len(visible):
            self._selected_idx = idx
            msg = visible[idx]
            self._update_detection(msg.content)

    def _update_detection(self, content: str) -> None:
        result = detect_and_extract(content)
        self._current_ext = result.ext
        self._current_content = clean_content_for_ext(result.content, result.ext)

        # 감지 레이블
        detect_lbl = self.query_one("#sv-detect", Label)
        detect_lbl.update(f"Detected: {result.display}  →  .{result.ext}")

        # 포맷 버튼 활성화
        for fmt in QUICK_FORMATS:
            btn = self.query_one(f"#fmt-{fmt}", Button)
            if fmt == result.ext:
                btn.add_class("--active")
            else:
                btn.remove_class("--active")

        # 파일명 추천
        self.query_one("#sv-filename", Input).value = result.filename
        self._update_path_hint(result.filename)

    def _update_path_hint(self, filename: str) -> None:
        path = os.path.join(self._save_dir, filename)
        self.query_one("#sv-path", Label).update(f"→  {path}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""

        if bid == "btn-cancel":
            self.dismiss(None)
            return

        if bid.startswith("fmt-"):
            # 포맷 전환
            new_ext = bid[4:]
            self._current_ext = new_ext
            for fmt in QUICK_FORMATS:
                btn = self.query_one(f"#fmt-{fmt}", Button)
                if fmt == new_ext:
                    btn.add_class("--active")
                else:
                    btn.remove_class("--active")
            # 파일명 확장자 교체
            inp = self.query_one("#sv-filename", Input)
            stem = Path(inp.value).stem if inp.value else "export"
            new_name = f"{stem}.{new_ext}"
            inp.value = new_name
            self._update_path_hint(new_name)
            return

        if bid == "btn-save":
            self._do_save()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "sv-filename":
            self._update_path_hint(event.value)

    def _do_save(self) -> None:
        visible = [m for m in self._messages if m.role in ("user", "assistant")]
        if self._selected_idx < 0 or self._selected_idx >= len(visible):
            self.query_one("#sv-detect", Label).update("No message selected.")
            return

        filename = self.query_one("#sv-filename", Input).value.strip()
        if not filename:
            return

        filepath = os.path.join(self._save_dir, filename)
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self._current_content)
            self.dismiss(filepath)
        except Exception as e:
            self.query_one("#sv-detect", Label).update(f"Error: {e}")
