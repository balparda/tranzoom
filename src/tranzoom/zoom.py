# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Zoom CLI entry point for the TranZoom Mandelbrot renderer."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

import click
import typer
from rich import console as rich_console
from transcrypto.cli import clibase
from transcrypto.utils import config as app_config
from transcrypto.utils import logging as cli_logging

from tranzoom.cli import base

from . import __version__


@dataclass(kw_only=True, slots=True, frozen=True)
class TranZoomConfig(clibase.CLIConfig):
  """TranZoom global context, storing the configuration."""

  img_width: int
  img_height: int
  img_output_path: pathlib.Path | None
  img_use_date: bool
  img_use_hash: bool
  img_path_prefix: str
  max_threads: int | None


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
  img_width: int = base.IMAGE_WIDTH_OPTION,  # type: ignore[assignment]
  img_height: int = base.IMAGE_HEIGHT_OPTION,  # type: ignore[assignment]
  img_output_path: pathlib.Path | None = base.IMAGE_PATH_OUTPUT_OPTION,  # type: ignore[assignment]
  img_path_prefix: str = base.IMAGE_PREFIX_OPTION,  # type: ignore[assignment]
  img_use_date: bool = base.IMAGE_INCLUDE_DATE_OPTION,  # type: ignore[assignment]
  img_use_hash: bool = base.IMAGE_INCLUDE_HASH_OPTION,  # type: ignore[assignment]
  max_threads: int | None = base.MAX_THREADS_OPTION,  # type: ignore[assignment]
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
    img_output_path=None if img_output_path is None else img_output_path.expanduser().resolve(),
    img_path_prefix=img_path_prefix,
    img_use_date=img_use_date,
    img_use_hash=img_use_hash,
    max_threads=max_threads,
  )
  # even though this is a convenient place to print(), beware that this runs even when
  # a subcommand is invoked; so prefer logging.debug/info/warning/error instead of print();
  # for example, if you run `markdown` subcommand, this will still print and spoil the output


@app.command(
  'markdown',
  help='Emit Markdown docs for the CLI (see README.md section "Versioning and releases").',
  epilog=('Example:\n\n\n\n$ poetry run zoom markdown > zoom.md\n\n<<saves CLI doc>>'),
)
@clibase.CLIErrorGuard
def Markdown(*, ctx: click.Context) -> None:  # documentation is help/epilog/args # noqa: D103
  config: TranZoomConfig = ctx.obj
  config.console.print(clibase.GenerateTyperHelpMarkdown(app, prog_name='zoom'))


# Import CLI modules to register their commands with the app
from tranzoom.cli import imagecommand  # pyright: ignore[reportUnusedImport] # noqa: E402, F401
