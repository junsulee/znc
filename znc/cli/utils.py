"""
CLI 공통 유틸리티 함수
"""
from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional

import click

from znc.backends.base import BaseBackend
from znc.core.models import Session


def safe_input(prompt: str) -> str:
    sys.stdout.write(prompt)
    sys.stdout.flush()
    try:
        raw_bytes = sys.stdin.buffer.readline()
        line = raw_bytes.decode("utf-8", errors="replace").strip()
        if "\ufffd" in line:
            click.secho(
                "⚠️  입력에 깨진 문자가 감지되어 \ufffd 로 표시됩니다.",
                fg="yellow",
            )
        return line
    except Exception as e:
        click.secho(f"❌ 입력 오류: {e}", fg="red")
        return ""


def build_prompt(session: Session, ai_name: str) -> str:
    prompt = ""
    for message in session.messages:
        if message.role == "user":
            prompt += f"User: {message.content}\n"
        elif message.role == "assistant":
            prompt += f"{ai_name}: {message.content}\n"
    prompt += f"{ai_name}:"
    return prompt


def generate_default_session_name() -> str:
    return f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def generate_session_title(session: Session, backend: BaseBackend) -> str:
    if not session.messages:
        return generate_default_session_name()

    lines = "\n".join(
        f"{m.role.capitalize()}: {m.content}" for m in session.messages[:6]
    )
    prompt = (
        "아래 대화 내용을 한 줄로 자연스럽게 요약해 파일명으로 쓸 수 있는 짧은 제목을 만들어줘.\n"
        "공백은 하이픈(-)으로 대체하고 특수문자는 제거해줘. 20자 이내로.\n\n"
        f"{lines}\n\n제목:"
    )
    try:
        title = backend.generate(prompt)
        title = title.strip().splitlines()[0]  # 첫 줄만
        title = title.replace(" ", "-").replace("/", "-")
        # 따옴표 제거
        title = title.strip("\"'""''")
        return title[:40] or generate_default_session_name()
    except Exception:
        return generate_default_session_name()


def print_session_history(session: Session, ai_name: str) -> None:
    for message in session.messages:
        if message.role == "user":
            click.secho(f"👤 User: {message.content}", fg="yellow")
        elif message.role == "assistant":
            click.secho(f"🤖 {ai_name}: {message.content}", fg="green")
        elif message.role == "system":
            click.secho(f"⚙️  [system]: {message.content}", fg="blue", dim=True)


def run_chat_loop(
    session: Session,
    backend: BaseBackend,
    ai_name: str,
    lang: str,
) -> None:
    """대화 루프. session.messages 에 메시지를 추가한다."""
    from znc.core.i18n import get_message

    click.secho(get_message(lang, "exit_tip"), fg="yellow")

    while True:
        try:
            user_input = safe_input("\n> ")
        except (KeyboardInterrupt, EOFError):
            click.secho("\n⚠️  종료 요청", fg="yellow")
            break

        if user_input.lower() in {"/exit", "exit", "quit", "/quit"}:
            click.secho("\n👋 대화를 종료합니다.", fg="yellow")
            break
        if not user_input:
            continue

        from znc.core.models import Message

        session.append(Message(role="user", content=user_input))
        prompt = build_prompt(session, ai_name)

        click.secho("\n" + "─" * 44, fg="cyan")
        click.secho(f"🤖 {ai_name}:", fg="green", bold=True)
        click.secho("─" * 44, fg="cyan")

        accumulated = ""
        try:
            for token in backend.stream(prompt, system_prompt=session.system_prompt):
                print(token, end="", flush=True)
                accumulated += token
            print()
        except Exception as e:
            click.secho(f"\n❌ API 오류: {e}", fg="red")
            session.messages.pop()
            continue

        session.append(Message(role="assistant", content=accumulated))
