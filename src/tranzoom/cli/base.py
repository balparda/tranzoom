# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Base."""

from __future__ import annotations

import typer

from tranzoom.core import fractal

# CLI options that can be re-used
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
