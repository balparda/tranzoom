# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Base."""

from __future__ import annotations

import typer

from tranzoom.core import fractal

# CLI options that can be re-used

# Image: output image size
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

# Frame: the default frame is the one that shows the whole Mandelbrot set, which is centered at
# -0.75+0j and has width 2.5; the height is the same as the width by default;
# The set <https://en.wikipedia.org/wiki/Mandelbrot_set> is contained in the rectangle with corners
# -2.5-1.25j and 0.5+1.25j, which is exactly our default here
FRAME_CENTER_RE_OPTION: typer.models.ArgumentInfo = typer.Argument(
  '-0.75', help='Real part of the center point; default is "-0.75"'
)
FRAME_CENTER_IM_OPTION: typer.models.ArgumentInfo = typer.Argument(
  '0', help='Imaginary part of the center point; default is "0"'
)
FRAME_WIDTH_OPTION: typer.models.ArgumentInfo = typer.Argument(
  '2.5', help='Width of the frame in the real plane; default is "2.5"'
)
FRAME_HEIGHT_OPTION: typer.models.ArgumentInfo = typer.Argument(
  None, help='Height of the frame in the imaginary plane; default is None, i.e, the same as width'
)
