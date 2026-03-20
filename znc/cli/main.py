"""
znc CLI 메인 진입점.

`znc`          → TUI 실행
`znc <cmd>`    → 기존 CLI 서브커맨드 (headless 환경용)
"""
from __future__ import annotations

import io
import os
import sys

import click

from znc.cli.session_cmds import cmd_new, cmd_load, cmd_ls, cmd_rm, cmd_export
from znc.cli.settings_cmds import cmd_settings
from znc.cli.project_cmds import cmd_project


def _setup_encoding() -> None:
    """
    SSH 환경에서 한글 입력이 깨지는 문제를 예방하기 위해
    Python I/O 스트림을 UTF-8로 강제 설정한다.

    증상:
      - 자소분리: '가' → 'ㄱㅏ'  (SSH 클라이언트가 NFD로 전송)
      - 중복입력: IME 미리보기 자모 + 조합 완성 문자 이중 수신

    PYTHONIOENCODING / PYTHONUTF8 환경 변수는 이미 실행된 프로세스에
    영향을 주지 않으므로, reconfigure() 로 직접 재설정한다.
    """
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

    for name, stream in (("stdout", sys.stdout), ("stderr", sys.stderr), ("stdin", sys.stdin)):
        if stream is None:
            continue
        if not hasattr(stream, "reconfigure"):
            continue
        try:
            enc = getattr(stream, "encoding", None) or ""
            if enc.lower().replace("-", "") != "utf8":
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


@click.group(
    context_settings=dict(help_option_names=["-h", "--help"]),
    invoke_without_command=True,
)
@click.pass_context
def cli(ctx):
    """znc — 개인용 AI CLI.

    인수 없이 실행하면 풀스크린 TUI가 실행됩니다.
    서브커맨드를 지정하면 headless 모드로 동작합니다.
    """
    if ctx.invoked_subcommand is None:
        from znc.tui.app import ZncApp
        ZncApp().run()


cli.add_command(cmd_new)
cli.add_command(cmd_load)
cli.add_command(cmd_ls)
cli.add_command(cmd_rm)
cli.add_command(cmd_export)
cli.add_command(cmd_settings)
cli.add_command(cmd_project)


def main():
    _setup_encoding()
    cli()


if __name__ == "__main__":
    main()
