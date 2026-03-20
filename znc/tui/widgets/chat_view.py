"""
채팅 메시지 뷰 위젯.

레이아웃:
  MessageView (scrollable, height: 1fr)
  ├── RichLog#message-log (height: auto) — 완성된 메시지 히스토리
  └── Static#stream-current  — 스트리밍 중인 현재 응답

스트리밍 설계:
  RichLog.write() 는 호출마다 새 블록(단락)을 추가하므로
  토큰을 개별 write() 로 넣으면 글자마다 줄바꿈이 발생한다.
  대신 누적 버퍼를 Static.update() 로 실시간 표시하고,
  스트리밍 완료 시 Markdown 으로 변환해 RichLog 에 기록한다.
"""
from __future__ import annotations

from rich.markdown import Markdown
from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import RichLog, Static

from znc.core.models import Message


class MessageView(Widget):
    """대화 메시지 스크롤 뷰."""

    DEFAULT_CSS = """
    MessageView {
        height: 1fr;
        overflow-y: auto;
        overflow-x: hidden;
        background: #0d1117;
    }
    #message-log {
        height: auto;
        min-height: 100%;
        background: #0d1117;
        padding: 1 2;
        scrollbar-size: 0 0;
    }
    #stream-current {
        padding: 0 2 1 4;
        background: #0d1117;
        color: #e6edf3;
        display: none;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._stream_buffer = ""

    def compose(self) -> ComposeResult:
        yield RichLog(
            id="message-log",
            wrap=True,
            markup=False,
            highlight=False,
        )
        yield Static("", id="stream-current", markup=False)

    # ── Public API ──────────────────────────────────────────
    def clear(self) -> None:
        self.query_one("#message-log", RichLog).clear()
        sc = self.query_one("#stream-current", Static)
        sc.update("")
        sc.display = False
        self._stream_buffer = ""

    def render_history(self, messages: list[Message], ai_name: str) -> None:
        log = self.query_one("#message-log", RichLog)
        log.clear()
        for m in messages:
            self._write_msg(log, m, ai_name)
        self.scroll_end(animate=False)

    def append_message(self, message: Message, ai_name: str) -> None:
        self._write_msg(
            self.query_one("#message-log", RichLog), message, ai_name
        )
        self.scroll_end(animate=False)

    def begin_assistant_turn(self, ai_name: str) -> None:
        """스트리밍 시작 — AI 이름 헤더 기록 후 스트리밍 영역 활성화."""
        self.query_one("#message-log", RichLog).write(
            Text(f"\n{ai_name}", style="bold #3fb950")
        )
        self._stream_buffer = ""
        sc = self.query_one("#stream-current", Static)
        sc.update("")
        sc.display = True

    def append_token(self, token: str) -> None:
        """토큰 누적 후 Static 한 번에 업데이트 (줄바꿈 없음)."""
        self._stream_buffer += token
        self.query_one("#stream-current", Static).update(self._stream_buffer)
        self.scroll_end(animate=False)

    def end_streaming(self) -> None:
        """스트리밍 완료 — Static 숨기고 Markdown 으로 RichLog 에 기록."""
        content = self._stream_buffer
        self._stream_buffer = ""
        sc = self.query_one("#stream-current", Static)
        sc.display = False
        sc.update("")
        if content:
            log = self.query_one("#message-log", RichLog)
            try:
                log.write(Markdown(content))
            except Exception:
                log.write(Text(f"  {content}"))
        self.scroll_end(animate=False)

    def write_status(self, text: str, style: str = "yellow") -> None:
        self.query_one("#message-log", RichLog).write(
            Text(f"  {text}", style=style)
        )
        self.scroll_end(animate=False)

    def write(self, text: str = "") -> None:
        """구분자·빈 줄."""
        self.query_one("#message-log", RichLog).write(Text(text))

    # ── Internal ────────────────────────────────────────────
    def _write_msg(self, log: RichLog, m: Message, ai_name: str) -> None:
        if m.role == "user":
            log.write(Text(f"\nyou", style="bold #79c0ff"))
            log.write(Text(f"  {m.content}"))
        elif m.role == "assistant":
            log.write(Text(f"\n{ai_name}", style="bold #3fb950"))
            try:
                log.write(Markdown(m.content))
            except Exception:
                log.write(Text(f"  {m.content}"))
        elif m.role == "system":
            log.write(
                Text(f"\n[system]  {m.content}", style="dim #8b949e")
            )
