# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Base."""

from __future__ import annotations

import dataclasses
import pathlib

import typer
from transcrypto.cli import clibase

from tranzoom.core import fractal, frame, palette

# global CLI data, and some test stuff

# if `tests/data/images/demo-mandel-seahorse-tail.png` changes you have to update this hash!
SEAHORSE_TAIL_HASH: str = '38824cdaa58b64496ebfd86facf4d4ba4596ab18db95ac97afd643a7a892ff83'
# this is tested from `tests/cli/base_test.py` & `tests_integration/test_installed_cli.py`!

# CLI options that can be re-used

DEFAULT_IMAGE_PREFIX: str = 'mandel'

# Image: output image
IMAGE_WIDTH_OPTION: typer.models.OptionInfo = typer.Option(
  frame.DEFAULT_IMAGE_SIZE,
  '-w',
  '--width',
  min=frame.MIN_IMAGE_SIZE,
  max=frame.MAX_IMAGE_SIZE,
  help=(
    f'Width of the image; {frame.MIN_IMAGE_SIZE} ≤ w ≤ {frame.MAX_IMAGE_SIZE}; '
    f'default is {frame.DEFAULT_IMAGE_SIZE}'
  ),
)
IMAGE_HEIGHT_OPTION: typer.models.OptionInfo = typer.Option(
  frame.DEFAULT_IMAGE_SIZE,
  '-h',
  '--height',
  min=frame.MIN_IMAGE_SIZE,
  max=frame.MAX_IMAGE_SIZE,
  help=(
    f'Height of the image; {frame.MIN_IMAGE_SIZE} ≤ h ≤ {frame.MAX_IMAGE_SIZE}; '
    f'default is {frame.DEFAULT_IMAGE_SIZE}'
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
  writable=True,
  help=(
    'The local output root directory path, ex: "~/foo/bar/"; '
    'if not given, the image will be saved in the current working directory'
  ),
)
IMAGE_PREFIX_OPTION: typer.models.OptionInfo = typer.Option(
  DEFAULT_IMAGE_PREFIX,
  '--prefix',
  help=(
    f'Image save prefix; default: {DEFAULT_IMAGE_PREFIX!r} '
    '(the final file name will be "<prefix>[-<date>][-<hash20>].png", note the date and the hash '
    'can be turned off with --no-date and --no-hash, respectively)'
  ),
)
IMAGE_INCLUDE_DATE_OPTION: typer.models.OptionInfo = typer.Option(
  True,
  '--date/--no-date',
  help=(
    'If True, file names will include the date-time as YYYYMMDDhhmmss; '
    'if False, file names will not include the date-time; default is True'
  ),
)
IMAGE_INCLUDE_HASH_OPTION: typer.models.OptionInfo = typer.Option(
  True,
  '--hash/--no-hash',
  help=(
    'If True, file names will include the hash; '
    'if False, file names will not include the hash; default is True'
  ),
)

# Image: input image
IMAGE_PATH_INPUT_OPTION: typer.models.ArgumentInfo = typer.Argument(
  ...,
  exists=True,
  file_okay=True,
  dir_okay=False,
  readable=True,
  writable=False,
  help=('The local input file path, ex: "~/foo/bar/file.png"'),
)

# Frame: the default frame is the one that shows the whole Mandelbrot set, which is centered at
# -0.75+0j and has width 2.5; the height is the same as the width by default;
# The set <https://en.wikipedia.org/wiki/Mandelbrot_set> is contained in the rectangle with corners
# -2.5-1.25j and 0.5+1.25j, which is exactly our default here
FRAME_CENTER_RE_OPTION: typer.models.ArgumentInfo = typer.Argument(
  frame.DEFAULT_FRAME_CENTER_RE,
  help=f'Real part of the center point; default is {frame.DEFAULT_FRAME_CENTER_RE!r}',
)
FRAME_CENTER_IM_OPTION: typer.models.ArgumentInfo = typer.Argument(
  frame.DEFAULT_FRAME_CENTER_IM,
  help=f'Imaginary part of the center point; default is {frame.DEFAULT_FRAME_CENTER_IM!r}',
)
FRAME_WIDTH_OPTION: typer.models.ArgumentInfo = typer.Argument(
  frame.DEFAULT_FRAME_SIZE,
  help=f'Width of the frame in the real plane; default is {frame.DEFAULT_FRAME_SIZE!r}',
)
FRAME_HEIGHT_OPTION: typer.models.ArgumentInfo = typer.Argument(
  None, help='Height of the frame in the imaginary plane; default is None, i.e, the same as width'
)

# Computation Options
MAX_ITERATIONS_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '-i',
  '--iter',
  min=fractal.MIN_ITER,
  max=fractal.MAX_ITER,
  help=(
    'Maximum iterations (depth) to compute before determining escape; '
    f'{fractal.MIN_ITER} ≤ iter ≤ {fractal.MAX_ITER}; '
    f'default is None (automatic search for optimal iterations --- recommended)'
  ),
)
MAX_THREADS_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--threads',
  min=1,
  max=fractal.MAX_CONCURRENCE,
  help=(
    'Number of threads to use for rendering; default is None, which means to use all available '
    f'CPU cores; will be limited to {fractal.MAX_CONCURRENCE} threads'
  ),
)
MAX_STEPS_OPTION: typer.models.OptionInfo = typer.Option(
  0,
  '-n',
  '--max-steps',
  min=0,
  help=(
    'Maximum number of zoom steps to run; 0 means run until manually stopped (Ctrl+C); '
    'default is 0 (unlimited, run forever)'
  ),
)

# Color options
PALETTE_OPTION: typer.models.OptionInfo = typer.Option(
  palette.DEFAULT_PALETTE,
  '--palette',
  help=(
    f'Color palette to use for rendering; default is {palette.DEFAULT_PALETTE.value!r}; '
    f'available palettes: {sorted(p.value for p in palette.PALETTES)}'
  ),
)


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class TranZoomConfig(clibase.CLIConfig):
  """TranZoom global context, storing the configuration."""

  img_width: int
  img_height: int
  img_output_path: pathlib.Path | None
  img_use_date: bool
  img_use_hash: bool
  img_path_prefix: str
  max_threads: int | None
