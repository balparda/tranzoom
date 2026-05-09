# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Image command.

<https://en.wikipedia.org/wiki/Mandelbrot_set>

README.md has good examples for different zoom levels.
"""

from __future__ import annotations

import pathlib
import time

import click
from transcrypto.cli import clibase
from transcrypto.utils import human, timer

from tranzoom import zoom
from tranzoom.cli import base
from tranzoom.core import fractal, frame, image


@zoom.app.command(
  'image',
  help='Make a Mandelbrot image.',
  epilog=(
    'Example:\n\n\n\n'
    '$ poetry run zoom image\n\n'
    '<saves fractal to disk with default frame>\n\n'
    '$ poetry run zoom image " -0.3" 0 2  # note the space because of the "-"\n\n'
    '<saves fractal to disk with center -0.3+0j and width 2>'
  ),
)
@clibase.CLIErrorGuard
def Image(  # documentation is help/epilog/args  # noqa: D103
  *,
  ctx: click.Context,
  center_re: str = base.FRAME_CENTER_RE_OPTION,  # type: ignore[assignment]
  center_im: str = base.FRAME_CENTER_IM_OPTION,  # type: ignore[assignment]
  f_width: str = base.FRAME_WIDTH_OPTION,  # type: ignore[assignment]
  f_height: str | None = base.FRAME_HEIGHT_OPTION,  # type: ignore[assignment]
  max_iter: int | None = base.MAX_ITERATIONS_OPTION,  # type: ignore[assignment]
) -> None:
  # check sanity
  config: zoom.TranZoomConfig = ctx.obj
  try:
    frm: frame.Frame = frame.Frame.FromCenter(center_re, center_im, f_width, f_height)
  except Exception as err:
    raise click.UsageError(
      f'Invalid coordinates: {center_re=}, {center_im=}, {f_width=}, {f_height=}'
    ) from err
  magnification, magnitude = frm.magnification
  magnification_str: str = (
    # beyond 10^21, human-readable formatting becomes ridiculous, so we use scientific notation
    human.HumanizedDecimal(float(magnification)) if magnitude < 21 else f'{magnification:e}'  # noqa: PLR2004
  )
  config.console.print(
    f'\n{config.img_width}x{config.img_height} Mandelbrot in frame {frm}, '
    f'precision {frm.precision} bits, {magnification_str} magnification, '
    f'{"AUTO" if max_iter is None else max_iter} iterations...\n'
  )
  # render the image
  with timer.Timer(emit_log=False) as tmr:
    img: image.Image = fractal.Mandelbrot(
      frm, config.img_width, config.img_height, max_iter=max_iter
    )
    raw_png, raw_hash = img.AsPNG()
  config.console.print(f'\nGenerated image {raw_hash!r} in {tmr}')
  # check we can recover the hash from the PNG: should never fail unless we have a bug
  w, h, png_hash, _ = image.GetBasicDataFromPNG(raw_png)
  if png_hash != raw_hash or w != config.img_width or h != config.img_height:
    raise click.ClickException(
      f'Mismatch: expected {config.img_width}x{config.img_height}/{raw_hash!r} but '
      f'got {w}x{h}/{png_hash!r} from PNG; this should never happen, please report this as a bug'
    )
  # save the image to a file named by its time/hash
  tm_str: str = time.strftime('%Y%m%d%H%M%S', time.gmtime(timer.Now()))
  # validate that img_path_prefix is a basename (no path separators) to prevent directory traversal
  filename: str = config.img_path_prefix
  if pathlib.Path(filename).name != config.img_path_prefix:
    raise click.UsageError(
      f'Invalid prefix: {config.img_path_prefix!r} has path separators (ex: "/" or "\\")'
    )
  # add date and hash to the file name if requested
  if config.img_use_date:
    filename += f'-{tm_str}'
  if config.img_use_hash:
    # use 20 chars of the hash to avoid very long file names; 20 chars = 10 bytes = 80 bits;
    # collision is 1 in 2**40 ~ 1 in 1 trillion, which is good enough for our use case
    filename += f'-{raw_hash[:20]}'
  # add .png extension, make full path, and save the file
  filename += '.png'
  full_path: pathlib.Path = (
    pathlib.Path(filename) if config.img_output_path is None else config.img_output_path / filename
  )
  full_path.write_bytes(raw_png)
  config.console.print(f'Saved to "{full_path}"\n')
