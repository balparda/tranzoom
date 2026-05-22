# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: tranZoom configurations command."""

from __future__ import annotations

import json

import click
import typer
from transcrypto.cli import clibase
from transcrypto.utils import timer

from tranzoom import tranz
from tranzoom.cli import base

config_app = typer.Typer(
  no_args_is_help=True,
  help=(
    'Examples:\n\n\n\n'
    'poetry run tranz config get\n'
    'poetry run tranz config set use_db true\n'
    'poetry run tranz config set foo bar'
  ),
)
tranz.app.add_typer(config_app, name='config')


@config_app.command(
  'get',
  help='Read a configuration file from disk.',
  epilog=(
    'Examples:\n\n\n\n$ poetry run tranz config get\n\n<shows config values, save time, etc>'
  ),
)
@clibase.CLIErrorGuard
def Get(  # documentation is help/epilog/args  # noqa: D103
  *,
  ctx: click.Context,
) -> None:
  # read
  config: base.TranZoomConfig = ctx.obj
  cnf: base.ConfigType = config.GetConfig()
  # print
  config.console.print()
  if config.appconfig.path.exists():
    config.console.print(
      f'Config read from [yellow]"{config.appconfig.path}"[/], '
      f'saved @ {timer.TimeStr(cnf["last_save"])}'
    )
  else:
    config.console.print('Config file does [red]NOT EXIST ON DISK[/] yet, just showing defaults')
  config.console.print()
  config.console.print_json(json.dumps(cnf), indent=2)
  config.console.print()


@config_app.command(
  'set',
  help='Set values in a configuration file (saves to disk).',
  epilog=(
    'Examples:\n\n\n\n'
    '$ poetry run tranz config set use_db true\n\n'
    '<set use_db option to True>\n\n\n\n'
    '$ poetry run tranz config set foo bar\n\n'
    '<set option "foo" to value "bar">'
  ),
)
@clibase.CLIErrorGuard
def Set(  # documentation is help/epilog/args  # noqa: D103
  *,
  ctx: click.Context,
  key: str = base.CONFIG_KEY_ARGUMENT,  # type: ignore[assignment]
  value: str = base.CONFIG_VALUE_ARGUMENT,  # type: ignore[assignment]
) -> None:
  # read
  config: base.TranZoomConfig = ctx.obj
  cnf: base.ConfigType = config.GetConfig()
  # check parameters
  key = key.strip().lower()
  if key not in base.CONFIG_SETTABLE_KEYS:
    raise click.ClickException(
      f'Invalid config key {key!r}. Valid keys: {sorted(base.CONFIG_SETTABLE_KEYS)}'
    )
  value = value.strip()
  if not value:
    raise click.ClickException('Config value cannot be empty')
  # convert value to the right type
  try:
    if base.CONFIG_SETTABLE_KEYS[key] is bool:
      # special handling for bool: accept "true"/"false" (case-insensitive)
      if value.lower() in {'true', '1', 'yes', 'on'}:
        cnf[key] = True  # type: ignore[literal-required]
      elif value.lower() in {'false', '0', 'no', 'off'}:
        cnf[key] = False  # type: ignore[literal-required]
      else:
        raise ValueError(f'Invalid boolean value: {value!r}')  # noqa: TRY301
    else:
      cnf[key] = base.CONFIG_SETTABLE_KEYS[key](value)  # type: ignore[literal-required]
  except ValueError as err:
    raise click.ClickException(
      f'Invalid value for {key!r}: {value!r}; '
      f'expecting type {base.CONFIG_SETTABLE_KEYS[key].__name__}'
    ) from err
  # save
  config.SetConfig(cnf)
  # print
  config.console.print()
  config.console.print(f'Config saved to [yellow]"{config.appconfig.path}"[/]')
  config.console.print()
  config.console.print_json(json.dumps(cnf), indent=2)
  config.console.print()
