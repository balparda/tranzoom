# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Random commands."""

from __future__ import annotations

import click
from transcrypto.cli import clibase

from tranzoom import zoom
from tranzoom.core import fractal


@zoom.app.command(
  'image',
  help='Make an image.',
  epilog=(  # TODO
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
  # if not config.db and not config.output:
  #   raise click.UsageError('With `--no-db` you must specify `--out`')

  fractal.render_mandelbrot(
    out_dir='renders/seahorse',
    x='-0.743643887037151',
    y='0.131825904205330',
    dx='1e-8',
    precision=40,
    width=1920,
    height=1080,
    max_iter=20_000,
  )

  config.console.print()
