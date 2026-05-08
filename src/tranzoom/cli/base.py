# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Base."""

from __future__ import annotations

import typer

from tranzoom.core import fractal

# CLI options that can be re-used

# Image: output image
IMAGE_WIDTH_OPTION: typer.models.OptionInfo = typer.Option(
  fractal.DEFAULT_IMAGE_SIZE,
  '-w',
  '--width',
  min=fractal.MIN_IMAGE_SIZE,
  max=fractal.MAX_IMAGE_SIZE,
  help=(
    f'Width of the image; {fractal.MIN_IMAGE_SIZE} ≤ w ≤ {fractal.MAX_IMAGE_SIZE}; '
    f'default is {fractal.DEFAULT_IMAGE_SIZE}'
  ),
)
IMAGE_HEIGHT_OPTION: typer.models.OptionInfo = typer.Option(
  fractal.DEFAULT_IMAGE_SIZE,
  '-h',
  '--height',
  min=fractal.MIN_IMAGE_SIZE,
  max=fractal.MAX_IMAGE_SIZE,
  help=(
    f'Height of the image; {fractal.MIN_IMAGE_SIZE} ≤ h ≤ {fractal.MAX_IMAGE_SIZE}; '
    f'default is {fractal.DEFAULT_IMAGE_SIZE}'
  ),
)
IMAGE_PATH_OUTPUT_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '-o',
  '--out',
  exists=True,
  file_okay=False,
  dir_okay=True,
  readable=True,
  help=(
    'The local output root directory path, ex: "~/foo/bar/"; '
    'if not given, the image will be saved in the current working directory'
  ),
)
SD_DB_USE_OPTION: typer.models.OptionInfo = typer.Option(
  True,
  '--date/--no-date',
  help=(
    'If True, file names will include the date-time as YYYYMMDDhhmmss; '
    'if False, file names will only include the hash; default is True'
  ),
)

# Frame: the default frame is the one that shows the whole Mandelbrot set, which is centered at
# -0.75+0j and has width 2.5; the height is the same as the width by default;
# The set <https://en.wikipedia.org/wiki/Mandelbrot_set> is contained in the rectangle with corners
# -2.5-1.25j and 0.5+1.25j, which is exactly our default here
FRAME_CENTER_RE_OPTION: typer.models.ArgumentInfo = typer.Argument(
  fractal.DEFAULT_FRAME_CENTER_RE,
  help=f'Real part of the center point; default is {fractal.DEFAULT_FRAME_CENTER_RE!r}',
)
FRAME_CENTER_IM_OPTION: typer.models.ArgumentInfo = typer.Argument(
  fractal.DEFAULT_FRAME_CENTER_IM,
  help=f'Imaginary part of the center point; default is {fractal.DEFAULT_FRAME_CENTER_IM!r}',
)
FRAME_WIDTH_OPTION: typer.models.ArgumentInfo = typer.Argument(
  fractal.DEFAULT_FRAME_SIZE,
  help=f'Width of the frame in the real plane; default is {fractal.DEFAULT_FRAME_SIZE!r}',
)
FRAME_HEIGHT_OPTION: typer.models.ArgumentInfo = typer.Argument(
  None, help='Height of the frame in the imaginary plane; default is None, i.e, the same as width'
)
