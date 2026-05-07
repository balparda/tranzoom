# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Image command.

<https://en.wikipedia.org/wiki/Mandelbrot_set>

Good examples for different zoom levels:

$ poetry run zoom image
1024x1024 Mandelbrot in frame [(-3/4, 0) ± 5/2],
precision 80 bits, 1 magnification, 512 iterations...
<contains the whole set, centered at -0.75+0j, with width 2.5>

$ poetry run zoom -w 512 -h 512 image " -0.743030" "0.126433" "0.01611"
512x512 Mandelbrot in frame [(-74303/100000, 126433/1000000) ± 1611/100000],
precision 83 bits, 155.183 magnification, 1072 iterations...
<https://en.wikipedia.org/wiki/File:Mandel_zoom_03_seehorse.jpg>

$ poetry run zoom -w 512 -h 512 image " -0.7436499" "0.13188204" "0.00073801"
512x512 Mandelbrot in frame [(-7436499/10000000, 3297051/25000000) ± 73801/100000000],
precision 88 bits, 3.387 k magnification, 1415 iterations...
<https://en.wikipedia.org/wiki/File:Mandel_zoom_05_tail_part.jpg>

$ poetry run zoom -w 256 -h 256 image " -0.743644786" "0.1318252536" "0.0000029336"
256x256 Mandelbrot in frame [(-371822393/500000000, 164781567/1250000000) ± 3667/1250000000],
precision 96 bits, 852.195 k magnification, 2030 iterations...
<https://en.wikipedia.org/wiki/File:Mandel_zoom_08_satellite_antenna.jpg>

$ poetry run zoom -w 256 -h 256 image " -0.74364388717342" "0.13182590425182" "0.00000000059849"
256x256 Mandelbrot in frame [(-37182194358671/50000000000000, 6591295212591/50000000000000) ±
59849/100000000000000], precision 108 bits, 4.177 G magnification, 2974 iterations...
<https://en.wikipedia.org/wiki/File:Mandel_zoom_13_satellite_seehorse_tail_with_julia_island.jpg>

$ poetry run zoom -w 256 -h 256 image " -0.743643887036" "0.13182590421" "0.000000000006"
256x256 Mandelbrot in frame [(-185910971759/250000000000, 13182590421/100000000000) ±
3/500000000000], precision 115 bits, 416.667 G magnification, 3486 iterations...
<https://commons.wikimedia.org/wiki/File:Mandel_zoom_15_one_island.jpg>
"""

from __future__ import annotations

import math
import pathlib
import time

import click
import gmpy2
from transcrypto.cli import clibase
from transcrypto.utils import human, timer

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
  mag: gmpy2.mpfr | gmpy2.mpc = gmpy2.sqrt(base.DEFAULT_FRAME.area / frame.area)
  iter_limit: int = int(512 + 256 * math.log10(float(mag.real))) if mag.real > 1 else 512
  # TODO: histogram-based iteration limit
  config.console.print(
    f'{config.img_width}x{config.img_height} Mandelbrot in frame {frame}, '
    f'precision {frame.precision} bits, {human.HumanizedDecimal(float(mag.real))} magnification, '
    f'{iter_limit} iterations...'
  )
  # render the image
  with timer.Timer(emit_log=False) as tmr:
    raw_png, raw_hash = fractal.Mandelbrot(
      frame, config.img_width, config.img_height, max_iter=iter_limit
    )
  config.console.print(f'Generated image {raw_hash!r} in {tmr}')
  # save the image to a file named by its time/hash
  tm_str: str = time.strftime('%Y%m%d%H%M%S', time.gmtime(timer.Now()))
  filename: str = f'mandel-{tm_str}-{raw_hash[:12]}.png'
  pathlib.Path(filename).write_bytes(raw_png)
  config.console.print(f'Saved to {filename!r}')
