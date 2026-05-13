# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Mandelbrot generation command.

<https://en.wikipedia.org/wiki/Mandelbrot_set>

README.md has good examples for different zoom levels.
"""

from __future__ import annotations

import json
import pathlib

import click
from transcrypto.cli import clibase
from transcrypto.utils import human, timer

from tranzoom import mandel
from tranzoom.cli import base
from tranzoom.core import fractal, frame, image, palette


@mandel.app.command(
  'gen',
  help='Generate a Mandelbrot image.',
  epilog=(
    'Examples:\n\n\n\n'
    '$ poetry run mandel gen\n\n'
    '1024x1024 Mandelbrot in frame [(-3/4, 0) @ 5/2] ...\n\n'
    '...\n\n'
    'Saved to "mandel-<date>-<hash>.png"\n\n\n\n'
    '$ poetry run mandel -w 512 -h 512 gen " -0.74303" "0.126433" "0.01611"  '
    '# note the space because of the "-"\n\n'
    '<saves Mandelbrot to disk with center --0.74303+0.126433j and width 0.01611>'
  ),
)
@clibase.CLIErrorGuard
def Gen(  # documentation is help/epilog/args  # noqa: D103
  *,
  ctx: click.Context,
  center_re: str = base.FRAME_CENTER_RE_ARGUMENT,  # type: ignore[assignment]
  center_im: str = base.FRAME_CENTER_IM_ARGUMENT,  # type: ignore[assignment]
  f_width: str = base.FRAME_WIDTH_ARGUMENT,  # type: ignore[assignment]
  f_height: str | None = base.FRAME_HEIGHT_ARGUMENT,  # type: ignore[assignment]
  max_iter: int | None = base.MAX_ITERATIONS_OPTION,  # type: ignore[assignment]
  pal: palette.Palette = base.PALETTE_OPTION,  # type: ignore[assignment]
) -> None:
  # check sanity, create frame, and print info about the image we're going to generate
  config: base.TranZoomConfig = ctx.obj
  try:
    frm: frame.Frame = frame.Frame.FromCenter(
      frame.Fractal.MANDELBROT, center_re, center_im, f_width, f_height
    )
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
      frm, config.img_width, config.img_height, max_iter=max_iter, n_processes=config.max_threads
    )
    raw_png, raw_hash = img.AsPNG(pal=pal)
  config.console.print(f'\nGenerated image {raw_hash!r} in {tmr}, escape range {img.escape_range}')
  # check we can recover the hash from the PNG: should never fail unless we have a bug
  w, h, png_hash, _ = image.GetBasicDataFromPNG(raw_png)
  if png_hash != raw_hash or w != config.img_width or h != config.img_height:
    raise click.ClickException(
      f'Mismatch: expected {config.img_width}x{config.img_height}/{raw_hash!r} but '
      f'got {w}x{h}/{png_hash!r} from PNG; this should never happen, please report this as a bug'
    )
  # save the image to a file named by its time/hash
  full_path: pathlib.Path = image.MakeImagePath(
    config.img_output_path,
    config.img_use_date,
    config.img_use_hash,
    config.img_path_prefix,
    raw_hash,
  )
  full_path.write_bytes(raw_png)
  config.console.print(f'Saved to "{full_path}"\n')


@mandel.app.command(
  'read',
  help='Read a Mandelbrot image.',
  epilog=(
    'Examples:\n\n\n\n'
    '$ poetry run mandel read /path/to/image.png\n\n'
    '1024x1024 Mandelbrot in frame [(-3/4, 0) @ 5/2] ...\n\n'
    '...\n\n'
  ),
)
@clibase.CLIErrorGuard
def Read(  # documentation is help/epilog/args  # noqa: D103
  *,
  ctx: click.Context,
  image_path: pathlib.Path = base.IMAGE_PATH_INPUT_ARGUMENT,  # type: ignore[assignment]
  iterm: bool = base.IMAGE_PRINT_ITERM_OPTION,  # type: ignore[assignment]
) -> None:
  # check sanity
  config: base.TranZoomConfig = ctx.obj
  image_path = image_path.expanduser().resolve()
  image_data: bytes = image_path.read_bytes()
  w, h, png_hash, info = image.GetBasicDataFromPNG(image_data)
  config.console.print()
  config.console.print(f'[yellow]{str(image_path)!r}[/yellow]')
  config.console.print(f'[green]{w}x{h}[/green] (wxh) / [cyan]{png_hash}[/cyan]')
  config.console.print()
  if image.META_EVALUATION_KEY in info:
    info[image.META_EVALUATION_KEY] = json.loads(str(info[image.META_EVALUATION_KEY]))
  config.console.print_json(data=info, indent=2)
  config.console.print()
  if iterm:
    image.PrintITerm2(image_data)
    config.console.print()
