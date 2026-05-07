# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Image command.

<https://en.wikipedia.org/wiki/Mandelbrot_set>
"""

from __future__ import annotations

import pathlib
import time

import click
from transcrypto.cli import clibase
from transcrypto.utils import timer

from tranzoom import zoom
from tranzoom.cli import base
from tranzoom.core import fractal


@zoom.app.command(
  'image',
  help='Make a Mandelbrot image.',
  epilog=(  # TODO: write example
    ''
  ),
)
@clibase.CLIErrorGuard
def Image(  # documentation is help/epilog/args # noqa: D103
  *,
  ctx: click.Context,
  center_re: str = base.FRAME_CENTER_RE_OPTION,  # type: ignore[assignment]
  center_im: str = base.FRAME_CENTER_IM_OPTION,  # type: ignore[assignment]
  f_width: str = base.FRAME_WIDTH_OPTION,  # type: ignore[assignment]
  f_height: str | None = base.FRAME_HEIGHT_OPTION,  # type: ignore[assignment]
) -> None:
  # check sanity
  config: zoom.TranZoomConfig = ctx.obj
  try:
    frame: fractal.Frame = fractal.Frame.FromCenter(center_re, center_im, f_width, f_height)
  except Exception as err:
    raise click.UsageError(
      f'Invalid coordinates: {center_re=}, {center_im=}, {f_width=}, {f_height=}'
    ) from err
  config.console.print(f'{config.img_width}x{config.img_height} Mandelbrot in frame {frame}...')
  # render the image
  with timer.Timer(emit_log=False) as tmr:
    raw_png, raw_hash = fractal.Mandelbrot(frame, config.img_width, config.img_height)
  config.console.print(f'Generated image {raw_hash!r} in {tmr}')
  # save the image to a file named by its time/hash
  tm_str: str = time.strftime('%Y%m%d%H%M%S', time.gmtime(timer.Now()))
  filename: str = f'mandel-{tm_str}-{raw_hash[:12]}.png'
  pathlib.Path(filename).write_bytes(raw_png)
  config.console.print(f'Saved to {filename!r}')
