"""
znc CLI 메인 진입점.

`znc`          → TUI 실행
`znc <cmd>`    → 기존 CLI 서브커맨드 (headless 환경용)
"""
from __future__ import annotations

import click

from znc.cli.session_cmds import cmd_new, cmd_load, cmd_ls, cmd_rm, cmd_export
from znc.cli.settings_cmds import cmd_settings
from znc.cli.project_cmds import cmd_project


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
    cli()


if __name__ == "__main__":
    main()
