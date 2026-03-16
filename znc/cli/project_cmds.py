"""
znc CLI — 프로젝트 관리 명령어
"""
from __future__ import annotations

import sys

import click

from znc.core.config import load_settings, save_project_settings
from znc.core.i18n import get_message
from znc.core.repository import ProjectRepository


@click.group("project", help="프로젝트 관리 (new/ls/rm/info/settings)")
def cmd_project():
    pass


@cmd_project.command("new", help="새 프로젝트 생성")
@click.argument("name")
@click.option("--desc", "-d", default="", help="프로젝트 설명")
@click.option("--system", "-s", default="", help="프로젝트 기본 시스템 프롬프트")
def project_new(name, desc, system):
    settings = load_settings()
    lang = settings.get("lang", "ko")

    if ProjectRepository.get(name):
        click.secho(f"⚠️  이미 존재하는 프로젝트: {name}", fg="yellow")
        sys.exit(1)

    ProjectRepository.create(name, description=desc, system_prompt=system)
    click.secho(get_message(lang, "project_created", name=name), fg="green")
    if system:
        click.secho(f"   시스템 프롬프트: {system[:80]}{'...' if len(system) > 80 else ''}", fg="cyan")


@cmd_project.command("ls", help="프로젝트 목록 보기")
def project_ls():
    settings = load_settings()
    lang = settings.get("lang", "ko")

    projects = ProjectRepository.list_all()
    if not projects:
        click.secho(get_message(lang, "no_projects"), fg="cyan")
        return

    click.secho(get_message(lang, "project_list_header"), fg="green")
    for p in projects:
        desc = f" — {p.description}" if p.description else ""
        click.echo(f"  - {p.name}{desc}")


@cmd_project.command("rm", help="프로젝트 삭제 (세션 포함)")
@click.argument("name")
@click.confirmation_option(prompt="프로젝트와 모든 세션을 삭제하시겠습니까?")
def project_rm(name):
    settings = load_settings()
    lang = settings.get("lang", "ko")

    if not ProjectRepository.delete(name):
        click.secho(get_message(lang, "project_not_found", name=name), fg="red")
        sys.exit(1)
    click.secho(get_message(lang, "project_deleted", name=name), fg="cyan")


@cmd_project.command("info", help="프로젝트 상세 정보")
@click.argument("name")
def project_info(name):
    settings = load_settings()
    lang = settings.get("lang", "ko")

    proj = ProjectRepository.get(name)
    if proj is None:
        click.secho(get_message(lang, "project_not_found", name=name), fg="red")
        sys.exit(1)

    click.secho(f"📁 프로젝트: {proj.name}", fg="cyan", bold=True)
    if proj.description:
        click.echo(f"   설명    : {proj.description}")
    if proj.system_prompt:
        click.echo(f"   시스템  : {proj.system_prompt}")
    click.echo(f"   생성일  : {proj.created_at}")

    sessions = ProjectRepository.list_sessions(name)
    click.echo(f"   세션 수 : {len(sessions)}")
    for s in sessions:
        click.echo(f"     - {s}")


@cmd_project.command("settings", help="프로젝트별 설정 덮어쓰기")
@click.argument("name")
@click.option("--model", default=None)
@click.option("--backend", default=None, type=click.Choice(["ollama", "openai"]))
@click.option("--server-url", default=None)
@click.option("--ai-name", default=None)
@click.option("--system", default=None, help="시스템 프롬프트")
def project_settings(name, model, backend, server_url, ai_name, system):
    settings_global = load_settings()
    lang = settings_global.get("lang", "ko")

    proj = ProjectRepository.get(name)
    if proj is None:
        click.secho(get_message(lang, "project_not_found", name=name), fg="red")
        sys.exit(1)

    import json, os
    from znc.core.config import get_project_settings_path

    cfg_path = get_project_settings_path(name)
    cfg: dict = {}
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

    if model:
        cfg["model"] = model
        click.secho(get_message(lang, "model_set", model=model), fg="cyan")
    if backend:
        cfg["backend"] = backend
        click.secho(get_message(lang, "backend_set", backend=backend), fg="cyan")
    if server_url:
        cfg["server_url"] = server_url
        click.secho(get_message(lang, "server_url_set", url=server_url), fg="cyan")
    if ai_name:
        cfg["ai_name"] = ai_name
        click.secho(get_message(lang, "ai_name_set", name=ai_name), fg="cyan")
    if system:
        # project.json 의 system_prompt 도 업데이트
        import json as _json
        from znc.core.config import get_project_dir
        meta_path = os.path.join(get_project_dir(name), "project.json")
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = _json.load(f)
        meta["system_prompt"] = system
        with open(meta_path, "w", encoding="utf-8") as f:
            _json.dump(meta, f, indent=2, ensure_ascii=False)
        click.secho(f"✅ 시스템 프롬프트 업데이트 완료", fg="cyan")

    save_project_settings(name, cfg)
    click.secho(get_message(lang, "settings_updated"), fg="green")
