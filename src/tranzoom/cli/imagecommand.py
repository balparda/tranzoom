# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Random commands."""

from __future__ import annotations

import pathlib

import click
from transcrypto.cli import clibase

from tranzoom import zoom
from tranzoom.core import fractal


@zoom.app.command(
  'image',
  help='Make an image.',
  epilog=(  # TODO: write example
    ''
  ),
)
@clibase.CLIErrorGuard
def Image(  # documentation is help/epilog/args # noqa: D103
  *,
  ctx: click.Context,
) -> None:
  # check sanity
  config: zoom.TranZoomConfig = ctx.obj
  # if not config.db and not config.output:  # TODO: use or remove
  #   raise click.UsageError('With `--no-db` you must specify `--out`')  # noqa: ERA001

  # TODO: do something useful!
  raw_png: bytes = fractal.Mandelbrot(fractal.Frame.FromCenter('0', '0', '2'), 1024, 1024)
  pathlib.Path('output.png').write_bytes(raw_png)

  config.console.print()
