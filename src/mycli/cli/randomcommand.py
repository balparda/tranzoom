# SPDX-FileCopyrightText: Copyright 2026 Daniel Balparda <balparda@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Random commands."""

from __future__ import annotations

import logging

import click
import typer
from transcrypto.cli import clibase

from mycli import mycli
from mycli.core import example

# Subcommand group: random
_random_app = typer.Typer(no_args_is_help=True)
mycli.app.add_typer(_random_app, name='random', help='Random utilities.')


@_random_app.command('num', help='Generate a random integer.')
@clibase.CLIErrorGuard
def RandomNum(  # documentation is help/epilog/args # noqa: D103
  *,
  ctx: click.Context,
  min_: int = typer.Option(0, '--min', help='Minimum value (inclusive).'),
  max_: int = typer.Option(100, '--max', help='Maximum value (inclusive).'),
) -> None:
  logging.debug('Generating random integer between %d and %d', min_, max_)
  config: mycli.MyCLIConfig = ctx.obj  # get application global config
  if max_ < min_:
    raise typer.BadParameter(f'--max ({max_}) must be >= --min ({min_})')
  config.console.print(example.RandomNum(min_, max_))


@_random_app.command('str', help='Generate a random string.')
@clibase.CLIErrorGuard
def RandomStr(  # documentation is help/epilog/args # noqa: D103
  *,
  ctx: click.Context,
  length: int = typer.Option(16, '--length', '-n', min=1, help='String length.'),
  alphabet: str | None = typer.Option(
    None,
    '--alphabet',
    help='Custom alphabet to sample from (defaults to [a-zA-Z0-9]).',
  ),
) -> None:
  logging.debug(
    'Generating random string of length %d with alphabet: %s',
    length,
    alphabet or '[a-zA-Z0-9]',
  )
  config: mycli.MyCLIConfig = ctx.obj  # get application global config
  config.console.print(
    example.RandomStr(length, alphabet) + (' - in color' if config.color else ' - no colors')
  )
