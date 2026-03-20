"""
MessageSaverScreen — 메시지 선택 후 파일 저장 팝업.

레이아웃:
  ┌─────────────────────────────────────────────────────────┐
  │  Save Message                                           │
  │  ─────────────────────────────────────────────────────  │
  │  Select a message:                                      │
  │  ┌─────────────────────────────────────────────────┐   │
  │  │  you  Python 함수 작성해줘                       │   │
  │  │▶ znc  ```python\ndef hello():...                │   │
  │  └─────────────────────────────────────────────────┘   │
  │  Detected: Python  →  .py                               │
  │  ─────────────────────────────────────────────────────  │
  │  Format:  [.md] [.txt] [■.py] [.json] [.csv] ...       │
  │  Filename: [hello.py_______________________________]    │
  │  →  /home/user/.znc/sessions/hello.py                  │
  ├─────────────────────────────────────────────────────────┤
  │  [        Save        ]   [      Cancel      ]          │
  └─────────────────────────────────────────────────────────┘

스크롤 가능한 콘텐츠 + 항상 보이는 고정 푸터.
"""
from __future__ import annotations

import os
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from znc.core.content_detector import (
    QUICK_FORMATS, EXT_DISPLAY,
    detect_and_extract, clean_content_for_ext,
)
from znc.core.models import Message


class MessageSaverScreen(ModalScreen):
    """메시지 선택 → 타입 감지 → 파일 저장."""

    BINDINGS = [
        Binding("escape", "dismiss", "닫기"),
        Binding("ctrl+s", "save",    "저장", priority=True),
    ]

    DEFAULT_CSS = """
    MessageSaverScreen { align: center middle; }

    #saver-box {
        background: #161b22;
        border: tall #30363d;
        padding: 0;
        width: 70;
        height: 36;
    }

    /* 스크롤 가능한 콘텐츠 영역: 1fr → 푸터(3) 제외 나머지 채움 */
    #saver-scroll {
        padding: 1 2;
        height: 1fr;
        overflow-y: auto;
        background: #161b22;
    }

    /* 항상 보이는 하단 저장/취소 버튼 영역 */
    #saver-footer {
        border-top: tall #30363d;
        height: 3;
        background: #161b22;
        align: center middle;
        padding: 0 2;
    }

    .sv-title  { color: #58a6ff; text-style: bold; height: 1; }
    .sv-sep    { color: #30363d; height: 1; margin: 1 0; }
    .sv-label  { color: #8b949e; height: 1; margin-top: 1; }
    .sv-detect { color: #3fb950; height: 1; margin-top: 1; }
    .sv-path   { color: #484f58; height: 1; margin-top: 1; }

    #msg-list  { height: 8; background: #0d1117; border: tall #30363d; margin-top: 1; }
    .msg-user  { color: #79c0ff; padding: 0 1; height: 1; }
    .msg-ai    { color: #3fb950;  padding: 0 1; height: 1; }

    #fmt-row   { height: 3; margin-top: 1; }
    .fmt-btn   {
        width: 7; min-width: 7; height: 3;
        margin: 0; border: tall #30363d; color: #8b949e;
    }
    .fmt-btn.--active { border: tall #58a6ff; color: #58a6ff; text-style: bold; }

    #sv-filename {
        background: #0d1117;
        border: tall #30363d;
        color: #e6edf3;
        margin-top: 1;
    }
    #sv-filename:focus { border: tall #58a6ff; }

    #btn-save   { margin: 0 1; }
    #btn-cancel { margin: 0 1; }
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
            # ── 스크롤 가능한 콘텐츠 ──────────────────────────────
            with VerticalScroll(id="saver-scroll"):
                yield Label("Save Message", classes="sv-title")
                yield Label("─" * 58, classes="sv-sep")

                yield Label("Select a message:", classes="sv-label")
                yield ListView(id="msg-list")

                yield Label("", id="sv-detect", classes="sv-detect")
                yield Label("─" * 58, classes="sv-sep")

                yield Label("Format:", classes="sv-label")
                with Horizontal(id="fmt-row"):
                    for fmt in QUICK_FORMATS:
                        yield Button(f".{fmt}", id=f"fmt-{fmt}", classes="fmt-btn")

                yield Label("Filename:", classes="sv-label")
                yield Input(id="sv-filename", placeholder="filename.ext")
                yield Label("", id="sv-path", classes="sv-path")

            # ── 항상 보이는 푸터 ──────────────────────────────────
            with Horizontal(id="saver-footer"):
                yield Button("Save", id="btn-save", variant="primary")
                yield Button("Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        lv = self.query_one("#msg-list", ListView)
        visible = [m for m in self._messages if m.role in ("user", "assistant")]
        for m in visible:
            if m.role == "user":
                preview = m.content.replace("\n", " ")[:64]
                lv.append(ListItem(Label(
                    f"  you  {preview}", markup=False, classes="msg-user"
                )))
            else:
                preview = m.content.replace("\n", " ")[:64]
                lv.append(ListItem(Label(
                    f"  {self._ai_name}  {preview}", markup=False, classes="msg-ai"
                )))

    # ── 메시지 선택 시 타입 감지 ────────────────────────────────
    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        idx = event.list_view.index
        if idx is None:
            return
        visible = [m for m in self._messages if m.role in ("user", "assistant")]
        if idx < len(visible):
            self._selected_idx = idx
            self._update_detection(visible[idx].content)

    def _update_detection(self, content: str) -> None:
        result = detect_and_extract(content)
        self._current_ext = result.ext
        self._current_content = clean_content_for_ext(result.content, result.ext)

        # 감지 결과 표시
        self.query_one("#sv-detect", Label).update(
            f"Detected: {result.display}  →  .{result.ext}"
        )

        # 포맷 버튼 활성화
        for fmt in QUICK_FORMATS:
            btn = self.query_one(f"#fmt-{fmt}", Button)
            if fmt == result.ext:
                btn.add_class("--active")
            else:
                btn.remove_class("--active")

        # 파일명 추천
        self.query_one("#sv-filename", Input).value = result.filename
        self._refresh_path(result.filename)

    def _refresh_path(self, filename: str) -> None:
        path = os.path.join(self._save_dir, filename)
        self.query_one("#sv-path", Label).update(f"  →  {path}")

    # ── 버튼 / 입력 이벤트 ──────────────────────────────────────
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""

        if bid == "btn-cancel":
            self.dismiss(None)
            return

        if bid.startswith("fmt-"):
            new_ext = bid[4:]
            self._current_ext = new_ext
            for fmt in QUICK_FORMATS:
                btn = self.query_one(f"#fmt-{fmt}", Button)
                (btn.add_class if fmt == new_ext else btn.remove_class)("--active")
            inp = self.query_one("#sv-filename", Input)
            stem = Path(inp.value).stem if inp.value else "export"
            new_name = f"{stem}.{new_ext}"
            inp.value = new_name
            self._refresh_path(new_name)
            return

        if bid == "btn-save":
            self.action_save()

    def on_input_changed(self, event) -> None:
        if event.input.id == "sv-filename":
            self._refresh_path(event.value)

    def action_save(self) -> None:
        visible = [m for m in self._messages if m.role in ("user", "assistant")]
        if self._selected_idx < 0 or self._selected_idx >= len(visible):
            self.query_one("#sv-detect", Label).update(
                "[red]No message selected. Click a message first.[/]"
            )
            return

        filename = self.query_one("#sv-filename", Input).value.strip()
        if not filename:
            return

        filepath = os.path.join(self._save_dir, filename)
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self._current_content)
            self.dismiss(filepath)
        except Exception as e:
            self.query_one("#sv-detect", Label).update(f"[red]Error: {e}[/]")
