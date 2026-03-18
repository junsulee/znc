"""
채팅 메시지 뷰 위젯.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, RichLog, Static
from textual.scroll_view import ScrollView
from textual import on
from rich.markdown import Markdown
from rich.text import Text

from znc.core.models import Message


class MessageView(Widget):
    """대화 메시지를 스크롤 가능하게 표시."""

    DEFAULT_CSS = """
    MessageView {
        height: 1fr;
        overflow-y: auto;
    }
    """

    def compose(self) -> ComposeResult:
        yield RichLog(id="message-view", wrap=True, markup=True, highlight=False)

    def clear(self) -> None:
        self.query_one(RichLog).clear()

    def render_history(self, messages: list[Message], ai_name: str) -> None:
        log = self.query_one(RichLog)
        log.clear()
        for m in messages:
            self._write_message(log, m, ai_name)

    def append_message(self, message: Message, ai_name: str) -> None:
        log = self.query_one(RichLog)
        self._write_message(log, message, ai_name)

    def append_token(self, token: str) -> None:
        """스트리밍 토큰을 현재 줄에 이어 씀."""
        log = self.query_one(RichLog)
        log.write(Text(token), expand=False)

    def begin_assistant_turn(self, ai_name: str) -> None:
        log = self.query_one(RichLog)
        log.write(Text(f"\n{ai_name}", style="bold green"))

    def end_assistant_turn(self, content: str) -> None:
        """스트리밍 완료 후 마크다운 렌더링으로 교체."""
        log = self.query_one(RichLog)
        # 마지막 raw 텍스트를 markdown 으로 재렌더링
        log.write(Text(""))  # 줄 구분

    def write_status(self, text: str, style: str = "yellow") -> None:
        log = self.query_one(RichLog)
        log.write(Text(f"  {text}", style=style))

    def _write_message(self, log: RichLog, m: Message, ai_name: str) -> None:
        if m.role == "user":
            log.write(Text(f"\nyou", style="bold #79c0ff"))
            log.write(Text(f"  {m.content}", style="#e6edf3"))
        elif m.role == "assistant":
            log.write(Text(f"\n{ai_name}", style="bold #3fb950"))
            try:
                log.write(Markdown(m.content))
            except Exception:
                log.write(Text(f"  {m.content}", style="#e6edf3"))
        elif m.role == "system":
            log.write(Text(f"\n[system]  {m.content}", style="dim #8b949e"))
