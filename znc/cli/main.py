"""
znc CLI 메인 진입점
"""
from __future__ import annotations

import click

from znc.core.config import load_settings
from znc.core.i18n import MESSAGES
from znc.cli.session_cmds import cmd_new, cmd_load, cmd_ls, cmd_rm, cmd_export
from znc.cli.settings_cmds import cmd_settings
from znc.cli.project_cmds import cmd_project


@click.group(
    context_settings=dict(help_option_names=["-h", "--help"]),
    invoke_without_command=True,
)
@click.pass_context
def cli(ctx):
    settings = load_settings()
    lang = settings.get("lang", "ko")
    if ctx.invoked_subcommand is None:
        click.secho(
            MESSAGES.get(lang, MESSAGES["en"])["help_header"],
            fg="cyan",
            bold=True,
        )


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
