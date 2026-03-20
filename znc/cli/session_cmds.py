"""
znc CLI — session 관련 명령어 (new, load, ls, rm, export)
"""
from __future__ import annotations

import os
import sys

import click

from znc.backends.base import BaseBackend
from znc.cli.utils import (
    generate_default_session_name,
    generate_session_title,
    print_session_history,
    run_chat_loop,
)
from znc.core.config import (
    SESSIONS_DIR,
    load_settings,
    ensure_dirs,
)
from znc.core.i18n import get_message
from znc.core.models import Session
from znc.core.repository import ProjectRepository


def _resolve_sessions_dir(project: str | None) -> str:
    if project:
        return ProjectRepository.sessions_dir(project)
    ensure_dirs()
    return SESSIONS_DIR


# ---------------------------------------------------------------------------
# new
# ---------------------------------------------------------------------------
@click.command("new", help="새 대화 세션 시작")
@click.option("--save", "-s", default=None, help="세션 저장 이름")
@click.option("--project", "-p", default=None, help="연결할 프로젝트 이름")
@click.option(
    "--auto-title/--no-auto-title",
    default=True,
    show_default=True,
    help="자동 제목 생성 여부",
)
@click.option("--system", default=None, help="시스템 프롬프트 (세션 단위 덮어쓰기)")
def cmd_new(save, project, auto_title, system):
    settings = load_settings()
    lang = settings.get("lang", "ko")
    ai_name = settings.get("ai_name", "znc")

    if project:
        from znc.core.repository import ProjectRepository as PR
        proj = PR.get(project)
        if proj is None:
            click.secho(get_message(lang, "project_not_found", name=project), fg="red")
            sys.exit(1)
        effective_system = system or proj.system_prompt or None
    else:
        effective_system = system or None

    click.secho(f"\n{get_message(lang, 'welcome')}", fg="cyan", bold=True)
    click.secho(f"{get_message(lang, 'desc')}\n", fg="cyan")

    session_name = save or "__tmp__"
    session = Session(
        name=session_name,
        project=project,
        system_prompt=effective_system,
    )

    backend = BaseBackend.from_settings(settings)
    from znc.core.persona import load_default_persona
    persona = load_default_persona()
    run_chat_loop(session, backend, ai_name, lang, persona=persona)

    sessions_dir = _resolve_sessions_dir(project)

    if session.messages:
        if not save:
            if auto_title and len(session.messages) >= 4:
                session_name = generate_session_title(session, backend)
                click.secho(f"✅ 생성된 세션 이름: {session_name}", fg="green")
            else:
                session_name = generate_default_session_name()
                click.secho(
                    f"ℹ️  자동 생성된 세션 이름: {session_name}", fg="cyan"
                )

        session.name = session_name
        path = session.save(sessions_dir)
        click.secho(get_message(lang, "session_saved", path=path), fg="cyan")
    else:
        click.secho("ℹ️  대화 내용이 없어 저장하지 않습니다.", fg="yellow")


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------
@click.command("load", help="기존 세션 불러오기 (이어서 대화)")
@click.argument("name")
@click.option("--project", "-p", default=None, help="프로젝트 이름")
@click.option("--view", is_flag=True, default=False, help="이전 대화만 출력하고 종료")
def cmd_load(name, project, view):
    settings = load_settings()
    lang = settings.get("lang", "ko")
    ai_name = settings.get("ai_name", "znc")

    sessions_dir = _resolve_sessions_dir(project)
    try:
        session = Session.load(sessions_dir, name)
    except FileNotFoundError:
        click.secho(get_message(lang, "session_not_found", name=name), fg="red")
        sys.exit(1)

    click.secho(
        get_message(lang, "session_loaded", path=os.path.join(sessions_dir, name + ".json")),
        fg="cyan",
    )
    print_session_history(session, ai_name)

    if view:
        return

    click.secho(
        get_message(lang, "session_continue", count=len(session.messages)), fg="cyan"
    )

    backend = BaseBackend.from_settings(settings)
    from znc.core.persona import load_default_persona
    persona = load_default_persona()
    run_chat_loop(session, backend, ai_name, lang, persona=persona)

    path = session.save(sessions_dir)
    click.secho(get_message(lang, "session_saved", path=path), fg="cyan")


# ---------------------------------------------------------------------------
# ls
# ---------------------------------------------------------------------------
@click.command("ls", help="저장된 세션 리스트 보기")
@click.option("--project", "-p", default=None, help="프로젝트 이름")
def cmd_ls(project):
    settings = load_settings()
    lang = settings.get("lang", "ko")

    sessions_dir = _resolve_sessions_dir(project)
    names = Session.list_names(sessions_dir)

    if not names:
        click.secho(get_message(lang, "no_sessions"), fg="cyan")
        return

    header = get_message(lang, "session_list_header")
    if project:
        header += f" (project: {project})"
    click.secho(header, fg="green")
    for n in names:
        click.echo(f"  - {n}")


# ---------------------------------------------------------------------------
# rm
# ---------------------------------------------------------------------------
@click.command("rm", help="세션 삭제")
@click.argument("name")
@click.option("--project", "-p", default=None, help="프로젝트 이름")
@click.confirmation_option(prompt="정말 삭제하시겠습니까?")
def cmd_rm(name, project):
    settings = load_settings()
    lang = settings.get("lang", "ko")

    sessions_dir = _resolve_sessions_dir(project)
    fname = name if name.endswith(".json") else f"{name}.json"
    path = os.path.join(sessions_dir, fname)
    if os.path.exists(path):
        os.remove(path)
        click.secho(get_message(lang, "session_deleted", path=path), fg="cyan")
    else:
        click.secho(get_message(lang, "session_not_found", name=name), fg="red")
        sys.exit(1)


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
@click.command("export", help="세션 내보내기 (plain text)")
@click.argument("name")
@click.option("-f", "--file", required=True, help="출력 파일 경로")
@click.option("--project", "-p", default=None, help="프로젝트 이름")
def cmd_export(name, file, project):
    settings = load_settings()
    lang = settings.get("lang", "ko")
    ai_name = settings.get("ai_name", "znc")

    sessions_dir = _resolve_sessions_dir(project)
    try:
        session = Session.load(sessions_dir, name)
    except FileNotFoundError:
        click.secho(get_message(lang, "export_error", name=name), fg="red")
        sys.exit(1)

    with open(file, "w", encoding="utf-8") as f:
        f.write(f"znc — Chat Export\n")
        f.write("─" * 44 + "\n")
        f.write(f"Session : {session.name}\n")
        if session.project:
            f.write(f"Project : {session.project}\n")
        f.write(f"Created : {session.created_at}\n")
        f.write(f"Updated : {session.updated_at}\n")
        f.write("─" * 44 + "\n\n")
        for message in session.messages:
            if message.role == "user":
                f.write(f"User:\n{message.content}\n\n")
            elif message.role == "assistant":
                f.write(f"{ai_name}:\n{message.content}\n\n")

    click.secho(get_message(lang, "export_done", file=file), fg="cyan")
