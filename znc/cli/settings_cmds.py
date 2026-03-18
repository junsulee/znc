"""
znc CLI — settings 명령어
"""
from __future__ import annotations

import click

from znc.core.config import load_settings, save_settings
from znc.core.i18n import get_message


@click.command("settings", help="전역 설정 관리")
@click.option("--lang", type=click.Choice(["ko", "en"]), default=None, help="언어 설정")
@click.option("--ai-name", default=None, help="AI 이름")
@click.option(
    "--backend",
    default=None,
    type=click.Choice(["ollama", "openai"]),
    help="AI 백엔드 선택",
)
@click.option("--model", default=None, help="Ollama 모델명")
@click.option("--server-url", default=None, help="Ollama 서버 URL")
@click.option("--openai-api-key", default=None, help="OpenAI API 키")
@click.option("--openai-model", default=None, help="OpenAI 모델명")
@click.option("--openai-base-url", default=None, help="OpenAI 호환 서버 URL")
@click.option(
    "--search-engines",
    default=None,
    help="검색 엔진 콤마 구분 (ddg,naver,google)",
)
@click.option("--google-serper-key", default=None, help="Serper.dev API 키 (Google 검색용)")
@click.option("--show", is_flag=True, default=False, help="현재 설정 출력")
def cmd_settings(
    lang,
    ai_name,
    backend,
    model,
    server_url,
    openai_api_key,
    openai_model,
    openai_base_url,
    search_engines,
    google_serper_key,
    show,
):
    current = load_settings()
    effective_lang = lang or current.get("lang", "ko")

    if show:
        click.secho("⚙️  현재 설정:", fg="cyan", bold=True)
        masked = dict(current)
        if masked.get("openai_api_key"):
            masked["openai_api_key"] = masked["openai_api_key"][:8] + "..."
        for k, v in masked.items():
            click.echo(f"  {k:20s} = {v}")
        return

    if lang:
        current["lang"] = lang
        click.secho(get_message(effective_lang, "lang_set", lang=lang), fg="cyan")
    if ai_name:
        current["ai_name"] = ai_name
        click.secho(get_message(effective_lang, "ai_name_set", name=ai_name), fg="cyan")
    if backend:
        current["backend"] = backend
        click.secho(get_message(effective_lang, "backend_set", backend=backend), fg="cyan")
    if model:
        current["model"] = model
        click.secho(get_message(effective_lang, "model_set", model=model), fg="cyan")
    if server_url:
        current["server_url"] = server_url
        click.secho(get_message(effective_lang, "server_url_set", url=server_url), fg="cyan")
    if openai_api_key:
        current["openai_api_key"] = openai_api_key
        click.secho(get_message(effective_lang, "openai_key_set"), fg="cyan")
    if openai_model:
        current["openai_model"] = openai_model
        click.secho(
            get_message(effective_lang, "openai_model_set", model=openai_model), fg="cyan"
        )
    if openai_base_url:
        current["openai_base_url"] = openai_base_url
        click.secho(
            get_message(effective_lang, "server_url_set", url=openai_base_url), fg="cyan"
        )
    if search_engines:
        engines = [e.strip() for e in search_engines.split(",") if e.strip()]
        valid = {"ddg", "naver", "google"}
        engines = [e for e in engines if e in valid]
        if engines:
            current["search_engines"] = engines
            click.secho(f"✅ 검색 엔진 설정: {', '.join(engines)}", fg="cyan")
    if google_serper_key:
        current["google_serper_key"] = google_serper_key
        click.secho("✅ Google Serper API 키 설정 완료", fg="cyan")

    save_settings(current)
    click.secho(get_message(effective_lang, "settings_updated"), fg="green")
