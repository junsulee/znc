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

응답 대기 중 (Stage.THINKING) 에는 ASCII 스피너를 표시해
앱이 멈춘 게 아님을 알린다.

  | → / → - → \\  (classic TUI spinner, 100 ms 간격)
"""
from __future__ import annotations

from rich.markdown import Markdown
from rich.text import Text
from textual.app import ComposeResult
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import RichLog, Static

from znc.core.models import Message

# 고전적 TUI ASCII 스피너 (이모지 없음)
_THINK_FRAMES = ["|", "/", "-", "\\"]


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
        background: #0d1117;
        padding: 1 2;
        scrollbar-size: 0 0;
    }
    #stream-current {
        padding: 0 2 1 2;
        background: #0d1117;
        color: #e6edf3;
        display: none;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._stream_buffer = ""
        self._stream_ai_name = ""
        self._thinking = False
        self._think_tick = 0
        self._think_timer: Timer | None = None

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
        self._stop_thinking()
        self.query_one("#message-log", RichLog).clear()
        sc = self.query_one("#stream-current", Static)
        sc.update("")
        sc.display = False
        self._stream_buffer = ""
        self._stream_ai_name = ""

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
        """스트리밍 시작.

        첫 토큰 도착 전까지 ASCII 스피너(|/-\\)를 표시해 응답 대기 중임을 알린다.
        토큰이 도착하면 스피너가 실제 내용으로 교체된다.
        """
        self._stream_ai_name = ai_name
        self._stream_buffer = ""
        self._thinking = True
        self._think_tick = 0

        sc = self.query_one("#stream-current", Static)
        sc.display = True
        self._render_thinking()
        self.scroll_end(animate=False)

        # 100 ms 마다 스피너 프레임 전진
        self._stop_thinking()
        self._think_timer = self.set_interval(0.1, self._on_think_tick)

    def append_token(self, token: str) -> None:
        """토큰 누적 — 첫 토큰 수신 시 스피너 중단 후 실제 내용 표시."""
        if self._thinking:
            self._stop_thinking()

        self._stream_buffer += token
        sc = self.query_one("#stream-current", Static)
        t = Text()
        t.append(f"\n{self._stream_ai_name}", style="bold #3fb950")
        t.append(f"\n{self._stream_buffer}")
        sc.update(t)
        self.scroll_end(animate=False)

    def end_streaming(self) -> None:
        """스트리밍 완료 — Static 숨기고 AI 이름 + Markdown 본문을 RichLog 에 기록."""
        self._stop_thinking()
        content = self._stream_buffer
        ai_name = self._stream_ai_name
        self._stream_buffer = ""
        self._stream_ai_name = ""
        sc = self.query_one("#stream-current", Static)
        sc.display = False
        sc.update("")
        if content:
            log = self.query_one("#message-log", RichLog)
            log.write(Text(f"\n{ai_name}", style="bold #3fb950"))
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

    # ── Thinking animation ───────────────────────────────────
    def _on_think_tick(self) -> None:
        if not self._thinking:
            return
        self._think_tick += 1
        self._render_thinking()

    def _render_thinking(self) -> None:
        frame = _THINK_FRAMES[self._think_tick % len(_THINK_FRAMES)]
        sc = self.query_one("#stream-current", Static)
        t = Text()
        t.append(f"\n{self._stream_ai_name}", style="bold #3fb950")
        t.append(f"\n  {frame}", style="dim #8b949e")
        sc.update(t)

    def _stop_thinking(self) -> None:
        self._thinking = False
        if self._think_timer is not None:
            self._think_timer.stop()
            self._think_timer = None

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
