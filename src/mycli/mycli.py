# SPDX-FileCopyrightText: Copyright 2026 Daniel Balparda <balparda@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI name / short purpose.

Delete sections you don't need. Keep this docstring focused and truthful.

Purpose
- What this module does and what it does NOT do.
- Key invariants / assumptions.

Public API
- Main entry points (functions/classes) intended for other modules to import.
- Stability expectations (e.g., "internal/private", "public and stable").

Usage
- Typical usage patterns (short, runnable examples).
- If CLI-related, show how other code calls into it (not necessarily shell commands).

Inputs / Outputs
- Expected inputs, types, constraints.
- What gets printed to stdout vs stderr (if relevant).

Errors and exit codes
- Exceptions raised (and which are "user errors" vs "bugs").
- For CLI-facing modules: mapping to exit codes (if applicable).

Configuration
- Environment variables (e.g., MYCLI_*), config files, defaults.
- Where config is read from and precedence rules.

Performance / limits
- Any complexity notes, big-O, or known bottlenecks.

Security
- Handling of secrets, filesystem paths, command execution, input validation.

Notes
-----
- Links to related modules, design decisions, TODOs.

"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import click
import typer
from rich import console as rich_console
from transcrypto.cli import clibase
from transcrypto.utils import config as app_config
from transcrypto.utils import logging as cli_logging

from . import __version__


@dataclass(kw_only=True, slots=True, frozen=True)
class MyCLIConfig(clibase.CLIConfig):
  """MyCLI global context, storing the configuration."""

  foo: int
  bar: str


# CLI app setup, this is an important object and can be imported elsewhere and called
app = typer.Typer(add_completion=True, no_args_is_help=True, help='MyCLI does amazing things!')


def Run() -> None:
  """Run the CLI."""
  app()


@app.callback(invoke_without_command=True)  # have only one; this is the "constructor"
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
  foo: int = typer.Option(1000, '-f', '--foo', help='Some integer option.'),
  bar: str = typer.Option('str default', '-b', '--bar', help='Some string option.'),
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
  ctx.obj = MyCLIConfig(
    console=console,
    verbose=verbose,
    color=color,
    appconfig=app_config.InitConfig('mycli', 'mycli.bin'),  # TODO: change app & config name
    foo=foo,
    bar=bar,
  )
  # even though this is a convenient place to print(), beware that this runs even when
  # a subcommand is invoked; so prefer logging.debug/info/warning/error instead of print();
  # for example, if you run `markdown` subcommand, this will still print and spoil the output


@app.command(
  'markdown',
  help='Emit Markdown docs for the CLI (see README.md section "Creating a New Version").',
  epilog=('Example:\n\n\n\n$ poetry run mycli markdown > mycli.md\n\n<<saves CLI doc>>'),
)
@clibase.CLIErrorGuard
def Markdown(*, ctx: click.Context) -> None:  # documentation is help/epilog/args # noqa: D103
  config: MyCLIConfig = ctx.obj
  config.console.print(clibase.GenerateTyperHelpMarkdown(app, prog_name='mycli'))


@app.command('configpath', help='Print the config file path.')  # create one per command
@clibase.CLIErrorGuard
def ConfigPath(*, ctx: click.Context) -> None:  # documentation is help/epilog/args # noqa: D103
  config: MyCLIConfig = ctx.obj
  config.console.print(str(config.appconfig.path))


@app.command('hello', help='Say hello.')  # create one per command
@clibase.CLIErrorGuard
def Hello(  # documentation is help/epilog/args # noqa: D103
  *, ctx: click.Context, name: str = typer.Argument('World')
) -> None:
  logging.info('Saying hello to %s', name)
  config: MyCLIConfig = ctx.obj  # get application global config
  config.console.print(f'{config.foo} times "Hello, {name}!"')


# Import CLI modules to register their commands with the app
from mycli.cli import randomcommand  # pyright: ignore[reportUnusedImport] # noqa: E402, F401
