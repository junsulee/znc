"""
CLI headless 모드 공통 유틸리티.

run_chat_loop() 는 TUI 와 동등한 기능을 제공:
  - Persona 시스템 프롬프트 적용
  - 장기 메모리 컨텍스트 자동 주입 + 응답 후 자동 추출
  - 웹 검색 자동 감지 + 수동 /search (freshness 옵션)
  - 자동 제목 생성 (세션 종료 전)
  - 다중 줄 입력 (\ 줄 연속 또는 <<< ... >>> 블록)
  - Rich 기반 마크다운 렌더링 + 컬러 출력
  - 진행 상태 표시 (검색/크롤링/생성 중...)
  - 슬래시 명령어 전체 집합
"""
from __future__ import annotations

import os
import sys
import threading
import unicodedata
from datetime import datetime
from typing import Optional

import click

from znc.backends.base import BaseBackend
from znc.core.models import Session

# ── Rich 임포트 (없으면 click 폴백) ─────────────────────────────
try:
    from rich.console import Console as _RichConsole
    from rich.markdown import Markdown as _RichMD
    from rich.text import Text as _RichText
    _console = _RichConsole(highlight=False)
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False


# ────────────────────────────────────────────────────────────────
# 출력 헬퍼
# ────────────────────────────────────────────────────────────────

def _print_ai(ai_name: str, content: str, lang: str = "ko") -> None:
    """AI 응답을 마크다운 렌더링으로 출력."""
    if _HAS_RICH:
        _console.print(f"\n[bold green]{ai_name}[/bold green]")
        _console.print("─" * 44)
        try:
            _console.print(_RichMD(content))
        except Exception:
            _console.print(content)
    else:
        click.secho(f"\n{ai_name}:", fg="green", bold=True)
        click.secho("─" * 44, fg="cyan")
        click.echo(content)


def _print_user(content: str) -> None:
    if _HAS_RICH:
        _console.print(f"\n[bold #79c0ff]you[/bold #79c0ff]")
        _console.print(f"  {content}")
    else:
        click.echo(f"\nyou: {content}")


def _status(msg: str, style: str = "yellow") -> None:
    if _HAS_RICH:
        _console.print(f"  [{style}]{msg}[/{style}]")
    else:
        click.secho(f"  {msg}", fg=style if style != "yellow" else "yellow")


def _stream_tokens(gen, ai_name: str) -> str:
    """토큰 스트리밍 + 생성 중 표시. 전체 누적 문자열 반환."""
    if _HAS_RICH:
        _console.print(f"\n[bold green]{ai_name}[/bold green]")
        _console.print("─" * 44)
    else:
        click.secho(f"\n{ai_name}:", fg="green", bold=True)
        click.secho("─" * 44, fg="cyan")

    accumulated = ""
    try:
        for token in gen:
            print(token, end="", flush=True)
            accumulated += token
        print()
    except Exception as e:
        print()
        _status(f"오류: {e}", "red")

    # 마크다운 재렌더링 (코드블록 등 포함 시)
    if _HAS_RICH and accumulated and (
        "```" in accumulated or "**" in accumulated or "##" in accumulated
    ):
        print()
        try:
            _console.print(_RichMD(accumulated))
        except Exception:
            pass

    return accumulated


# ────────────────────────────────────────────────────────────────
# 입력 헬퍼
# ────────────────────────────────────────────────────────────────

def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def safe_input(prompt: str) -> str:
    """
    한글 입력 안전 처리:
      1. stdout flush 보장
      2. UTF-8 디코딩, 실패 시 EUC-KR 재시도
      3. NFC 정규화 (자소 분리 수정)
    """
    sys.stdout.write(prompt)
    sys.stdout.flush()
    try:
        raw = sys.stdin.buffer.readline()
    except (EOFError, KeyboardInterrupt):
        raise
    except Exception as e:
        click.secho(f"입력 오류: {e}", fg="red")
        return ""

    if not raw:
        return ""

    try:
        line = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            line = raw.decode("euc-kr")
        except UnicodeDecodeError:
            line = raw.decode("utf-8", errors="replace")

    line = line.rstrip("\r\n").strip()
    # NFC 정규화만 적용 (ghost 제거는 오탐 위험으로 미사용)
    return _nfc(line)


def _multi_line_input(prompt: str) -> str:
    """
    다중 줄 입력 지원.
      - 줄 끝 \\ → 다음 줄 연속
      - <<< 입력 → >>> 까지 블록 입력
    """
    first = safe_input(prompt)

    # 블록 모드: <<< 로 시작
    if first.strip() == "<<<":
        lines = []
        while True:
            try:
                line = safe_input("... ")
            except (KeyboardInterrupt, EOFError):
                break
            if line.strip() == ">>>":
                break
            lines.append(line)
        return "\n".join(lines)

    # 줄 연속 모드: 끝이 \\
    lines = [first]
    while lines[-1].endswith("\\"):
        lines[-1] = lines[-1][:-1]
        try:
            lines.append(safe_input("... "))
        except (KeyboardInterrupt, EOFError):
            break
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────
# 기타 유틸
# ────────────────────────────────────────────────────────────────

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
        title = title.strip().splitlines()[0]
        title = title.replace(" ", "-").replace("/", "-")
        title = title.strip("\"'\u201c\u201d\u2018\u2019")
        return title[:40] or generate_default_session_name()
    except Exception:
        return generate_default_session_name()


def print_session_history(session: Session, ai_name: str) -> None:
    for message in session.messages:
        if message.role == "user":
            _print_user(message.content)
        elif message.role == "assistant":
            _print_ai(ai_name, message.content)
        elif message.role == "system":
            _status(f"[system]: {message.content}", "blue")


# ────────────────────────────────────────────────────────────────
# 메인 대화 루프
# ────────────────────────────────────────────────────────────────

def run_chat_loop(
    session: Session,
    backend: BaseBackend,
    ai_name: str,
    lang: str,
    persona=None,
) -> None:
    """
    TUI 와 동등한 기능의 CLI 대화 루프.

    TUI 대비 동등 기능:
      - Persona 시스템 프롬프트 적용
      - 장기 메모리 컨텍스트 자동 주입 + 응답 후 자동 추출
      - 웹 검색 자동 감지 (최신 정보 필요 시)
      - Rich 마크다운 렌더링
      - 다중 줄 입력 (\\\\, <<<...>>>)
      - 자동 제목 생성 (세션 종료 전)
      - 슬래시 명령어 전체 집합

    슬래시 명령어:
      /search <query> [--week|--day|--month]   웹 검색
      /remember <key>:<value>                  메모리 저장
      /forget <key>                            메모리 삭제
      /memory                                  메모리 목록
      /persona [name]                          페르소나 전환/목록
      /clear                                   대화 초기화
      /save [name]                             세션 이름 지정
      /title                                   현재 세션 제목 강제 생성
      /save-msg <file>                         마지막 AI 응답 저장
      /history                                 현재 세션 히스토리 출력
      /about                                   버전/정보
      /exit                                    종료

    다중 줄 입력:
      줄 끝에 \\\\  →  다음 줄 연속
      <<< 입력    →  >>> 까지 블록 입력
    """
    from znc.core.config import load_settings, SESSIONS_DIR
    from znc.core.i18n import get_message, ui as _ui
    from znc.core.memory import build_memory_context, add_manual, remove_manual, load_all
    from znc.core.search_intent import detect_search_intent
    from znc.core.persona import load_default_persona, load_persona, list_personas
    from znc.core.models import Message
    from znc.core.repository import ProjectRepository

    settings = load_settings()
    engines = settings.get("search_engines", ["ddg", "naver"])
    serper_key = settings.get("google_serper_key", "")
    title_generated = False

    # Persona 시스템 프롬프트 결정
    if persona is None:
        persona = load_default_persona()

    def _build_system(extra: str = "") -> str:
        mem_ctx = build_memory_context()
        parts = []
        # 페르소나 + 메모리
        effective = persona.build_system_prompt(
            extra_context="\n".join(filter(None, [mem_ctx, extra]))
        )
        if session.system_prompt:
            parts.append(session.system_prompt)
        parts.append(effective)
        return "\n".join(filter(None, parts))

    # 시작 힌트 출력
    if _HAS_RICH:
        _console.print(
            f"\n[bold yellow]znc[/bold yellow]  "
            f"[dim]{ai_name}[/dim]  "
            f"[dim]{settings.get('backend','ollama')}[/dim]"
        )
        if session.project:
            _console.print(f"[dim]  project: {session.project}[/dim]")
        if persona and persona.name != "default":
            _console.print(f"[dim]  persona: {persona.name}[/dim]")
        _console.print(
            "[dim]  /exit 또는 Ctrl+C 종료  |  \\\\ 줄연속  |  <<< 블록입력[/dim]"
        )
    else:
        click.secho(get_message(lang, "exit_tip"), fg="yellow")

    click.secho(
        "  /search  /remember  /forget  /memory  /persona  /history  /save-msg  /about",
        fg="blue", dim=True,
    )

    # ── 대화 루프 ──────────────────────────────────────────────────
    while True:
        try:
            user_input = _multi_line_input("\n> ")
        except (KeyboardInterrupt, EOFError):
            click.secho("\n종료합니다.", fg="yellow")
            break

        if user_input.lower() in {"/exit", "exit", "quit", "/quit"}:
            click.secho("종료합니다.", fg="yellow")
            break
        if not user_input:
            continue

        # ── 슬래시 명령어 ─────────────────────────────────────────
        if user_input.startswith("/"):
            parts = user_input.split(None, 1)
            cmd  = parts[0].lower()
            arg  = parts[1].strip() if len(parts) > 1 else ""

            # /search
            if cmd == "/search":
                if not arg:
                    _status("usage: /search <검색어> [--week|--day|--month]")
                    continue
                freshness, query = "", arg
                for flag, code in (("--week", "w"), ("--day", "d"), ("--month", "m")):
                    if flag in query:
                        freshness, query = code, query.replace(flag, "").strip()
                _cli_search(query, engines, serper_key, session, backend, ai_name,
                            freshness=freshness, build_system_fn=_build_system)
                title_generated = False
                continue

            # /remember
            if cmd == "/remember":
                _cli_remember(arg)
                continue

            # /forget
            if cmd == "/forget":
                _cli_forget(arg)
                continue

            # /memory
            if cmd == "/memory":
                _cli_show_memory()
                continue

            # /persona [name]
            if cmd == "/persona":
                if arg:
                    p = load_persona(arg.strip())
                    if p:
                        persona = p
                        _status(f"페르소나 전환: {p.name}", "green")
                    else:
                        _status(f"페르소나를 찾을 수 없습니다: {arg}", "red")
                else:
                    click.secho("사용 가능한 페르소나:", fg="cyan")
                    for p in list_personas():
                        marker = " *" if p.name == persona.name else ""
                        click.echo(f"  {p.name}{marker}  [{p.description}]")
                continue

            # /clear
            if cmd == "/clear":
                session.messages.clear()
                title_generated = False
                _status("대화를 초기화했습니다.", "cyan")
                continue

            # /save [name]
            if cmd == "/save":
                if arg:
                    session.name = arg
                    _status(f"세션 이름: {session.name}", "cyan")
                else:
                    _status(f"현재 세션: {session.name}", "cyan")
                continue

            # /title
            if cmd == "/title":
                if len(session.messages) >= 2:
                    _status("제목 생성 중...", "cyan")
                    title = generate_session_title(session, backend)
                    session.name = title
                    title_generated = True
                    _status(f"제목: {title}", "green")
                else:
                    _status("대화 내용이 부족합니다.", "yellow")
                continue

            # /save-msg <file>
            if cmd in ("/save-msg", "/savemsg"):
                _cli_save_last_msg(session, arg or None, ai_name)
                continue

            # /history
            if cmd == "/history":
                if session.messages:
                    print_session_history(session, ai_name)
                else:
                    _status("아직 대화 내용이 없습니다.", "yellow")
                continue

            # /about
            if cmd == "/about":
                _cli_show_about()
                continue

            # /delete
            if cmd == "/delete":
                _status("headless 모드에서는 세션 파일을 직접 삭제하세요.", "yellow")
                _status(f"파일: {session.name}.json", "dim")
                continue

            # /export
            if cmd in ("/export",):
                if not arg:
                    _status("usage: /export <filepath>")
                    continue
                _cli_export(session, arg, ai_name)
                continue

            _status(f"알 수 없는 명령어: {cmd}  (/search /memory /persona /history /about ...)", "yellow")
            continue

        # ── 일반 메시지 처리 ──────────────────────────────────────
        # 최신 정보 필요 여부 자동 감지
        needs_search, reason = detect_search_intent(user_input)
        if needs_search:
            _status(f"최신 정보 자동 검색 ({reason})", "cyan")
            _cli_search(user_input, engines, serper_key, session, backend, ai_name,
                        freshness="w", build_system_fn=_build_system)
            title_generated = False
            continue

        # 사용자 메시지 기록
        session.append(Message(role="user", content=user_input))
        prompt = build_prompt(session, ai_name)
        system = _build_system()

        _status("생성 중...", "dim")
        accumulated = _stream_tokens(backend.stream(prompt, system_prompt=system), ai_name)

        if not accumulated:
            session.messages.pop()
            continue

        session.append(Message(role="assistant", content=accumulated))

        # 자동 메모리 추출 (백그라운드)
        try:
            def _extract():
                from znc.core.memory import extract_and_save_auto
                extract_and_save_auto(accumulated, backend)
            threading.Thread(target=_extract, daemon=True).start()
        except Exception:
            pass

        title_generated = False

    # ── 세션 종료 후 처리 ────────────────────────────────────────
    if session.messages and not title_generated:
        if len(session.messages) >= 4:
            try:
                _status("세션 제목 생성 중...", "dim")
                title = generate_session_title(session, backend)
                if title and title != session.name:
                    session.name = title
                    _status(f"제목: {title}", "green")
            except Exception:
                pass


# ────────────────────────────────────────────────────────────────
# 슬래시 명령어 구현
# ────────────────────────────────────────────────────────────────

def _cli_search(
    query: str,
    engines: list[str],
    serper_key: str,
    session: Session,
    backend: BaseBackend,
    ai_name: str,
    freshness: str = "",
    build_system_fn=None,
) -> None:
    """웹 검색 → 크롤링 → 컨텍스트 삽입 → 모델 응답."""
    from znc.core.web_search import search_and_crawl
    from znc.core.models import Message
    from datetime import datetime as _dt
    from znc.core.memory import extract_and_save_auto

    engine_label = "+".join(engines)
    freshness_label = {"d": "1일", "w": "1주", "m": "1달"}.get(freshness, "전체")
    _status(f'검색 중 [{engine_label}][{freshness_label}]: "{query}"', "yellow")

    def progress(url: str, done: int, total: int) -> None:
        if url:
            domain = url.split("/")[2] if url.count("/") >= 2 else url
            _status(f"  크롤링: {domain}", "blue")

    results, context = search_and_crawl(
        query, engines=engines, google_serper_key=serper_key,
        freshness=freshness, progress_callback=progress,
    )

    if not context:
        _status("검색 결과가 없습니다.", "red")
        return

    search_date = _dt.now().strftime("%Y-%m-%d %H:%M")
    _status(f"  결과 {len(results)}건  ({search_date})", "cyan")

    # 사용자 질문을 히스토리에 기록
    session.append(Message(role="user", content=query))
    full_prompt = build_prompt(session, ai_name)
    session.messages.pop()

    dated_ctx = f"[검색 날짜: {search_date}]\n{context}"
    actual_prompt = (
        full_prompt.rstrip(f"{ai_name}:").rstrip()
        + f"\n[context]\n{dated_ctx}\n위 검색 결과를 바탕으로 '{query}' 에 대해 답해줘.\n{ai_name}:"
    )

    system = build_system_fn() if build_system_fn else (session.system_prompt or None)
    accumulated = _stream_tokens(backend.stream(actual_prompt, system_prompt=system), ai_name)

    if accumulated:
        session.append(Message(role="user", content=f"[search: {query}]"))
        session.append(Message(role="assistant", content=accumulated))
        try:
            def _extract():
                extract_and_save_auto(accumulated, backend)
            threading.Thread(target=_extract, daemon=True).start()
        except Exception:
            pass


def _cli_remember(arg: str) -> None:
    from znc.core.memory import add_manual
    if ":" in arg:
        key, _, val = arg.partition(":")
    else:
        key, val = arg.strip(), arg.strip()
    key, val = key.strip(), val.strip()
    if not key:
        _status("usage: /remember <key>:<value>")
        return
    add_manual(key, val)
    _status(f"기억 저장: {key} = {val}", "green")


def _cli_forget(arg: str) -> None:
    from znc.core.memory import remove_manual
    key = arg.strip()
    if not key:
        _status("usage: /forget <key>")
        return
    removed = remove_manual(key)
    _status(f"기억 삭제: {key}" if removed else f"해당 키 없음: {key}",
            "green" if removed else "yellow")


def _cli_show_memory() -> None:
    from znc.core.memory import load_all
    items = load_all()
    if not items:
        _status("저장된 메모리가 없습니다.", "cyan")
        return
    click.secho("저장된 메모리:", fg="cyan")
    for item in items:
        src = "m" if item.source == "manual" else "a"
        click.echo(f"  [{src}] {item.key}: {item.value}")


def _cli_save_last_msg(session: Session, filepath: Optional[str], ai_name: str) -> None:
    """마지막 AI 응답을 파일로 저장 (콘텐츠 타입 자동 감지)."""
    ai_msgs = [m for m in session.messages if m.role == "assistant"]
    if not ai_msgs:
        _status("저장할 AI 응답이 없습니다.", "yellow")
        return

    last = ai_msgs[-1].content
    try:
        from znc.core.content_detector import detect_and_extract, clean_content_for_ext
        result = detect_and_extract(last)
        content = clean_content_for_ext(result.content, result.ext)
        if not filepath:
            from znc.core.config import ZNC_DIR
            outdir = os.path.join(ZNC_DIR, "output")
            os.makedirs(outdir, exist_ok=True)
            filepath = os.path.join(outdir, result.filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        _status(f"저장됨: {filepath}  ({result.display})", "green")
    except Exception as e:
        _status(f"저장 오류: {e}", "red")


def _cli_export(session: Session, filepath: str, ai_name: str) -> None:
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"znc — Chat Export\n{'─' * 44}\n")
            f.write(f"Session : {session.name}\n\n")
            for m in session.messages:
                if m.role == "user":
                    f.write(f"you:\n{m.content}\n\n")
                elif m.role == "assistant":
                    f.write(f"{ai_name}:\n{m.content}\n\n")
        _status(f"내보내기 완료: {filepath}", "green")
    except Exception as e:
        _status(f"내보내기 오류: {e}", "red")


def _cli_show_about() -> None:
    try:
        from znc.version import VERSION, BUILD
        from znc.core.config import load_settings
        settings = load_settings()
        backend = settings.get("backend", "ollama")
        model = settings.get("openai_model") if backend == "openai" else settings.get("model", "")
        if _HAS_RICH:
            _console.print(f"\n[bold yellow]znc[/bold yellow] — Personal AI CLI")
            _console.print(f"  version [green]{VERSION}[/green]  build [dim]#{BUILD}[/dim]")
            _console.print(f"  backend [cyan]{backend}[/cyan]  model [dim]{model}[/dim]")
        else:
            click.echo(f"\nznc v{VERSION} build #{BUILD}")
            click.echo(f"  backend: {backend}  model: {model}")
    except Exception:
        click.echo("znc — Personal AI CLI")
