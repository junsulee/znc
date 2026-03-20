"""
CLI 공통 유틸리티 함수
"""
from __future__ import annotations

import sys
import unicodedata
from datetime import datetime

import click

from znc.backends.base import BaseBackend
from znc.core.models import Session
from znc.core.text_utils import sanitize_korean


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def safe_input(prompt: str) -> str:
    """
    한글 입력 안전 처리:
      1. stdout flush 보장 (프롬프트가 즉시 표시되도록)
      2. 바이너리 버퍼에서 직접 읽어 인코딩 오류 방지
      3. UTF-8 디코딩 실패 시 EUC-KR 재시도 (일부 SSH 클라이언트 대응)
      4. NFC 정규화 — 자소분리(NFD 자모) → 완성형 음절로 조합
      5. 중복 자모 감지: 완성형 음절 앞에 동일 초성 자모가 붙은 경우 제거
    """
    sys.stdout.write(prompt)
    sys.stdout.flush()
    try:
        raw = sys.stdin.buffer.readline()
    except (EOFError, KeyboardInterrupt):
        raise
    except Exception as e:
        click.secho(f"❌ 입력 오류: {e}", fg="red")
        return ""

    if not raw:
        return ""

    # ── 인코딩 디코딩 ──────────────────────────────────────────────
    line: str
    try:
        line = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            line = raw.decode("euc-kr")
        except UnicodeDecodeError:
            line = raw.decode("utf-8", errors="replace")
            click.secho(
                "⚠️  입력에 인식 불가 문자가 포함되었습니다 (UTF-8/EUC-KR 모두 실패).",
                fg="yellow",
            )

    line = line.rstrip("\r\n").strip()

    # ── NFC 정규화 (자소분리 수정) ──────────────────────────────────
    line = _nfc(line)

    # IME ghost 제거: 자소분리·중복 자모·조합 중간 상태 수정
    line = sanitize_korean(line)

    return line


# 한글 자모 범위 (호환 자모 U+3131~U+318E, 채움 문자 포함)
_COMPAT_JAMO_START = 0x3131
_COMPAT_JAMO_END   = 0x318E
# NFC 조합 음절 범위 U+AC00~U+D7A3
_SYLLABLE_START = 0xAC00
_SYLLABLE_END   = 0xD7A3
# 초성 인덱스 (가-힣 구조: 초성 21*28 + 중성 28 + 종성)
_INITIAL_CONSONANTS = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"


def _syllable_initial(ch: str) -> str:
    """NFC 음절의 초성 자모 반환. 음절이 아니면 빈 문자열."""
    cp = ord(ch)
    if not (_SYLLABLE_START <= cp <= _SYLLABLE_END):
        return ""
    idx = (cp - _SYLLABLE_START) // (21 * 28)
    return _INITIAL_CONSONANTS[idx] if idx < len(_INITIAL_CONSONANTS) else ""


def _is_compat_jamo(ch: str) -> bool:
    return _COMPAT_JAMO_START <= ord(ch) <= _COMPAT_JAMO_END


def _remove_leading_jamo_duplicates(text: str) -> str:
    """
    패턴: <호환 자모> <해당 자모가 초성인 음절>
    예)  'ㄱ가나다' → '가나다'
         'ㅎ하하하' → '하하하'  (앞의 ㅎ만 제거, 뒤 음절은 유지)
    """
    if len(text) < 2:
        return text
    result = list(text)
    i = 0
    while i < len(result) - 1:
        cur = result[i]
        nxt = result[i + 1]
        if (
            _is_compat_jamo(cur)
            and _SYLLABLE_START <= ord(nxt) <= _SYLLABLE_END
            and cur == _syllable_initial(nxt)
        ):
            result.pop(i)   # 자모 제거, i는 그대로 → 다음 문자 재검사
        else:
            i += 1
    return "".join(result)


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
            click.secho(f"User: {message.content}", fg="yellow")
        elif message.role == "assistant":
            click.secho(f"{ai_name}: {message.content}", fg="green")
        elif message.role == "system":
            click.secho(f"[system]: {message.content}", fg="blue", dim=True)


def run_chat_loop(
    session: Session,
    backend: BaseBackend,
    ai_name: str,
    lang: str,
) -> None:
    """
    대화 루프. session.messages 에 메시지를 추가한다.

    슬래시 명령어:
      /search <query>       웹 검색 후 컨텍스트 삽입
      /remember <key>:<val> 장기 메모리 저장
      /forget <key>         장기 메모리 삭제
      /clear                대화 초기화
      /save <name>          세션 저장 이름 지정
      /memory               저장된 메모리 목록
      /exit                 종료
    """
    from znc.core.i18n import get_message
    from znc.core.config import load_settings

    settings = load_settings()
    engines = settings.get("search_engines", ["ddg", "naver"])
    serper_key = settings.get("google_serper_key", "")

    click.secho(get_message(lang, "exit_tip"), fg="yellow")
    click.secho(
        "  /search <query>  /remember <k>:<v>  /forget <k>  /clear  /memory",
        fg="blue",
        dim=True,
    )

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

        # ── 슬래시 명령어 처리 ────────────────────────────────────────
        if user_input.startswith("/"):
            parts = user_input.split(None, 1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == "/search":
                if not arg:
                    click.secho("usage: /search <검색어>", fg="yellow")
                    continue
                _cli_search(arg, engines, serper_key, session, backend, ai_name)
                continue

            if cmd == "/remember":
                _cli_remember(arg)
                continue

            if cmd == "/forget":
                _cli_forget(arg)
                continue

            if cmd == "/clear":
                session.messages.clear()
                click.secho("대화 기록을 초기화했습니다.", fg="cyan")
                continue

            if cmd == "/memory":
                _cli_show_memory()
                continue

            if cmd == "/save":
                if arg.strip():
                    session.name = arg.strip()
                    click.secho(f"세션 이름이 '{session.name}' 으로 설정됩니다.", fg="cyan")
                continue

            click.secho(f"알 수 없는 명령어: {cmd}", fg="yellow")
            continue
        # ──────────────────────────────────────────────────────────────

        from znc.core.models import Message
        from znc.core.memory import build_memory_context

        # 메모리 컨텍스트 삽입
        mem_ctx = build_memory_context(user_input)

        session.append(Message(role="user", content=user_input))
        prompt = build_prompt(session, ai_name)

        # 시스템 프롬프트 (메모리 + 세션 시스템 프롬프트 조합)
        system_parts = []
        if session.system_prompt:
            system_parts.append(session.system_prompt)
        if mem_ctx:
            system_parts.append(mem_ctx)
        effective_system = "\n".join(system_parts) or None

        click.secho("\n" + "─" * 44, fg="cyan")
        click.secho(f"{ai_name}:", fg="green", bold=True)
        click.secho("─" * 44, fg="cyan")

        accumulated = ""
        try:
            for token in backend.stream(prompt, system_prompt=effective_system):
                print(token, end="", flush=True)
                accumulated += token
            print()
        except Exception as e:
            click.secho(f"\n❌ API 오류: {e}", fg="red")
            session.messages.pop()
            continue

        session.append(Message(role="assistant", content=accumulated))


# ---------------------------------------------------------------------------
# 헤드리스 슬래시 명령어 구현
# ---------------------------------------------------------------------------

def _cli_search(
    query: str,
    engines: list[str],
    serper_key: str,
    session: Session,
    backend: BaseBackend,
    ai_name: str,
) -> None:
    """웹 검색 → 크롤링 → 컨텍스트 삽입 → 모델 응답."""
    from znc.core.web_search import search_and_crawl
    from znc.core.models import Message

    engine_label = "+".join(engines)
    click.secho(f'검색 중 [{engine_label}]: "{query}"', fg="yellow")

    def progress(url: str, done: int, total: int) -> None:
        if url:
            domain = url.split("/")[2] if url.count("/") >= 2 else url
            click.secho(f"  크롤링: {domain}", fg="blue", dim=True)

    results, context = search_and_crawl(
        query,
        engines=engines,
        google_serper_key=serper_key,
        progress_callback=progress,
    )

    if not context:
        click.secho("검색 결과가 없습니다.", fg="red")
        return

    click.secho(f"  결과 {len(results)}건 수집 완료", fg="cyan")

    # 검색 컨텍스트를 포함한 프롬프트 구성
    context_prompt = (
        f"[웹 검색 컨텍스트: {query}]\n{context}\n\n"
        f"위 검색 결과를 바탕으로 '{query}' 에 대해 답해줘."
    )
    session.append(Message(role="user", content=f"/search {query}"))
    full_prompt = build_prompt(session, ai_name)
    session.messages.pop()  # 프롬프트 빌드용 임시 메시지 제거

    actual_prompt = full_prompt.rstrip(f"{ai_name}:").rstrip() + \
        f"\n[context]\n{context_prompt}\n{ai_name}:"

    click.secho("\n" + "─" * 44, fg="cyan")
    click.secho(f"{ai_name}:", fg="green", bold=True)
    click.secho("─" * 44, fg="cyan")

    accumulated = ""
    try:
        for token in backend.stream(actual_prompt, system_prompt=session.system_prompt):
            print(token, end="", flush=True)
            accumulated += token
        print()
    except Exception as e:
        click.secho(f"\n❌ API 오류: {e}", fg="red")
        return

    # 검색 질문과 답변을 히스토리에 추가
    session.append(Message(role="user", content=f"[search: {query}]"))
    session.append(Message(role="assistant", content=accumulated))


def _cli_remember(arg: str) -> None:
    from znc.core.memory import add_manual
    if ":" in arg:
        key, _, val = arg.partition(":")
    else:
        key, val = arg.strip(), arg.strip()
    key, val = key.strip(), val.strip()
    if not key:
        click.secho("usage: /remember <key>:<value>", fg="yellow")
        return
    add_manual(key, val)
    click.secho(f"기억 저장: {key} = {val}", fg="green")


def _cli_forget(arg: str) -> None:
    from znc.core.memory import remove_manual
    key = arg.strip()
    if not key:
        click.secho("usage: /forget <key>", fg="yellow")
        return
    removed = remove_manual(key)
    if removed:
        click.secho(f"기억 삭제: {key}", fg="green")
    else:
        click.secho(f"해당 키를 찾을 수 없습니다: {key}", fg="yellow")


def _cli_show_memory() -> None:
    from znc.core.memory import load_all
    items = load_all()
    if not items:
        click.secho("저장된 메모리가 없습니다.", fg="cyan")
        return
    click.secho("저장된 메모리:", fg="cyan")
    for item in items:
        src = "manual" if item.source == "manual" else "auto"
        click.secho(f"  [{src}] {item.key}: {item.value}", fg="white")
