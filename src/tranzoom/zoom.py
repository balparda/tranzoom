# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI name / short purpose."""

from __future__ import annotations

from dataclasses import dataclass

import click
import typer
from rich import console as rich_console
from transcrypto.cli import clibase
from transcrypto.utils import config as app_config
from transcrypto.utils import logging as cli_logging

from . import __version__


@dataclass(kw_only=True, slots=True, frozen=True)
class TranZoomConfig(clibase.CLIConfig):
  """TranZoom global context, storing the configuration."""

  img_width: int
  img_height: int


# CLI app setup, this is an important object and can be imported elsewhere and called
app = typer.Typer(
  add_completion=True,
  no_args_is_help=True,
  help='TranZoom does amazing things!',  # keep in sync with Main() app.callback help
  # TODO: add epilog and actual help
)


def Run() -> None:
  """Run the CLI."""
  app()


@app.callback(
  invoke_without_command=True,
  help='TranZoom does amazing things!',  # keep in sync with app help
  # TODO: add actual help
)  # have only one; this is the "constructor"
@clibase.CLIErrorGuard
def Main(  # documentation is help/epilog/args # noqa: D103
  *,
  ctx: click.Context,  # global context
  version: bool = typer.Option(False, '--version', help='Show version and exit.'),
  verbose: int = typer.Option(
    0,
    '-v',
    '--verbose',
    count=True,
    help='Verbosity (nothing=ERROR, -v=WARNING, -vv=INFO, -vvv=DEBUG).',
    min=0,
    max=3,
  ),
  color: bool | None = typer.Option(
    None,
    '--color/--no-color',
    help=(
      'Force enable/disable colored output (respects NO_COLOR env var if not provided). '
      'Defaults to having colors.'  # state default because None default means docs don't show it
    ),
  ),
  img_width: int = typer.Option(
    1024,
    '-w',
    '--width',
    min=4,
    max=16384,
    help='Width of the image; 4 <= width <= 16384; default is 1024',
  ),
  img_height: int = typer.Option(
    1024,
    '-h',
    '--height',
    min=4,
    max=16384,
    help='Height of the image; 4 <= height <= 16384; default is 1024',
  ),
) -> None:
  if version:
    typer.echo(__version__)
    raise typer.Exit(0)
  console: rich_console.Console
  console, verbose, color = cli_logging.InitLogging(
    verbose,
    color=color,
    include_process=False,  # decide if you want process names in logs
    soft_wrap=False,  # decide if you want soft wrapping of long lines
  )
  # create context with the arguments we received
  ctx.obj = TranZoomConfig(
    console=console,
    verbose=verbose,
    color=color,
    appconfig=app_config.InitConfig('tranzoom', 'config.bin'),
    img_width=img_width,
    img_height=img_height,
  )
  # even though this is a convenient place to print(), beware that this runs even when
  # a subcommand is invoked; so prefer logging.debug/info/warning/error instead of print();
  # for example, if you run `markdown` subcommand, this will still print and spoil the output


@app.command(
  'markdown',
  help='Emit Markdown docs for the CLI (see README.md section "Creating a New Version").',
  epilog=('Example:\n\n\n\n$ poetry run zoom markdown > zoom.md\n\n<<saves CLI doc>>'),
)
@clibase.CLIErrorGuard
def Markdown(*, ctx: click.Context) -> None:  # documentation is help/epilog/args # noqa: D103
  config: TranZoomConfig = ctx.obj
  config.console.print(clibase.GenerateTyperHelpMarkdown(app, prog_name='zoom'))


# Import CLI modules to register their commands with the app
from tranzoom.cli import imagecommand  # pyright: ignore[reportUnusedImport] # noqa: E402, F401
